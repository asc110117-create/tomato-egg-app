
import streamlit as st
import pandas as pd
import random
from io import BytesIO

st.set_page_config(page_title="一餐的碳足跡大冒險", layout="centered")

st.title("🍽️ 一餐的碳足跡大冒險（Excel 嚴格版）")

# ============================
# 1. 上傳 Excel（嚴格依欄位）
# ============================
uploaded = st.file_uploader("請上傳《碳足跡4.xlsx》", type=["xlsx"])

if uploaded is None:
    st.info("請先上傳 Excel 檔案")
    st.stop()

df = pd.read_excel(uploaded)

required_cols = ["族群", "產品名稱", "碳足跡(kg)"]
missing = [c for c in required_cols if c not in df.columns]

if missing:
    st.error(f"Excel 缺少必要欄位：{missing}")
    st.stop()

# ============================
# 2. 主食（group = 1）
# ============================
df_food = df[df["族群"] == 1].copy()

if len(df_food) < 2:
    st.error("主食（族群=1）資料不足")
    st.stop()

sample_5 = df_food.sample(min(5, len(df_food)), random_state=42)

options = {
    f"{row['產品名稱']}（{row['碳足跡(kg)']} kgCO₂e）": row
    for _, row in sample_5.iterrows()
}

st.subheader("🍚 主食（隨機 5 選 2）")

chosen = st.multiselect(
    "請選 2 種主食",
    options=list(options.keys()),
    max_selections=2
)

# ============================
# 3. 顯示選擇結果
# ============================
if len(chosen) == 2:
    st.success("你選擇的主食為：")
    total_food_cf = 0.0

    for name in chosen:
        row = options[name]
        cf = float(row["碳足跡(kg)"])
        total_food_cf += cf
        st.write(f"- {row['產品名稱']}（{cf} kgCO₂e）")

    st.markdown(f"### 主食碳足跡小計：**{total_food_cf:.3f} kgCO₂e**")
else:
    st.warning("請選擇 2 種主食")

