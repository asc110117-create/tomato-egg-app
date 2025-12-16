
# tomato_egg_app_v4_with_map.py
# 一餐的碳足跡大冒險（v4）
# 重點：穩定版 + 可選地圖（點選店家）+ 交通碳足跡（走路/機車/貨車-延噸公里）
# 資料來源：使用者上傳【碳足跡4.xlsx】

import streamlit as st
import pandas as pd
import math
from io import BytesIO
from datetime import datetime

import folium
from streamlit_folium import st_folium

# -----------------
# 基本設定
# -----------------
st.set_page_config(page_title="一餐的碳足跡大冒險 v4", layout="centered")
st.title("🍽️ 一餐的碳足跡大冒險（v4）")

# -----------------
# 工具函式
# -----------------
def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2-lat1)
    dl = math.radians(lon2-lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dl/2)**2
    return 2*R*math.asin(math.sqrt(a))

def load_excel(upload):
    df = pd.read_excel(upload)
    df.columns = ["group","name","cf"]
    df["cf"] = df["cf"].astype(float)
    return df

# -----------------
# 1️⃣ 基本資料
# -----------------
student = st.text_input("請輸入姓名")
if student:
    st.info(f"👤 學生：{student}（系統將自動記錄測驗次數）")

upload = st.file_uploader("上傳【碳足跡4.xlsx】", type=["xlsx"])
if not upload:
    st.stop()

df = load_excel(upload)

# -----------------
# 2️⃣ 主食（group 1）
# -----------------
st.header("🍱 主食（group 1）")

food_df = df[df["group"]==1]
meal = st.multiselect(
    "選擇主食（可選多項）",
    options=food_df["name"].tolist()
)

food_cf = food_df[food_df["name"].isin(meal)]["cf"].sum()

# -----------------
# 3️⃣ 飲料（group 2）
# -----------------
st.header("🥤 飲料（group 2）")

drink_df = df[df["group"]==2]
drink_options = ["不喝"] + [
    f"{r.name}（{r.cf} kgCO₂e）" for r in drink_df.itertuples()
]
drink_choice = st.selectbox("選擇飲料", drink_options)

drink_cf = 0.0
if drink_choice != "不喝":
    drink_name = drink_choice.split("（")[0]
    drink_cf = drink_df[drink_df["name"]==drink_name]["cf"].values[0]

# -----------------
# 4️⃣ 甜點（group 3）
# -----------------
st.header("🍰 甜點（group 3）")

dessert_df = df[df["group"]==3]
dessert_options = [
    f"{r.name}（{r.cf} kgCO₂e）" for r in dessert_df.itertuples()
]
dessert_choice = st.multiselect("選擇甜點（可複選）", dessert_options)

dessert_cf = 0.0
for d in dessert_choice:
    name = d.split("（")[0]
    dessert_cf += dessert_df[dessert_df["name"]==name]["cf"].values[0]

# -----------------
# 5️⃣ 地圖選擇商店（交通）
# -----------------
st.header("🗺️ 交通（地圖選點）")

origin_lat, origin_lng = 24.1477, 120.6736  # 台中教育大學
m = folium.Map(location=[origin_lat, origin_lng], zoom_start=14)
folium.Marker([origin_lat, origin_lng], tooltip="出發點").add_to(m)

map_data = st_folium(m, height=350, width=700)

distance = 0.0
if map_data and map_data.get("last_clicked"):
    dest_lat = map_data["last_clicked"]["lat"]
    dest_lng = map_data["last_clicked"]["lng"]
    distance = haversine(origin_lat, origin_lng, dest_lat, dest_lng)
    st.success(f"📏 估算距離：約 {distance:.2f} km")

transport_mode = st.selectbox(
    "交通工具",
    [
        "走路（0）",
        "機車（0.05 kgCO₂e/km）",
        "貨車（延噸公里）"
    ]
)

transport_cf = 0.0
formula = ""

if transport_mode.startswith("機車"):
    transport_cf = distance * 0.05
    formula = f"{distance:.2f} × 0.05"

elif transport_mode.startswith("貨車"):
    weight_kg = st.number_input("貨物重量（kg）", value=1.0)
    tkm = 2.71
    transport_cf = distance * (weight_kg/1000) * tkm
    formula = f"{distance:.2f} × {weight_kg/1000:.4f} × {tkm}"

# -----------------
# 6️⃣ 結果與下載
# -----------------
total = food_cf + drink_cf + dessert_cf + transport_cf

st.header("✅ 碳足跡結果")
st.write(f"🍱 主食：{food_cf:.2f} kgCO₂e")
st.write(f"🥤 飲料：{drink_cf:.2f} kgCO₂e")
st.write(f"🍰 甜點：{dessert_cf:.2f} kgCO₂e")
st.write(f"🚚 交通：{transport_cf:.2f} kgCO₂e")
if formula:
    st.caption(f"公式：{formula}")
st.success(f"🌍 總計：{total:.2f} kgCO₂e")

result = pd.DataFrame([{
    "student": student,
    "food": food_cf,
    "drink": drink_cf,
    "dessert": dessert_cf,
    "transport": transport_cf,
    "total": total,
    "time": datetime.now().isoformat()
}])

st.download_button(
    "⬇️ 下載 CSV",
    result.to_csv(index=False).encode("utf-8-sig"),
    file_name="carbon_result_v4.csv",
    mime="text/csv"
)
