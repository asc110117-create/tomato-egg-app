
# tomato_egg_app_FINAL_STABLE.py
# 一餐的碳足跡大冒險（穩定版）
# -------------------------------------------------
# Excel 欄位需求（必須完全一致）：
#   族群 | 產品名稱 | 碳足跡(kg)
#
# 族群定義：
#   1   主食
#   1-1 水煮用水
#   1-2 油炸用油
#   2   飲料
#   3   甜點
#
# 交通係數（固定）：
#   機車                9.51E-2  kgCO2e / 人公里 (pkm)
#   自用小客車(汽油)    1.15E-1  kgCO2e / 人公里 (pkm)
#   3.49噸低溫貨車       2.71E+0  kgCO2e / 噸公里 (tkm)
#
# -------------------------------------------------

import math
import random
from io import BytesIO
from datetime import datetime

import pandas as pd
import streamlit as st

# =======================
# 基本設定
# =======================
st.set_page_config(page_title="一餐的碳足跡大冒險", page_icon="🍱", layout="centered")
st.title("🍱 一餐的碳足跡大冒險")

# =======================
# 工具函式
# =======================
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(a))

def require_columns(df):
    required = ["族群", "產品名稱", "碳足跡(kg)"]
    for c in required:
        if c not in df.columns:
            st.error(f"Excel 缺少欄位：{c}")
            st.stop()

# =======================
# 0. 使用者資訊
# =======================
student = st.text_input("請輸入你的名字")
if not student:
    st.stop()

# 本機測試次數（以 session 為準）
if "rounds" not in st.session_state:
    st.session_state.rounds = {}
round_no = st.session_state.rounds.get(student, 0) + 1
st.session_state.rounds[student] = round_no
st.info(f"📌 這是你第 {round_no} 次測試")

# =======================
# 1. 上傳 Excel
# =======================
uploaded = st.file_uploader("請上傳《碳足跡4.xlsx》", type=["xlsx"])
if uploaded is None:
    st.stop()

df = pd.read_excel(uploaded)
require_columns(df)
df["碳足跡(kg)"] = pd.to_numeric(df["碳足跡(kg)"], errors="coerce").fillna(0.0)

# 分群
df_main = df[df["族群"] == "1"]
df_water = df[df["族群"] == "1-1"]
df_oil   = df[df["族群"] == "1-2"]
df_drink = df[df["族群"] == "2"]
df_dessert = df[df["族群"] == "3"]

# =======================
# 2. 主食（隨機 5 選 2）
# =======================
st.header("🍚 主食（隨機 5 選 2）")

if "main_pool" not in st.session_state:
    st.session_state.main_pool = df_main.sample(min(5, len(df_main)), random_state=random.randint(1,9999))

options = [
    f"{r['產品名稱']} ({r['碳足跡(kg)']} kgCO₂e)"
    for _, r in st.session_state.main_pool.iterrows()
]

selected = st.multiselect("請選 2 種主食", options, max_selections=2)
if len(selected) != 2:
    st.stop()

chosen_rows = []
for s in selected:
    name = s.split(" (")[0]
    chosen_rows.append(st.session_state.main_pool[st.session_state.main_pool["產品名稱"] == name].iloc[0])

# =======================
# 3. 料理方式（水煮 / 油炸）
# =======================
st.header("🍳 料理方式")

cook_results = []
for r in chosen_rows:
    st.subheader(r["產品名稱"])
    method = st.radio(
        "選擇料理方式",
        ["水煮", "油炸"],
        key=f"cook_{r['產品名稱']}"
    )
    if method == "水煮":
        pick = df_water.sample(1).iloc[0]
    else:
        pick = df_oil.sample(1).iloc[0]

    st.caption(f"料理耗材：{pick['產品名稱']}（{pick['碳足跡(kg)']} kgCO₂e）")
    cook_results.append({
        "food": r,
        "method": method,
        "extra": pick
    })

# =======================
# 4. 飲料
# =======================
st.header("🥤 飲料")
drink_choice = st.selectbox(
    "選擇飲料",
    ["不喝"] + [
        f"{r['產品名稱']} ({r['碳足跡(kg)']} kgCO₂e)"
        for _, r in df_drink.iterrows()
    ]
)
drink_cf = 0.0
if drink_choice != "不喝":
    drink_name = drink_choice.split(" (")[0]
    drink_cf = float(df_drink[df_drink["產品名稱"] == drink_name]["碳足跡(kg)"].iloc[0])

# =======================
# 5. 甜點
# =======================
st.header("🍰 甜點")
dessert_choice = st.selectbox(
    "選擇甜點",
    ["不吃"] + [
        f"{r['產品名稱']} ({r['碳足跡(kg)']} kgCO₂e)"
        for _, r in df_dessert.iterrows()
    ]
)
dessert_cf = 0.0
if dessert_choice != "不吃":
    dname = dessert_choice.split(" (")[0]
    dessert_cf = float(df_dessert[df_dessert["產品名稱"] == dname]["碳足跡(kg)"].iloc[0])

# =======================
# 6. 交通
# =======================
st.header("🛵 交通")

mode = st.selectbox(
    "交通工具",
    [
        "機車 (0.0951 kgCO₂e / 人公里)",
        "自用小客車(汽油) (0.115 kgCO₂e / 人公里)",
        "3.49噸低溫貨車 (2.71 kgCO₂e / 噸公里)"
    ]
)

distance = st.number_input("來回距離（公里）", min_value=0.0, value=5.0)

# 總重量（主食 + 料理耗材）
total_weight_kg = sum(r["food"]["碳足跡(kg)"] for r in cook_results)

if "貨車" in mode:
    transport_cf = distance * (total_weight_kg/1000) * 2.71
else:
    factor = 0.0951 if "機車" in mode else 0.115
    transport_cf = distance * factor

# =======================
# 7. 總計
# =======================
food_cf = sum(r["food"]["碳足跡(kg)"] for r in cook_results)
cook_cf = sum(r["extra"]["碳足跡(kg)"] for r in cook_results)

total = food_cf + cook_cf + drink_cf + dessert_cf + transport_cf

st.success(f"🌍 本餐總碳足跡：{total:.3f} kgCO₂e")

# =======================
# 8. 匯出 CSV
# =======================
result = {
    "時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "姓名": student,
    "第幾次測試": round_no,
    "主食碳足跡": food_cf,
    "料理碳足跡": cook_cf,
    "飲料碳足跡": drink_cf,
    "甜點碳足跡": dessert_cf,
    "交通碳足跡": transport_cf,
    "總碳足跡": total
}

csv = pd.DataFrame([result]).to_csv(index=False).encode("utf-8-sig")
st.download_button("⬇️ 下載結果 CSV", csv, file_name=f"{student}_carbon.csv", mime="text/csv")
