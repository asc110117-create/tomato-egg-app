
# carbon_meal_app_COMPLETE_SAFE_V2.py

import streamlit as st
import pandas as pd
import random
import altair as alt
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="一餐的碳足跡（SAFE v2）", layout="centered")
st.title("🍱 一餐的碳足跡（SAFE v2）")

# ---------- utilities ----------
@st.cache_data
def load_data():
    df = pd.read_excel("產品碳足跡3.xlsx")
    df = df.iloc[:, :5]
    cols = ["code", "name", "cf", "unit", "weight"][:len(df.columns)]
    df.columns = cols
    if "weight" not in df.columns:
        df["weight"] = 0.0
    df["code"] = df["code"].astype(str)
    df["cf"] = pd.to_numeric(df["cf"], errors="coerce").fillna(0.0)
    return df

def safe_sample(df, n):
    if len(df) == 0:
        return df
    return df.sample(n=min(n, len(df)), replace=False).reset_index(drop=True)

# ---------- load ----------
df = load_data()
food_df = df[df["code"] == "1"]
oil_df = df[df["code"] == "1-1"]
water_df = df[df["code"] == "1-2"]
drink_df = df[df["code"] == "2"]
dessert_df = df[df["code"] == "3"]

# ---------- session ----------
if "meal" not in st.session_state:
    st.session_state.meal = safe_sample(food_df, 3)

# ---------- student ----------
st.subheader("👩‍🎓 學生資訊")
student = st.text_input("姓名（必填）")

# ---------- main food ----------
st.subheader("① 主食")

if st.button("🔄 更換一組食材"):
    st.session_state.meal = safe_sample(food_df, 3)

meal = st.session_state.meal
if meal.empty:
    st.error("❌ 沒有 code=1 的主食資料")
    st.stop()

st.dataframe(meal[["name", "cf"]])

# ---------- cooking ----------
st.subheader("② 料理方式（水煮=1-2｜油炸=1-1）")
cook_cf_total = 0.0

for i, row in meal.iterrows():
    method = st.radio(
        f"{row['name']}",
        ["水煮", "油炸"],
        key=f"cook_{i}",
        horizontal=True,
    )

    pick_cf = 0.0
    pick_name = "無"

    if method == "水煮" and not water_df.empty:
        pick = water_df.sample(1).iloc[0]
        pick_cf = float(pick["cf"])
        pick_name = pick["name"]

    elif method == "油炸" and not oil_df.empty:
        pick = oil_df.sample(1).iloc[0]
        pick_cf = float(pick["cf"])
        pick_name = pick["name"]

    cook_cf_total += pick_cf
    st.caption(f"→ {pick_name}：{pick_cf:.3f} kgCO₂e")

# ---------- drink ----------
st.subheader("③ 飲料")
drink_cf = 0.0
if st.checkbox("我要飲料"):
    if not drink_df.empty:
        d = drink_df.sample(1).iloc[0]
        drink_cf = float(d["cf"])
        st.info(f"{d['name']}：{drink_cf:.3f} kgCO₂e")

# ---------- dessert ----------
st.subheader("④ 甜點（選 2）")
dessert_cf = 0.0
dessert_pick = st.multiselect(
    "甜點選擇",
    dessert_df["name"].tolist(),
    max_selections=2,
)
if dessert_pick:
    dessert_cf = dessert_df[dessert_df["name"].isin(dessert_pick)]["cf"].sum()

# ---------- transport ----------
st.subheader("⑤ 運輸（地圖＋延噸公里）")
transport_mode = st.radio("交通方式", ["走路", "汽車"], horizontal=True)

transport_cf = 0.0
formula = ""

m = folium.Map(location=[24.15, 120.67], zoom_start=13)
state = st_folium(m, height=300)

if transport_mode != "走路" and state.get("last_clicked"):
    distance_km = 12
    total_weight_ton = meal["weight"].sum() / 1000
    tkm = 2.71
    transport_cf = distance_km * total_weight_ton * tkm
    formula = f"{distance_km} × {total_weight_ton:.4f} × {tkm} = {transport_cf:.3f}"

# ---------- total ----------
food_cf = meal["cf"].sum()
total = food_cf + cook_cf_total + drink_cf + dessert_cf + transport_cf

st.subheader("✅ 總計")
st.markdown(f"""
- 主食：{food_cf:.3f}
- 料理：{cook_cf_total:.3f}
- 飲料：{drink_cf:.3f}
- 甜點：{dessert_cf:.3f}
- 運輸：{transport_cf:.3f}
- **總計：{total:.3f} kgCO₂e**
""")

if formula:
    st.caption("運輸公式：" + formula)

# ---------- charts ----------
chart_df = pd.DataFrame([
    {"項目": "主食", "kgCO2e": food_cf},
    {"項目": "料理", "kgCO2e": cook_cf_total},
    {"項目": "飲料", "kgCO2e": drink_cf},
    {"項目": "甜點", "kgCO2e": dessert_cf},
    {"項目": "運輸", "kgCO2e": transport_cf},
])

st.altair_chart(
    alt.Chart(chart_df).mark_bar().encode(x="項目", y="kgCO2e"),
    use_container_width=True,
)
st.altair_chart(
    alt.Chart(chart_df).mark_arc().encode(theta="kgCO2e", color="項目"),
    use_container_width=True,
)
