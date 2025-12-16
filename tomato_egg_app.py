
# tomato_egg_app_FINAL_ALL.py
# 一餐的碳足跡大冒險（完整版）
# Excel 欄位固定三欄：族群、產品名稱、碳足跡(kg)

import math
import random
from datetime import datetime
from io import BytesIO

import pandas as pd
import streamlit as st
import altair as alt
import folium
from streamlit_folium import st_folium
import requests

# =========================
# 基本設定
# =========================
st.set_page_config(page_title="一餐的碳足跡大冒險", page_icon="🍽️", layout="centered")

st.title("🍽️ 一餐的碳足跡大冒險")

EXCEL_NAME = "碳足跡4.xlsx"

# =========================
# 載入資料（不在 cache 裡放 widget）
# =========================
def load_excel():
    try:
        return pd.read_excel(EXCEL_NAME)
    except FileNotFoundError:
        up = st.file_uploader("請上傳《碳足跡4.xlsx》", type=["xlsx"])
        if up is None:
            st.stop()
        return pd.read_excel(up)

df = load_excel()
df.columns = ["group", "name", "cf_kg"]
df["cf_kg"] = df["cf_kg"].astype(float)

# 群組
food_df = df[df["group"] == 1]
water_df = df[df["group"] == "1-1"]
oil_df = df[df["group"] == "1-2"]
drink_df = df[df["group"] == 2]
dessert_df = df[df["group"] == 3]

# =========================
# 使用者與測驗次數
# =========================
st.subheader("👤 使用者資訊")
student = st.text_input("請輸入姓名")
if not student:
    st.stop()

if "round" not in st.session_state:
    st.session_state.round = 1
else:
    st.session_state.round += 0

st.info(f"📘 這是 **第 {st.session_state.round} 次測試**")

# =========================
# 主食：5 選 2
# =========================
st.subheader("🍚 主食選擇（5 選 2）")

if "food_pool" not in st.session_state:
    st.session_state.food_pool = food_df.sample(n=min(5, len(food_df)))

options = [
    f"{r['name']}（{r['cf_kg']} kgCO₂e）"
    for _, r in st.session_state.food_pool.iterrows()
]

chosen = st.multiselect("請選 2 種主食", options, max_selections=2)

selected_foods = []
food_cf = 0.0

for opt in chosen:
    name = opt.split("（")[0]
    row = st.session_state.food_pool[st.session_state.food_pool["name"] == name].iloc[0]
    food_cf += row["cf_kg"]

    method = st.radio(
        f"{name} 的料理方式",
        ["水煮", "油炸"],
        horizontal=True,
        key=name
    )

    if method == "水煮":
        pick = water_df.sample(1).iloc[0]
    else:
        pick = oil_df.sample(1).iloc[0]

    st.caption(f"→ 使用 {pick['name']}（{pick['cf_kg']} kgCO₂e）")
    food_cf += pick["cf_kg"]

# =========================
# 飲料
# =========================
st.subheader("🥤 飲料")

drink_opt = st.selectbox(
    "選擇飲料",
    ["不喝飲料"] + [
        f"{r['name']}（{r['cf_kg']} kgCO₂e）"
        for _, r in drink_df.iterrows()
    ]
)

drink_cf = 0.0
if drink_opt != "不喝飲料":
    drink_cf = float(drink_opt.split("（")[1].replace(" kgCO₂e）", ""))

# =========================
# 甜點
# =========================
st.subheader("🍰 甜點")

dessert_opt = st.selectbox(
    "選擇甜點",
    ["不吃甜點"] + [
        f"{r['name']}（{r['cf_kg']} kgCO₂e）"
        for _, r in dessert_df.iterrows()
    ]
)

dessert_cf = 0.0
if dessert_opt != "不吃甜點":
    dessert_cf = float(dessert_opt.split("（")[1].replace(" kgCO₂e）", ""))

# =========================
# 交通（地圖 + 延噸公里）
# =========================
st.subheader("🚚 交通（延噸公里）")

transport = st.radio(
    "交通方式",
    ["走路（0 kgCO₂e）", "機車（kg/噸公里）", "貨車（kg/噸公里）"]
)

origin = [24.1477, 120.6736]
m = folium.Map(location=origin, zoom_start=13)
folium.Marker(origin, tooltip="起點").add_to(m)

map_state = st_folium(m, height=300)

distance_km = st.number_input("距離（km）", min_value=0.0, value=1.0)
weight_ton = st.number_input("食材總重量（噸）", min_value=0.0, value=0.0008)

tkm = 0.0
if transport == "機車（kg/噸公里）":
    tkm = 2.71
elif transport == "貨車（kg/噸公里）":
    tkm = 1.2

transport_cf = distance_km * weight_ton * tkm

st.code(f"碳足跡 = {distance_km} × {weight_ton} × {tkm} = {transport_cf:.3f} kgCO₂e")

# =========================
# 總計與圖表
# =========================
total = food_cf + drink_cf + dessert_cf + transport_cf

st.subheader("📊 碳足跡總計")
st.success(f"總碳足跡：{total:.3f} kgCO₂e")

chart_df = pd.DataFrame([
    {"項目": "主食+料理", "kgCO₂e": food_cf},
    {"項目": "飲料", "kgCO₂e": drink_cf},
    {"項目": "甜點", "kgCO₂e": dessert_cf},
    {"項目": "交通", "kgCO₂e": transport_cf},
])

bar = alt.Chart(chart_df).mark_bar().encode(
    x="項目",
    y="kgCO₂e"
)

pie = alt.Chart(chart_df).mark_arc().encode(
    theta="kgCO₂e",
    color="項目"
)

st.altair_chart(bar, use_container_width=True)
st.altair_chart(pie, use_container_width=True)

# =========================
# 匯出 CSV
# =========================
row = {
    "student": student,
    "round": st.session_state.round,
    "food_cf": food_cf,
    "drink_cf": drink_cf,
    "dessert_cf": dessert_cf,
    "transport_cf": transport_cf,
    "total_cf": total,
    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
}

csv = pd.DataFrame([row]).to_csv(index=False).encode("utf-8-sig")
st.download_button("⬇️ 下載 CSV", csv, "carbon_result.csv", "text/csv")
