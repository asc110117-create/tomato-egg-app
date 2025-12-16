
# tomato_egg_app_MAIN_DISH_FIXED_LABEL.py
# 修正：主食下拉顯示錯誤（顯示 index 而非產品名稱）
# Excel 欄位需為：族群、產品名稱、碳足跡(kg)

import streamlit as st
import pandas as pd
import random

st.set_page_config(page_title="主食 5 選 2（修正版）", layout="centered")
st.title("🍚 主食（隨機 5 選 2）")

# --- 讀檔（支援上傳，避免 FileNotFoundError）
uploaded = st.file_uploader("請上傳《碳足跡4.xlsx》", type=["xlsx"])
if uploaded is None:
    st.info("請先上傳 Excel 檔案")
    st.stop()

df = pd.read_excel(uploaded)

# --- 欄位檢查
required_cols = ["族群", "產品名稱", "碳足跡(kg)"]
missing = [c for c in required_cols if c not in df.columns]
if missing:
    st.error(f"缺少必要欄位：{missing}")
    st.stop()

# --- 主食（族群 = 1）
df_food = df[df["族群"] == 1].copy()
if len(df_food) < 2:
    st.error("主食資料不足（族群=1 至少要有 2 筆）")
    st.stop()

# 隨機抽 5 筆
sample_n = min(5, len(df_food))
df_sample = df_food.sample(n=sample_n, replace=False, random_state=random.randint(1, 9999)).reset_index(drop=True)

# 建立顯示 label（關鍵修正點）
df_sample["label"] = (
    df_sample["產品名稱"].astype(str)
    + "（"
    + df_sample["碳足跡(kg)"].astype(float).round(3).astype(str)
    + " kgCO₂e）"
)

# --- 選 2 種
choices = st.multiselect(
    "請選 2 種主食",
    options=df_sample["label"].tolist(),
    max_selections=2
)

if len(choices) == 2:
    st.subheader("你選擇的主食：")
    selected = df_sample[df_sample["label"].isin(choices)]
    for _, r in selected.iterrows():
        st.write(f"- {r['產品名稱']}（{float(r['碳足跡(kg)']):.3f} kgCO₂e）")
else:
    st.warning("請選擇 2 種主食")
