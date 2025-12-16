import streamlit as st
import pandas as pd
import random
import math
from datetime import datetime

# ======================
# 基本設定
# ======================
st.set_page_config(page_title="一餐的碳足跡大冒險", page_icon="🍽️")
st.title("🍽️ 一餐的碳足跡大冒險")

# ======================
# 讀取 Excel
# ======================
@st.cache_data
def load_excel():
    df = pd.read_excel("碳足跡4.xlsx")
    df.columns = ["group", "name", "cf_kg"]
    df["cf_kg"] = df["cf_kg"].astype(float)
    return df

df = load_excel()

food_df = df[df["group"] == "1"]
oil_df = df[df["group"] == "1-1"]
water_df = df[df["group"] == "1-2"]
drink_df = df[df["group"] == "2"]
dessert_df = df[df["group"] == "3"]

# ======================
# 學生資料
# ======================
st.subheader("👤 學生資料")
student = st.text_input("請輸入你的名字")

if student:
    st.info("📘 本次視為第 1 次測試（示範版）")

# ======================
# 主食（可重新抽）
# ======================
st.subheader("🍚 主食（3 道）")

if "meal" not in st.session_state:
    st.session_state.meal = food_df.sample(
        n=min(3, len(food_df)), replace=False
    ).reset_index(drop=True)

if st.button("🔄 更換主食"):
    st.session_state.meal = food_df.sample(
        n=min(3, len(food_df)), replace=False
    ).reset_index(drop=True)

meal = st.session_state.meal
st.table(meal[["name", "cf_kg"]])

food_cf = meal["cf_kg"].sum()

# ======================
# 料理方式
# ======================
st.subheader("🍳 料理方式")

cook_cf = 0.0
for i, row in meal.iterrows():
    method = st.radio(
        f"{row['name']}",
        ["水煮", "油炸"],
        key=f"cook_{i}",
        horizontal=True
    )
    if method == "水煮" and not water_df.empty:
        cook_cf += water_df.iloc[0]["cf_kg"]
    if method == "油炸" and not oil_df.empty:
        cook_cf += oil_df.iloc[0]["cf_kg"]

# ======================
# 飲料
# ======================
st.subheader("🥤 飲料")

drink_opts = ["不喝"] + [
    f"{r['name']}（{r['cf_kg']} kgCO₂e）"
    for _, r in drink_df.iterrows()
]

drink_choice = st.selectbox("選擇飲料", drink_opts)

drink_cf = 0.0
if drink_choice != "不喝":
    drink_cf = drink_df.iloc[
        drink_opts.index(drink_choice) - 1
    ]["cf_kg"]

# ======================
# 甜點
# ======================
st.subheader("🍰 甜點（group3）")

dessert_opts = ["不吃"] + [
    f"{r['name']}（{r['cf_kg']} kgCO₂e）"
    for _, r in dessert_df.iterrows()
]

dessert_choice = st.selectbox("選擇甜點", dessert_opts)

dessert_cf = 0.0
if dessert_choice != "不吃":
    dessert_cf = dessert_df.iloc[
        dessert_opts.index(dessert_choice) - 1
    ]["cf_kg"]

# ======================
# 交通（延噸公里）
# ======================
st.subheader("🚚 交通")

transport = st.radio(
    "交通方式",
    ["走路（0）", "機車", "貨車"],
    horizontal=True
)

distance = st.number_input("距離（km）", min_value=0.0, value=1.0)

# 食材總重量（假設每項 0.2 kg）
total_weight_kg = len(meal) * 0.2
total_weight_ton = total_weight_kg / 1000

transport_cf = 0.0
formula = "走路不計算"

if transport == "機車":
    transport_cf = distance * total_weight_ton * 1.5
    formula = f"{distance} × {total_weight_ton:.4f} × 1.5"
elif transport == "貨車":
    transport_cf = distance * total_weight_ton * 2.71
    formula = f"{distance} × {total_weight_ton:.4f} × 2.71"

st.caption(f"📐 計算式：{formula}")

# ======================
# 總計
# ======================
total = food_cf + cook_cf + drink_cf + dessert_cf + transport_cf

st.subheader("✅ 總碳足跡")
st.metric("總計（kgCO₂e）", f"{total:.3f}")

# ======================
# CSV 下載
# ======================
row = {
    "student": student,
    "food": food_cf,
    "cooking": cook_cf,
    "drink": drink_cf,
    "dessert": dessert_cf,
    "transport": transport_cf,
    "total": total,
    "time": datetime.now().isoformat()
}

csv = pd.DataFrame([row]).to_csv(index=False).encode("utf-8-sig")

st.download_button(
    "⬇️ 下載個人 CSV",
    csv,
    file_name=f"{student}_carbon.csv",
    mime="text/csv"
)
