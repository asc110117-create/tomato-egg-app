
# tomato_egg_app_TRANSPORT_PKM_TKM_FULL.py
# -------------------------------------------------
# 教學重點版本（給老師用）
# ✔ 主食 → 水煮/煎炸 → 飲料 → 甜點 → 運輸
# ✔ 運輸可選：走路 / pkm / tkm
# ✔ tkm 會自動加總食材重量，並顯示計算公式
# ✔ 地圖只負責「算距離」
# -------------------------------------------------

import streamlit as st
import pandas as pd
import random
import math
from io import BytesIO

# ========== 基本設定 ==========
st.set_page_config(page_title="一餐的碳足跡大冒險", layout="centered")
st.title("🍽️ 一餐的碳足跡大冒險")

# ========== 範例資料（你之後可換成 Excel 讀取） ==========
food_data = pd.DataFrame([
    {"name": "白飯", "cf": 0.20, "weight": 0.25},
    {"name": "雞肉", "cf": 0.45, "weight": 0.30},
    {"name": "青菜", "cf": 0.10, "weight": 0.15},
])

oil = {"name": "食用油", "cf": 0.12}
water = {"name": "自來水", "cf": 0.01}

drink_data = pd.DataFrame([
    {"name": "紅茶", "cf": 0.18, "weight": 0.10},
    {"name": "豆漿", "cf": 0.22, "weight": 0.10},
])

dessert_data = pd.DataFrame([
    {"name": "蛋糕", "cf": 0.30, "weight": 0.12},
    {"name": "餅乾", "cf": 0.20, "weight": 0.08},
    {"name": "布丁", "cf": 0.25, "weight": 0.10},
])

# ========== 第一階段：主食 ==========
st.header("① 主食")
meal = food_data.sample(3, replace=False).reset_index(drop=True)
st.dataframe(meal[["name", "cf"]])

food_cf = meal["cf"].sum()
food_weight = meal["weight"].sum()

# ========== 料理方式 ==========
st.header("② 料理方式（水煮 / 煎炸）")
cook_cf = 0.0
for i, row in meal.iterrows():
    method = st.radio(
        f"{row['name']} 的料理方式",
        ["水煮", "煎炸"],
        key=f"cook_{i}"
    )
    if method == "水煮":
        cook_cf += water["cf"]
    else:
        cook_cf += oil["cf"]

# ========== 飲料 ==========
st.header("③ 飲料")
drink_choice = st.radio("是否選擇飲料？", ["不喝", "隨機一杯"])
drink_cf = 0.0
drink_weight = 0.0
if drink_choice == "隨機一杯":
    d = drink_data.sample(1).iloc[0]
    st.info(f"你選了：{d['name']}")
    drink_cf = d["cf"]
    drink_weight = d["weight"]

# ========== 甜點 ==========
st.header("④ 甜點（選 2）")
dessert_pick = st.multiselect(
    "請選 2 種甜點",
    dessert_data["name"].tolist()
)

dessert_cf = 0.0
dessert_weight = 0.0
if len(dessert_pick) == 2:
    sel = dessert_data[dessert_data["name"].isin(dessert_pick)]
    dessert_cf = sel["cf"].sum()
    dessert_weight = sel["weight"].sum()

# ========== 運輸 ==========
st.header("⑤ 運輸（最後才計算）")

distance = st.number_input("距離（km）", value=12.0)

transport_mode = st.radio(
    "你怎麼取得食材？",
    ["走路", "自己去買（pkm）", "貨車配送（tkm）"]
)

transport_cf = 0.0

if transport_mode == "走路":
    st.success("🚶‍♀️ 走路：不計算碳足跡")

elif transport_mode == "自己去買（pkm）":
    vehicle = st.radio("交通工具", ["機車", "汽車"])
    ef = 0.0951 if vehicle == "機車" else 0.115
    transport_cf = distance * ef
    st.code(f"碳足跡 = 距離 × pkm\n{distance} × {ef} = {transport_cf:.3f} kgCO₂e")

else:
    tkm_ef = 2.71
    total_weight_kg = food_weight + drink_weight + dessert_weight
    total_weight_ton = total_weight_kg / 1000

    transport_cf = distance * total_weight_ton * tkm_ef

    st.markdown("**📦 食材總重量計算**")
    st.write(f"{total_weight_kg:.2f} kg = {total_weight_ton:.4f} 噸")

    st.code(
        f"碳足跡 = 距離 × 貨物重量(噸) × tkm 係數\n"
        f"{distance} × {total_weight_ton:.4f} × {tkm_ef} = {transport_cf:.3f} kgCO₂e"
    )

# ========== 總計 ==========
total = food_cf + cook_cf + drink_cf + dessert_cf + transport_cf

st.header("✅ 總碳足跡")
st.metric("總計 (kgCO₂e)", f"{total:.3f}")
