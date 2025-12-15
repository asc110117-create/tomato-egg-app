
# tomato_egg_app.py
import math
import re
from datetime import datetime
from io import BytesIO

import pandas as pd
import streamlit as st
import altair as alt

# =========================
# Basic page config
# =========================
st.set_page_config(page_title="一餐的碳足跡大冒險", page_icon="🍽️", layout="centered")
st.title("🍽️ 一餐的碳足跡大冒險")

# =========================
# Utilities
# =========================
def parse_cf_to_g(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return 0.0
    if isinstance(val, (int, float)):
        return float(val) * 1000 if float(val) <= 50 else float(val)
    s = str(val).lower().replace(" ", "")
    s = s.replace("kgco2e", "kg").replace("gco2e", "g")
    m = re.search(r"([0-9.]+)(kg|g)?", s)
    if not m:
        return 0.0
    num = float(m.group(1))
    unit = m.group(2)
    if unit == "kg":
        return num * 1000
    if unit == "g":
        return num
    return num * 1000 if num <= 50 else num

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return 2 * R * math.asin(math.sqrt(a))

# =========================
# Load Excel safely
# =========================
@st.cache_data
def load_excel(file):
    df = pd.read_excel(file)
    df = df.iloc[:, :4]
    df.columns = ["group", "name", "cf_raw", "unit"]
    df["cf_g"] = df["cf_raw"].apply(parse_cf_to_g)
    df["cf_kg"] = df["cf_g"] / 1000
    df["group"] = df["group"].astype(str)
    return df

try:
    with open("產品碳足跡3.xlsx", "rb") as f:
        df = load_excel(f)
except Exception:
    up = st.file_uploader("請上傳碳足跡 Excel", type=["xlsx"])
    if up is None:
        st.stop()
    df = load_excel(up)

# =========================
# Student + round
# =========================
student = st.text_input("請輸入你的名字")
if not student:
    st.stop()

round_no = st.session_state.get("round_no", 1)
st.session_state["round_no"] = round_no
st.info(f"📘 這是你第 {round_no} 次測試")

# =========================
# Main food (group 1)
# =========================
food_df = df[df["group"] == "1"]
if food_df.empty:
    st.error("❌ Excel 中找不到 group=1 的主食")
    st.stop()

meal = food_df.sample(min(3, len(food_df)), random_state=round_no).reset_index(drop=True)
st.subheader("🍛 主食（3 道）")
st.dataframe(meal[["name", "cf_kg", "unit"]])

food_cf = meal["cf_kg"].sum()

# =========================
# Cooking method (1-1 oil / 1-2 water)
# =========================
st.subheader("🍳 料理方式")
cook_cf = 0.0
for i, row in meal.iterrows():
    method = st.radio(
        f"{row['name']}",
        ["水煮", "油炸"],
        key=f"cook_{i}",
        horizontal=True,
    )
    if method == "水煮":
        pick = df[df["group"] == "1-2"].sample(1).iloc[0]
    else:
        pick = df[df["group"] == "1-1"].sample(1).iloc[0]
    cook_cf += pick["cf_kg"]
    st.caption(f"{method}：{pick['name']}（{pick['cf_kg']:.3f} kgCO₂e）")

# =========================
# Drink (group 2)
# =========================
st.subheader("🥤 飲料")
drink_opts = ["不喝"] + [
    f"{r['name']}（{r['cf_kg']:.3f} kgCO₂e / {r['unit']}）"
    for _, r in df[df["group"] == "2"].iterrows()
]
drink_choice = st.selectbox("選擇飲料", drink_opts)
drink_cf = 0.0
if drink_choice != "不喝":
    idx = drink_opts.index(drink_choice) - 1
    drink_cf = df[df["group"] == "2"].iloc[idx]["cf_kg"]

# =========================
# Dessert (group 3)
# =========================
st.subheader("🍰 甜點")
dessert_df = df[df["group"] == "3"]
dessert_opts = [
    f"{r['name']}（{r['cf_kg']:.3f} kgCO₂e / {r['unit']}）"
    for _, r in dessert_df.iterrows()
]
dessert_choice = st.selectbox("選擇甜點", ["不吃"] + dessert_opts)
dessert_cf = 0.0
if dessert_choice != "不吃":
    idx = dessert_opts.index(dessert_choice)
    dessert_cf = dessert_df.iloc[idx]["cf_kg"]

# =========================
# Transport (distance-based)
# =========================
st.subheader("🚚 交通")
mode = st.selectbox(
    "交通方式",
    [
        "走路（0 kgCO₂e）",
        "汽車（2.71 kgCO₂e / 噸公里）",
    ],
)
transport_cf = 0.0
if "汽車" in mode:
    km = st.number_input("距離（km）", 0.0, 100.0, 12.0)
    weight_kg = st.number_input("食材總重量（kg）", 0.1, 50.0, 0.8)
    transport_cf = km * (weight_kg / 1000) * 2.71
    st.caption(f"公式：{km} × {weight_kg/1000:.4f} × 2.71 = {transport_cf:.3f} kgCO₂e")

# =========================
# Total + charts
# =========================
total = food_cf + cook_cf + drink_cf + dessert_cf + transport_cf
st.success(f"🌍 本餐碳足跡：{total:.3f} kgCO₂e")

chart_df = pd.DataFrame(
    {
        "項目": ["主食", "料理", "飲料", "甜點", "交通"],
        "kgCO2e": [food_cf, cook_cf, drink_cf, dessert_cf, transport_cf],
    }
)

bar = (
    alt.Chart(chart_df)
    .mark_bar()
    .encode(x="項目", y="kgCO2e")
)
pie = (
    alt.Chart(chart_df)
    .mark_arc()
    .encode(theta="kgCO2e", color="項目")
)

st.altair_chart(bar, use_container_width=True)
st.altair_chart(pie, use_container_width=True)

# =========================
# CSV download
# =========================
out = {
    "timestamp": datetime.now().isoformat(),
    "student": student,
    "round": round_no,
    "total_kgco2e": total,
}
csv = pd.DataFrame([out]).to_csv(index=False).encode("utf-8-sig")
st.download_button("⬇️ 下載 CSV", csv, "carbon_meal.csv", "text/csv")
