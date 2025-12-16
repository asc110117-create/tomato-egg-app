
import streamlit as st
import pandas as pd
import random
from io import BytesIO

st.set_page_config(page_title="一餐的碳足跡大冒險", layout="centered")
st.title("🍚 主食（隨機 5 選 2）")

# ---------- 讀取 Excel ----------
uploaded = st.file_uploader("請上傳《碳足跡4.xlsx》", type=["xlsx"])

if uploaded is None:
    st.info("請先上傳 Excel 檔案")
    st.stop()

df = pd.read_excel(uploaded)

# 欄位檢查
required_cols = ["族群", "產品名稱", "碳足跡(kg)"]
missing = [c for c in required_cols if c not in df.columns]
if missing:
    st.error(f"缺少欄位：{missing}")
    st.stop()

# 數值轉型
df["碳足跡(kg)"] = pd.to_numeric(df["碳足跡(kg)"], errors="coerce")
df = df.dropna(subset=["碳足跡(kg)"])

# ---------- 主食 group1 ----------
food_df = df[df["族群"] == 1].copy()

if len(food_df) == 0:
    st.error("❌ Excel 中找不到族群 = 1 的主食資料")
    st.stop()

# 隨機抽 5（只在第一次）
if "food_pool" not in st.session_state:
    food_pool = food_df.sample(min(5, len(food_df)), random_state=random.randint(1, 9999))
    st.session_state.food_pool = food_pool
else:
    food_pool = st.session_state.food_pool

# 建立選項文字
options = [
    f"{row['產品名稱']}（{row['碳足跡(kg)']} kgCO₂e）"
    for _, row in food_pool.iterrows()
]

st.subheader("請選 2 種主食")

selected = st.multiselect(
    "主食選擇",
    options=options,
    max_selections=2
)

# ---------- 顯示結果 ----------
if len(selected) == 2:
    st.success("✅ 已選擇主食：")
    total_cf = 0.0
    for text in selected:
        name = text.split("（")[0]
        cf = food_pool.loc[food_pool["產品名稱"] == name, "碳足跡(kg)"].values[0]
        total_cf += cf
        st.write(f"- {name}：{cf} kgCO₂e")

    st.markdown(f"### 🍽 主食小計：**{total_cf:.3f} kgCO₂e**")
else:
    st.info("請選滿 2 種主食")
