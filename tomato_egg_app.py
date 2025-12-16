
# tomato_egg_app.py
import math
import random
import uuid
from datetime import datetime
from io import BytesIO

import pandas as pd
import streamlit as st
import altair as alt
import folium
from streamlit_folium import st_folium
from streamlit_geolocation import streamlit_geolocation

# =========================
# Page config
# =========================
st.set_page_config(page_title="一餐的碳足跡大冒險", page_icon="🍽️", layout="centered")

# =========================
# Helpers
# =========================
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))

def ensure_cols(df):
    # Expect columns: 族群, 產品名稱, 碳足跡(kg), optional 重量
    colmap = {c: c.strip() for c in df.columns}
    df = df.rename(columns=colmap)
    if "族群" not in df.columns or "產品名稱" not in df.columns or "碳足跡(kg)" not in df.columns:
        st.error("Excel 需要至少包含欄位：族群、產品名稱、碳足跡(kg)")
        st.stop()
    # Weight optional: try common names
    wcol = None
    for c in ["重量(kg)", "重量(g)", "重量"]:
        if c in df.columns:
            wcol = c
            break
    if wcol is None:
        df["_weight_kg"] = 0.0
    else:
        if "g" in wcol:
            df["_weight_kg"] = pd.to_numeric(df[wcol], errors="coerce").fillna(0) / 1000.0
        else:
            df["_weight_kg"] = pd.to_numeric(df[wcol], errors="coerce").fillna(0)
    df["_cf_kg"] = pd.to_numeric(df["碳足跡(kg)"], errors="coerce").fillna(0)
    return df

def safe_sample(df, n):
    if len(df) == 0:
        return df.copy()
    return df.sample(n=min(n, len(df)), replace=False, random_state=random.randint(1, 10_000)).reset_index(drop=True)

# =========================
# Load Excel
# =========================
st.title("🍽️ 一餐的碳足跡大冒險")

uploaded = st.file_uploader("請上傳《碳足跡4.xlsx》", type=["xlsx"])
if not uploaded:
    st.stop()

df = pd.read_excel(BytesIO(uploaded.getvalue()))
df = ensure_cols(df)

# Groups
g1 = df[df["族群"].astype(str) == "1"]       # 主食
g11 = df[df["族群"].astype(str) == "1-1"]    # 油
g12 = df[df["族群"].astype(str) == "1-2"]    # 水
g2 = df[df["族群"].astype(str) == "2"]       # 飲料
g3 = df[df["族群"].astype(str) == "3"]       # 甜點

# =========================
# User & round
# =========================
st.subheader("🧑‍🎓 基本資料")
name = st.text_input("姓名")
device_id = st.session_state.setdefault("device_id", str(uuid.uuid4())[:8])

round_no = 1
if "local_rounds" not in st.session_state:
    st.session_state["local_rounds"] = {}
if name:
    st.session_state["local_rounds"][name] = st.session_state["local_rounds"].get(name, 0) + 1
    round_no = st.session_state["local_rounds"][name]

st.caption(f"本次為第 **{round_no}** 次測試")

# =========================
# Main dish selection
# =========================
st.subheader("🍚 主食（從 5 選 2）")
pool = st.session_state.setdefault("food_pool", safe_sample(g1, 5))

labels = [f"{r['產品名稱']}（{r['_cf_kg']:.3f} kgCO₂e）" for _, r in pool.iterrows()]
sel = st.multiselect("選擇兩種主食", labels, max_selections=2)

selected_rows = []
for lab in sel:
    name_only = lab.split("（")[0]
    selected_rows.append(pool[pool["產品名稱"] == name_only].iloc[0])

# Cooking
cook_rows = []
if len(selected_rows) == 2:
    st.markdown("### 🍳 料理方式")
    for i, r in enumerate(selected_rows, 1):
        method = st.radio(f"{r['產品名稱']}", ["水煮", "油炸"], key=f"cook_{i}", horizontal=True)
        if method == "水煮":
            w = safe_sample(g12, 1).iloc[0] if len(g12) else None
        else:
            w = safe_sample(g11, 1).iloc[0] if len(g11) else None
        cook_rows.append((r, method, w))

# Drink & dessert
st.subheader("🥤 飲料")
drink = None
if len(g2):
    opts = [f"{r['產品名稱']}（{r['_cf_kg']:.3f} kgCO₂e）" for _, r in g2.iterrows()]
    pick = st.selectbox("選擇飲料（可不選）", ["不喝"] + opts)
    if pick != "不喝":
        nm = pick.split("（")[0]
        drink = g2[g2["產品名稱"] == nm].iloc[0]

