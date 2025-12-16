
# tomato_egg_app_main_dish_stable.py
# 穩定版主食邏輯（隨機 5 選 2，不跳回）

import random
import pandas as pd
import streamlit as st

st.set_page_config(page_title="一餐的碳足跡大冒險", layout="centered")

st.title("🍱 一餐的碳足跡大冒險（主食穩定版）")

# =========================
# 1. 讀取 Excel（不上 cache，避免 widget 問題）
# =========================
uploaded = st.file_uploader("請上傳《產品碳足跡4.xlsx》", type=["xlsx"])

if uploaded is None:
    st.info("請先上傳 Excel 檔案")
    st.stop()

df = pd.read_excel(uploaded)

# 欄位檢查
required_cols = ["族群", "產品名稱", "碳足跡(kg)"]
missing = [c for c in required_cols if c not in df.columns]
if missing:
    st.error(f"Excel 缺少欄位：{missing}")
    st.stop()

df["碳足跡(kg)"] = pd.to_numeric(df["碳足跡(kg)"], errors="coerce")
df = df.dropna(subset=["碳足跡(kg)"])

# 只取 group1 作為主食
g1 = df[df["族群"] == 1].reset_index(drop=True)

if len(g1) < 2:
    st.error("group1 主食資料不足")
    st.stop()

# =========================
# 2. 隨機 5 筆（只做一次）
# =========================
if "main_dish_pool" not in st.session_state:
    st.session_state.main_dish_pool = (
        g1.sample(min(5, len(g1)), random_state=random.randint(1, 9999))
        .reset_index(drop=True)
    )

pool = st.session_state.main_dish_pool

st.subheader("🍚 主食（隨機 5 選 2）")

options = [
    f"{row['產品名稱']}（{row['碳足跡(kg)']:.2f} kgCO₂e）"
    for _, row in pool.iterrows()
]

selected = st.multiselect(
    "請選 2 種主食",
    options=options,
    max_selections=2,
    key="main_dish_select"
)

if len(selected) != 2:
    st.info("請選擇 2 種主食")
    st.stop()

# =========================
# 3. 顯示選擇結果
# =========================
st.markdown("### ✅ 您選擇的主食：")

total_cf = 0.0
for label in selected:
    name = label.split("（")[0]
    row = pool[pool["產品名稱"] == name].iloc[0]
    cf = row["碳足跡(kg)"]
    total_cf += cf
    st.write(f"- {name}（{cf:.2f} kgCO₂e）")

st.success(f"🍽 主食碳足跡小計：{total_cf:.2f} kgCO₂e")
