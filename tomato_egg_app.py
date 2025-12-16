
# tomato_egg_app_AB_only.py
# 完整可執行版本（僅加入 A + B）
# A：交通碳足跡納入總計
# B：走路選項（0 排放）

import math
import pandas as pd
import streamlit as st

st.set_page_config(page_title="碳足跡計算（AB版）", layout="centered")

st.title("🍽️ 一餐的碳足跡（AB 版）")

# =========
# 讀取 Excel（嚴格依欄位）
# =========
st.subheader("📄 上傳 Excel")
uploaded = st.file_uploader("請上傳 Excel（欄位：族群、產品名稱、碳足跡(kg)）", type=["xlsx"])

if uploaded is None:
    st.stop()

df = pd.read_excel(uploaded)

required_cols = ["族群", "產品名稱", "碳足跡(kg)"]
for c in required_cols:
    if c not in df.columns:
        st.error(f"缺少必要欄位：{c}")
        st.stop()

df["碳足跡(kg)"] = pd.to_numeric(df["碳足跡(kg)"], errors="coerce").fillna(0.0)

# =========
# 主食（group1）
# =========
st.subheader("🍚 主食")
food_df = df[df["族群"] == "group1"]

if len(food_df) < 2:
    st.error("group1 主食不足 2 筆")
    st.stop()

options = [
    f"{r['產品名稱']} ({r['碳足跡(kg)']} kgCO₂e)"
    for _, r in food_df.iterrows()
]

selected = st.multiselect("請選 2 種主食", options, max_selections=2)

food_total = 0.0
for s in selected:
    name = s.split(" (")[0]
    food_total += float(food_df[food_df["產品名稱"] == name]["碳足跡(kg)"].iloc[0])

# =========
# 交通（A + B）
# =========
st.subheader("🚗 交通")

distance = st.number_input("來回距離（km）", min_value=0.0, value=5.0)

transport_mode = st.radio(
    "交通方式",
    [
        "走路（0 kgCO₂e / km）",
        "機車（0.0951 kgCO₂e / km）",
        "汽車（0.115 kgCO₂e / km）",
        "貨車（2.71 kgCO₂e / km）",
    ],
)

EF = {
    "走路（0 kgCO₂e / km）": 0.0,
    "機車（0.0951 kgCO₂e / km）": 0.0951,
    "汽車（0.115 kgCO₂e / km）": 0.115,
    "貨車（2.71 kgCO₂e / km）": 2.71,
}

transport_cf = distance * EF[transport_mode]

st.info(f"交通碳足跡：{transport_cf:.3f} kgCO₂e")

# =========
# A：納入總計
# =========
total = food_total + transport_cf

st.subheader("✅ 總計（含交通）")
st.metric("總碳足跡 (kgCO₂e)", f"{total:.3f}")

# =========
# 下載 CSV
# =========
result = pd.DataFrame([{
    "主食碳足跡(kg)": food_total,
    "交通方式": transport_mode,
    "距離(km)": distance,
    "交通碳足跡(kg)": transport_cf,
    "總碳足跡(kg)": total,
}])

st.download_button(
    "⬇️ 下載結果 CSV",
    data=result.to_csv(index=False).encode("utf-8-sig"),
    file_name="carbon_result_AB.csv",
    mime="text/csv",
)
