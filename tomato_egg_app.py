
# carbon_meal_app_COMPLETE_SAFE.py
# 修正 sample(n=3) 當資料不足時不炸掉

import streamlit as st
import pandas as pd
import random
import math
import altair as alt
import folium
from streamlit_folium import st_folium
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="一餐的碳足跡（FINAL SAFE）", layout="centered")
st.title("🍱 一餐的碳足跡（FINAL SAFE）")

@st.cache_data
def load_data():
    df = pd.read_excel("產品碳足跡3.xlsx")
    df = df.iloc[:, :5]
    cols = ["code", "name", "cf", "unit", "weight"][: len(df.columns)]
    df.columns = cols
    if "weight" not in df.columns:
        df["weight"] = 0.0
    df["code"] = df["code"].astype(str)
    return df

df = load_data()

food_df = df[df["code"] == "1"]
oil_df = df[df["code"] == "1-1"]
water_df = df[df["code"] == "1-2"]
drink_df = df[df["code"] == "2"]
dessert_df = df[df["code"] == "3"]

st.subheader("👩‍🎓 學生資訊")
student_name = st.text_input("姓名（必填）")
round_tag = st.radio("測驗次數", ["第一次測試", "第二次測試"], horizontal=True)

st.subheader("① 主食")

def safe_sample(df, n):
    if len(df) == 0:
        return df
    return df.sample(n=min(n, len(df)), replace=False).reset_index(drop=True)

meal = safe_sample(food_df, 3)

if meal.empty:
    st.error("❌ Excel 裡沒有 code=1 的主食資料")
    st.stop()

st.dataframe(meal[["name", "cf"]])

st.subheader("② 料理方式（1-1 油 / 1-2 水）")
cook_cf_total = 0.0

for i, row in meal.iterrows():
    method = st.radio(
        f"{row['name']} 的料理方式",
        ["水煮", "油炸"],
        key=f"cook_{i}",
        horizontal=True,
    )
    if method == "水煮" and not water_df.empty:
        pick = water_df.sample(1).iloc[0]
    elif method == "油炸" and not oil_df.empty:
        pick = oil_df.sample(1).iloc[0]
    else:
        pick = None

    if pick is not None:
        cook_cf_total += float(pick["cf"])
        st.caption(f"→ 使用 {pick['name']}：{pick['cf']} kgCO₂e")

st.subheader("③ 飲料")
drink_cf = 0.0
if st.checkbox("我要飲料"):
    if drink_df.empty:
        st.warning("沒有飲料資料")
    else:
        d = drink_df.sample(1).iloc[0]
        drink_cf = float(d["cf"])
        st.info(f"{d['name']}：{drink_cf} kgCO₂e")

st.subheader("④ 甜點（選 2）")
dessert_cf = 0.0
dessert_pick = st.multiselect(
    "甜點選擇",
    dessert_df["name"].tolist(),
    max_selections=2,
)
if dessert_pick:
    dessert_cf = dessert_df[dessert_df["name"].isin(dessert_pick)]["cf"].sum()

st.subheader("⑤ 運輸（延噸公里）")
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
