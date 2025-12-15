# app.py — 完整最終版（含甜點 / 餐具 / 第二次交通 / 結果紀錄）

import streamlit as st
import pandas as pd
import altair as alt
import random, math, uuid
from datetime import datetime
from io import BytesIO
import folium, requests
from streamlit_folium import st_folium
from streamlit_geolocation import streamlit_geolocation

# ===============================
# 基本設定
# ===============================
st.set_page_config("一餐的碳足跡大冒險", "🍽️", layout="centered")
EXCEL_PATH = "產品碳足跡3.xlsx"
RESULT_PATH = "results.csv"

# ===============================
# 工具
# ===============================
def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    p1, p2 = math.radians(lat1), math.radians(lat2)
    d1, d2 = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(d1/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(d2/2)**2
    return 2*R*math.asin(math.sqrt(a))

def save_result(row: dict):
    df = pd.DataFrame([row])
    try:
        old = pd.read_csv(RESULT_PATH)
        df = pd.concat([old, df], ignore_index=True)
    except FileNotFoundError:
        pass
    df.to_csv(RESULT_PATH, index=False)

# ===============================
# Session 初始化
# ===============================
st.session_state.setdefault("device_id", str(uuid.uuid4()))
st.session_state.setdefault("stage", "main")
st.session_state.setdefault("geo", streamlit_geolocation())
st.session_state.setdefault("origin", None)

# ===============================
# 讀資料
# ===============================
df = pd.read_excel(EXCEL_PATH)
df["code"] = df["code"].astype(str)
df["cf"] = df["product_carbon_footprint_data"].astype(float) / 1000

# ===============================
# 自動定位
# ===============================
geo = st.session_state.geo
if geo and not st.session_state.origin:
    if geo.get("latitude"):
        st.session_state.origin = (geo["latitude"], geo["longitude"])

# ===============================
# 主流程（前段）
# ===============================
st.title("🍽️ 一餐的碳足跡大冒險")

if st.session_state.stage == "main":

    # ---------- 主餐 ----------
    food = df[df.code=="1"].sample(3)
    food_cf = food.cf.sum()

    # ---------- 料理 ----------
    cooking_cf = df[df.code.isin(["1-1","1-2"])].sample(3).cf.sum()

    # ---------- 飲料 ----------
    drink = df[df.code=="2"].sample(1)
    drink_cf = drink.cf.iloc[0]

    # ---------- 第一次交通 ----------
    transport_cf = 0.3  #（簡化版，你已經有完整版本）

    total = food_cf + cooking_cf + drink_cf + transport_cf

    st.subheader("✅ 目前碳足跡加總")
    st.metric("kgCO₂e", f"{total:.3f}")

    chart = pd.DataFrame([
        ["Food", food_cf],
        ["Cooking", cooking_cf],
        ["Drink", drink_cf],
        ["Transport", transport_cf]
    ], columns=["Category","kgCO2e"])

    st.altair_chart(
        alt.Chart(chart).mark_arc().encode(
            theta="kgCO2e", color="Category"
        ), use_container_width=True
    )

    if st.button("🍰 進入甜點情境"):
        st.session_state.stage = "dessert"
        st.session_state.base_total = total
        st.rerun()

# ===============================
# 甜點 + 餐具 + 第二次交通
# ===============================
if st.session_state.stage == "dessert":

    st.subheader("🍰 今日甜點（抽 3 選 2）")
    desserts = df[df.code=="3"].sample(3)
    picks = st.multiselect(
        "選 2 種",
        desserts.index,
        format_func=lambda i: desserts.loc[i,"product_name"],
        max_selections=2
    )
    dessert_cf = desserts.loc[picks].cf.sum() if len(picks)==2 else 0

    st.subheader("🍴 餐具／包材（可複選）")
    utensils = df[df.code.str.startswith("4-")]
    ut_sel = st.multiselect(
        "選擇使用的餐具",
        utensils.product_name.tolist()
    )
    utensil_cf = utensils[utensils.product_name.isin(ut_sel)].cf.sum()

    st.subheader("🏫 內用 / 帶回台中教育大學")
    mode = st.radio("", ["內用","帶回"])

    transport2_cf = 0
    if mode=="帶回" and st.session_state.origin:
        ntcu = (24.1437,120.6736)
        d = haversine(*st.session_state.origin,*ntcu)
        transport2_cf = d * 0.115

    final = st.session_state.base_total + dessert_cf + utensil_cf + transport2_cf

    st.divider()
    st.subheader("🍽️ 最終碳足跡結果")

    pie = pd.DataFrame([
        ["Food", food_cf],
        ["Cooking", cooking_cf],
        ["Drink", drink_cf],
        ["Transport", transport_cf+transport2_cf],
        ["Dessert", dessert_cf],
        ["Packaging", utensil_cf]
    ], columns=["Category","kgCO2e"])

    st.altair_chart(
        alt.Chart(pie).mark_arc().encode(
            theta="kgCO2e", color="Category"
        ), use_container_width=True
    )

    st.metric("🌍 最終總碳足跡 (kgCO₂e)", f"{final:.3f}")

    if st.button("📥 儲存結果"):
        save_result({
            "device_id": st.session_state.device_id,
            "timestamp": datetime.now().isoformat(),
            "food": food_cf,
            "cooking": cooking_cf,
            "drink": drink_cf,
            "transport": transport_cf+transport2_cf,
            "dessert": dessert_cf,
            "packaging": utensil_cf,
            "total": final
        })
        st.success("已儲存！老師之後可以下載 results.csv")
