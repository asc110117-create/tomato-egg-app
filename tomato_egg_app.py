# tomato_egg_app.py
# 一餐的碳足跡大冒險（教學穩定版）

import streamlit as st
import pandas as pd
import random
import math
from io import BytesIO
from datetime import datetime
import folium
from streamlit_folium import st_folium

# =====================
# 基本設定
# =====================
st.set_page_config(page_title="一餐的碳足跡大冒險", layout="centered")
st.title("🍚 一餐的碳足跡大冒險")

# =====================
# 工具函式
# =====================
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

# =====================
# 讀取 Excel
# =====================
st.subheader("📂 上傳《碳足跡4.xlsx》")
uploaded = st.file_uploader("Excel 欄位需為：族群｜產品名稱｜碳足跡(kg)", type="xlsx")

if uploaded is None:
    st.stop()

df = pd.read_excel(uploaded)
df.columns = ["group", "name", "cf_kg"]
df["cf_kg"] = df["cf_kg"].astype(float)

# 分組
g1 = df[df["group"] == 1]
g1_oil = df[df["group"] == "1-1"]
g1_water = df[df["group"] == "1-2"]
g2 = df[df["group"] == 2]
g3 = df[df["group"] == 3]

# =====================
# 使用者資訊
# =====================
st.subheader("👤 使用者資訊")
student = st.text_input("請輸入姓名")
if student:
    st.info("這是你第 1 次測試")

# =====================
# 主食（5 選 2）
# =====================
st.subheader("🍱 主食（隨機 5 選 2）")

pool = g1.sample(min(5, len(g1)), random_state=42)
options = {
    f"{r.name} ({r.cf_kg:.2f} kgCO₂e)": r
    for _, r in pool.iterrows()
}

selected_labels = st.multiselect(
    "請選 2 種主食",
    list(options.keys()),
    max_selections=2,
)

if len(selected_labels) != 2:
    st.stop()

selected_foods = [options[l] for l in selected_labels]

# =====================
# 料理方式
# =====================
st.subheader("🍳 料理方式")

cook_results = []
total_food_weight = 0

for food in selected_foods:
    st.markdown(f"**{food.name}（{food.cf_kg:.2f} kgCO₂e）**")
    method = st.radio(
        "料理方式",
        ["水煮", "油炸"],
        key=food.name,
        horizontal=True,
    )

    if method == "水煮":
        water = g1_water.sample(1).iloc[0]
        cook_results.append((food, method, water))
    else:
        oil = g1_oil.sample(1).iloc[0]
        cook_results.append((food, method, oil))

    total_food_weight += food.cf_kg

# =====================
# 飲料
# =====================
st.subheader("🥤 飲料（group2）")
drink_opt = ["不喝"] + [
    f"{r.name} ({r.cf_kg:.2f} kgCO₂e)" for _, r in g2.iterrows()
]
drink_choice = st.selectbox("選擇飲料", drink_opt)
drink_cf = 0
if drink_choice != "不喝":
    drink_cf = float(drink_choice.split("(")[-1].replace(" kgCO₂e)", ""))

# =====================
# 甜點
# =====================
st.subheader("🍰 甜點（group3）")
dessert_opt = ["不吃"] + [
    f"{r.name} ({r.cf_kg:.2f} kgCO₂e)" for _, r in g3.iterrows()
]
dessert_choice = st.selectbox("選擇甜點", dessert_opt)
dessert_cf = 0
if dessert_choice != "不吃":
    dessert_cf = float(dessert_choice.split("(")[-1].replace(" kgCO₂e)", ""))

# =====================
# 交通（地圖）
# =====================
st.subheader("🚲 交通與距離")

transport = st.selectbox(
    "交通方式",
    [
        "機車（0.0951 kgCO₂e / pkm）",
        "自用小客車（0.115 kgCO₂e / pkm）",
        "低溫貨車（2.71 kgCO₂e / tkm）",
    ],
)

origin = st.text_input("你的出發座標（lat,lng）", "24.1477,120.6736")
store = st.text_input("分店座標（lat,lng）", "24.1600,120.6500")

olat, olng = map(float, origin.split(","))
slat, slng = map(float, store.split(","))

dist = haversine(olat, olng, slat, slng) * 2

if "機車" in transport:
    transport_cf = dist * 0.0951
    formula = f"{dist:.2f} km × 0.0951"
elif "自用" in transport:
    transport_cf = dist * 0.115
    formula = f"{dist:.2f} km × 0.115"
else:
    weight_ton = total_food_weight / 1000
    transport_cf = dist * weight_ton * 2.71
    formula = f"{dist:.2f} km × {weight_ton:.3f} 噸 × 2.71"

st.info(f"來回距離：{dist:.2f} km")
st.code(f"碳足跡 = {formula} = {transport_cf:.3f} kgCO₂e")

# =====================
# 總計
# =====================
total_cf = (
    sum(f.cf_kg for f, _, _ in cook_results)
    + sum(c.cf_kg for _, _, c in cook_results)
    + drink_cf
    + dessert_cf
    + transport_cf
)

st.success(f"🌍 本餐總碳足跡：{total_cf:.3f} kgCO₂e")

# =====================
# CSV 下載
# =====================
result = {
    "姓名": student,
    "主食": ", ".join([f.name for f, _, _ in cook_results]),
    "總重量(kg)": round(total_food_weight, 3),
    "交通距離(km)": round(dist, 2),
    "總碳足跡(kgCO2e)": round(total_cf, 3),
    "時間": datetime.now().strftime("%Y-%m-%d %H:%M"),
}

df_out = pd.DataFrame([result])
st.download_button(
    "⬇️ 下載結果 CSV",
    df_out.to_csv(index=False).encode("utf-8-sig"),
    file_name=f"{student}_carbon_meal.csv",
)