st.subheader("🍰 甜點")
dessert = None
if len(g3):
    opts = [f"{r['產品名稱']}（{r['_cf_kg']:.3f} kgCO₂e）" for _, r in g3.iterrows()]
    pick = st.selectbox("選擇甜點（可不選）", ["不吃"] + opts)
    if pick != "不吃":
        nm = pick.split("（")[0]
        dessert = g3[g3["產品名稱"] == nm].iloc[0]

# =========================
# Transport with map
# =========================
st.subheader("🗺️ 交通")
geo = streamlit_geolocation()
origin = None
if geo and geo.get("latitude") and geo.get("longitude"):
    origin = (float(geo["latitude"]), float(geo["longitude"]))

stores = [
    {"name": "全聯A", "lat": 24.150, "lon": 120.670},
    {"name": "全聯B", "lat": 24.145, "lon": 120.678},
]
store_name = st.selectbox("選擇分店", [s["name"] for s in stores])
store = next(s for s in stores if s["name"] == store_name)

dist_km = 0.0
if origin:
    dist_km = haversine_km(origin[0], origin[1], store["lat"], store["lon"]) * 2

m = folium.Map(location=[store["lat"], store["lon"]], zoom_start=14)
folium.Marker([store["lat"], store["lon"]], popup=store["name"]).add_to(m)
st_folium(m, height=300)

st.info(f"來回距離：約 **{dist_km:.2f} km**")

# Transport modes
TRANSPORTS = {
    "走路（0）": {"coef": 0.0, "unit": "pkm"},
    "機車": {"coef": 9.51e-2, "unit": "pkm"},
    "自用小客車(汽油)": {"coef": 1.15e-1, "unit": "pkm"},
    "低溫貨車": {"coef": 2.71, "unit": "tkm"},
}
tname = st.selectbox("交通工具", list(TRANSPORTS.keys()))
tinfo = TRANSPORTS[tname]

# =========================
# Totals
# =========================
food_cf = sum(r["_cf_kg"] for r in selected_rows)
cook_cf = sum((w["_cf_kg"] if w is not None else 0) for _, _, w in cook_rows)
drink_cf = drink["_cf_kg"] if drink is not None else 0
dessert_cf = dessert["_cf_kg"] if dessert is not None else 0

total_weight_kg = (
    sum(r["_weight_kg"] for r in selected_rows)
    + sum((w["_weight_kg"] if w is not None else 0) for _, _, w in cook_rows)
    + (drink["_weight_kg"] if drink is not None else 0)
    + (dessert["_weight_kg"] if dessert is not None else 0)
)

if tinfo["unit"] == "pkm":
    transport_cf = dist_km * tinfo["coef"]
else:
    transport_cf = dist_km * (total_weight_kg / 1000.0) * tinfo["coef"]

total_cf = food_cf + cook_cf + drink_cf + dessert_cf + transport_cf

# =========================
# Results & charts
# =========================
st.subheader("📊 結果")
st.write(f"**總重量**：{total_weight_kg:.3f} kg")
st.write(f"**交通碳足跡**：{transport_cf:.3f} kgCO₂e")
st.write(f"**總碳足跡**：{total_cf:.3f} kgCO₂e")

chart_df = pd.DataFrame({
    "項目": ["主食", "料理", "飲料", "甜點", "交通"],
    "kgCO2e": [food_cf, cook_cf, drink_cf, dessert_cf, transport_cf]
})
bar = alt.Chart(chart_df).mark_bar().encode(x="項目", y="kgCO2e")
pie = alt.Chart(chart_df).mark_arc().encode(theta="kgCO2e", color="項目")
st.altair_chart(bar, use_container_width=True)
st.altair_chart(pie, use_container_width=True)

# =========================
# Download CSV
# =========================
row = {
    "name": name,
    "round": round_no,
    "total_weight_kg": total_weight_kg,
    "food_cf": food_cf,
    "cook_cf": cook_cf,
    "drink_cf": drink_cf,
    "dessert_cf": dessert_cf,
    "transport_cf": transport_cf,
    "total_cf": total_cf,
    "timestamp": datetime.now().isoformat(timespec="seconds"),
}
csv = pd.DataFrame([row]).to_csv(index=False).encode("utf-8-sig")
st.download_button("⬇️ 下載 CSV", csv, "result.csv", "text/csv")
