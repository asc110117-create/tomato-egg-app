
# tomato_egg_app_STEP_D_ALL.py
import streamlit as st
import pandas as pd
import random
import math
from io import BytesIO
from datetime import datetime

# ------------------ 基本設定 ------------------
st.set_page_config(page_title="一餐的碳足跡大冒險", layout="centered")
st.title("🍽️ 一餐的碳足跡大冒險")

# ------------------ 使用者資訊 ------------------
st.subheader("👤 使用者資訊")
student = st.text_input("請輸入姓名")

if "round_no" not in st.session_state:
    st.session_state.round_no = 1

if student:
    st.info(f"📘 這是你第 {st.session_state.round_no} 次測試")

# ------------------ 讀取 Excel ------------------
st.subheader("📂 上傳《碳足跡4.xlsx》")
uploaded = st.file_uploader("請上傳檔案", type=["xlsx"])

if uploaded is None:
    st.stop()

df = pd.read_excel(uploaded)
df.columns = ["group", "name", "cf_kg"]

# 分群
g1 = df[df["group"] == 1]
g11 = df[df["group"] == "1-1"]
g12 = df[df["group"] == "1-2"]
g2 = df[df["group"] == 2]
g3 = df[df["group"] == 3]

# ------------------ 主食（5 選 2） ------------------
st.subheader("🍚 主食（隨機 5 選 2）")
pool = g1.sample(min(5, len(g1)))
options = {f'{r.name}（{r.cf_kg} kgCO₂e）': r for _, r in pool.iterrows()}
chosen = st.multiselect("請選 2 種主食", list(options.keys()), max_selections=2)

main_total = 0
cook_total = 0
weight_total = 0

for label in chosen:
    r = options[label]
    main_total += r.cf_kg
    weight_total += 0.3  # 每份假設 0.3 kg

    method = st.radio(
        f"{r.name} 的料理方式",
        ["水煮", "油炸"],
        key=r.name
    )

    if method == "水煮":
        pick = g12.sample(1).iloc[0]
    else:
        pick = g11.sample(1).iloc[0]

    cook_total += pick.cf_kg
    st.caption(f"→ {method}：{pick.name}（{pick.cf_kg} kgCO₂e）")

# ------------------ 飲料 ------------------
st.subheader("🥤 飲料（group2）")
drink_options = ["不喝"] + [
    f"{r.name}（{r.cf_kg} kgCO₂e）" for _, r in g2.iterrows()
]
drink_choice = st.selectbox("選擇飲料", drink_options)

drink_cf = 0
if drink_choice != "不喝":
    drink_cf = float(drink_choice.split("（")[1].split()[0])

# ------------------ 甜點 ------------------
st.subheader("🍰 甜點（group3）")
dessert_options = [
    f"{r.name}（{r.cf_kg} kgCO₂e）" for _, r in g3.iterrows()
]
dessert_choice = st.selectbox("選擇甜點", ["不吃"] + dessert_options)

dessert_cf = 0
if dessert_choice != "不吃":
    dessert_cf = float(dessert_choice.split("（")[1].split()[0])

# ------------------ 交通 ------------------
st.subheader("🧭 交通")
distance = st.number_input("來回距離（km）", min_value=0.0, value=5.0)

mode = st.selectbox(
    "交通工具",
    [
        "走路（0）",
        "機車（0.0951 kgCO₂e / pkm）",
        "自用小客車（0.115 kgCO₂e / pkm）",
        "低溫貨車（2.71 kgCO₂e / tkm）"
    ]
)

transport_cf = 0
if "機車" in mode:
    transport_cf = distance * 0.0951
elif "小客車" in mode:
    transport_cf = distance * 0.115
elif "貨車" in mode:
    transport_cf = distance * (weight_total / 1000) * 2.71

# ------------------ 總計 ------------------
total = main_total + cook_total + drink_cf + dessert_cf + transport_cf

st.subheader("✅ 總碳足跡結果")
st.write({
    "主食": round(main_total, 3),
    "料理": round(cook_total, 3),
    "飲料": round(drink_cf, 3),
    "甜點": round(dessert_cf, 3),
    "交通": round(transport_cf, 3),
    "總計 (kgCO₂e)": round(total, 3)
})

# ------------------ CSV 下載 ------------------
row = {
    "student": student,
    "round": st.session_state.round_no,
    "food": main_total,
    "cook": cook_total,
    "drink": drink_cf,
    "dessert": dessert_cf,
    "transport": transport_cf,
    "total": total,
    "time": datetime.now().isoformat()
}

csv = pd.DataFrame([row]).to_csv(index=False).encode("utf-8-sig")

st.download_button(
    "⬇️ 下載結果 CSV",
    data=csv,
    file_name=f"{student}_carbon.csv",
    mime="text/csv"
)

st.session_state.round_no += 1
