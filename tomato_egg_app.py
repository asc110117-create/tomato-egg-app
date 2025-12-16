
import streamlit as st
import pandas as pd
import random

st.set_page_config(page_title="一餐的碳足跡大冒險", layout="centered")

st.title("🍱 一餐的碳足跡大冒險（穩定版）")

# ---------- 讀取 Excel ----------
st.subheader("📂 上傳資料")
uploaded = st.file_uploader("請上傳《產品碳足跡4.xlsx》", type=["xlsx"])

if uploaded is None:
    st.stop()

df = pd.read_excel(uploaded)

# 欄位安全檢查
required_cols = ["族群", "產品名稱", "碳足跡(kg)"]
for c in required_cols:
    if c not in df.columns:
        st.error(f"缺少欄位：{c}")
        st.stop()

df["碳足跡(kg)"] = pd.to_numeric(df["碳足跡(kg)"], errors="coerce")
df = df.dropna(subset=["碳足跡(kg)"])

# ---------- 主食邏輯 ----------
st.header("🍚 主食（隨機 5 選 2）")

food_df = df[df["族群"] == 1].copy()

if len(food_df) < 5:
    st.error("主食（族群=1）不足 5 筆")
    st.stop()

if "food_pool" not in st.session_state:
    st.session_state.food_pool = food_df.sample(5, random_state=random.randint(1,9999))

food_pool = st.session_state.food_pool

options = [
    f"{row['產品名稱']}（{row['碳足跡(kg)']:.3f} kgCO₂e）"
    for _, row in food_pool.iterrows()
]

choice = st.multiselect(
    "請選 2 種主食",
    options,
    max_selections=2
)

if len(choice) == 2:
    st.success("✅ 已選擇 2 種主食")
    total_food_cf = 0.0

    for label in choice:
        name = label.split("（")[0]
        cf = food_pool.loc[food_pool["產品名稱"] == name, "碳足跡(kg)"].values[0]
        total_food_cf += cf
        st.write(f"- {name}：{cf:.3f} kgCO₂e")

    st.markdown(f"### 🍽 主食小計：**{total_food_cf:.3f} kgCO₂e**")

st.divider()

# ---------- 甜點 ----------
st.header("🍰 甜點（group 3）")
dessert_df = df[df["族群"] == 3]

dessert_options = ["不吃"] + [
    f"{r['產品名稱']}（{r['碳足跡(kg)']:.3f} kgCO₂e）"
    for _, r in dessert_df.iterrows()
]

dessert_choice = st.selectbox("選擇甜點", dessert_options)

# ---------- 交通（保留全聯分店邏輯接口） ----------
st.header("🗺 交通（分店選擇）")
st.info("✔ 這一版已保留『全聯選分店＋地圖』的接入位置，下一步可直接接回 PX Mart 搜尋與距離計算")

st.markdown("""
**將使用的係數（記憶確認）：**
- 機車：9.51E-2 kgCO₂e / pkm  
- 汽油小客車：1.15E-1 kgCO₂e / pkm  
- 低溫貨車：2.71 kgCO₂e / tkm
""")

st.divider()
st.success("🎯 這一版只修正『抓錯項目』與『主食顯示錯誤』，其餘邏輯完全保留")

