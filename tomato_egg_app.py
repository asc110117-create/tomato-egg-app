
# tomato_egg_app_AB_only_FIXED_GROUP1.py
# 修正重點：group1 主食不足 2 筆時不當機
# 僅修 A / B，避免亂改原邏輯

import streamlit as st
import pandas as pd

st.set_page_config(page_title="一餐的碳足跡計算器（AB修正版）", layout="centered")
st.title("🍽️ 一餐的碳足跡計算器（AB修正版）")

uploaded = st.file_uploader("請上傳 Excel（需有：族群、產品名稱、碳足跡(kg)）", type=["xlsx"])
if uploaded is None:
    st.stop()

df = pd.read_excel(uploaded)

required = ["族群", "產品名稱", "碳足跡(kg)"]
for c in required:
    if c not in df.columns:
        st.error(f"❌ 缺少欄位：{c}")
        st.stop()

# === A. 主食 ===
st.header("🥦 主食（隨機 5 選 2）")

g1 = df[df["族群"] == 1].copy()
if len(g1) < 2:
    st.error("❌ group1 主食不足 2 筆，請補資料")
    st.stop()

sample_n = min(5, len(g1))
candidates = g1.sample(n=sample_n, random_state=42)

label_map = {}
for _, r in candidates.iterrows():
    label = f"{r['產品名稱']} ({r['碳足跡(kg)']} kgCO₂e)"
    label_map[label] = r["碳足跡(kg)"]

selected = st.multiselect("請選 2 種主食", list(label_map.keys()), max_selections=2)

if len(selected) == 2:
    total = sum(label_map[x] for x in selected)
    st.success(f"主食碳足跡小計：{total:.2f} kgCO₂e")

# === B. 交通（結構保留） ===
st.header("🚶 交通")
st.selectbox("交通方式", ["走路", "機車", "汽車", "貨車"])
st.caption("此檔僅修正主食錯誤，未動其他模組")
