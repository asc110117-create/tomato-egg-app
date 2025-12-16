import re
import random
import math
import uuid
from io import BytesIO
from datetime import datetime

import pandas as pd
import streamlit as st
import altair as alt
import requests
import folium
from streamlit_folium import st_folium

from streamlit_geolocation import streamlit_geolocation

# =========================
# 0) 基本設定
# =========================
st.set_page_config(
    page_title="一餐的碳足跡大冒險：從農場到你的胃",
    page_icon="🍽️",
    layout="centered",
)

# 你 repo 內的預設 Excel 檔名（在 repo 根目錄）
EXCEL_PATH_DEFAULT = "產品碳足跡3.xlsx"

# 報到名單（你可自行加）
VALID_IDS = {
    "BEE114105黃文瑜": {"name": "文瑜"},
    "BEE114108陳依萱": {"name": "依萱"},
}

# 台中教育大學（預設座標；你也可以改成你要的）
NTSU_LAT = 24.1477
NTSU_LNG = 120.6736

# =========================
# 1) CF 解析：統一成 gCO2e
# =========================
def parse_cf_to_g(value) -> float:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return float("nan")
    # 數字：預設當作「g」還是「kg」？
    if isinstance(value, (int, float)):
        v = float(value)
        if v <= 50:
            return v * 1000.0
        return v

    s = str(value).strip().lower()
    s = s.replace(" ", "")
    s = s.replace("kgco2e", "kg").replace("gco2e", "g")
    
    if re.fullmatch(r"[-+]?\d*\.?\d+k", s):
        kg = float(s[:-1])
        return kg * 1000.0

    m = re.match(r"([-+]?\d*\.?\d+)(kg|g)?$", s)
    if m:
        num = float(m.group(1))
        unit = m.group(2)
        if unit == "kg":
            return num * 1000.0
        if unit == "g":
            return num
        return num * 1000.0 if num <= 50 else num

    m2 = re.search(r"([-+]?\d*\.?\d+)\s*(kg|g)", s)
    if m2:
        num = float(m2.group(1))
        unit = m2.group(2)
        return num * 1000.0 if unit == "kg" else num

    m3 = re.search(r"([-+]?\d*\.?\d+)", s)
    if m3:
        num = float(m3.group(1))
        return num * 1000.0 if num <= 50 else num

    return float("nan")


# =========================
# 11) 第一階段：主餐/料理/飲料/交通（可收起）
# =========================
if st.session_state.stage == 1:
    st.subheader("🍛 第一階段：主餐與採買")

    # 檢查 'meal_items' 是否已初始化
    if 'meal_items' not in st.session_state or st.session_state.meal_items.empty:
        st.error("meal_items 尚未初始化或為空，請檢查數據加載流程。")
    else:
        meal_df = st.session_state.meal_items.reset_index(drop=True)
        st.write("meal_df 列名：", meal_df.columns)

        # 確保所需的列存在
        required_columns = ["product_name", "cf_gco2e", "declared_unit"]
        missing_columns = [col for col in required_columns if col not in meal_df.columns]

        if missing_columns:
            st.error(f"缺少以下必要的列：{', '.join(missing_columns)}")
        else:
            # 進行列選擇
            food_table = meal_df[["product_name", "cf_gco2e", "declared_unit"]].copy()
            food_table.columns = ["食材名稱", "食材碳足跡(gCO₂e)", "宣告單位"]
            food_table["食材碳足跡(gCO₂e)"] = food_table["食材碳足跡(gCO₂e)"].astype(float).round(1)
            st.dataframe(food_table)

    # 料理方式
    st.markdown("### 🍳 料理方式（每道餐選一次）")
    for i in range(len(meal_df)):
        item_name = meal_df.loc[i, "product_name"]
        item_cf_kg = float(meal_df.loc[i, "cf_kgco2e"])
        st.markdown(f"**第 {i+1} 道：{item_name}**（食材 {item_cf_kg:.3f} kgCO₂e）")
        options = ["水煮", "煎炸"]
        current_method = st.session_state.cook_method.get(i, "水煮")
        chosen = st.radio(
            " ",
            options,
            index=0 if current_method == "水煮" else 1,
            horizontal=True,
            key=f"cook_choice_{i}",
            label_visibility="collapsed",
        )

        new_method = "水煮" if chosen.startswith("水煮") else "煎炸"
        st.session_state.cook_method[i] = new_method

    # 飲料
    st.markdown("### 🥤 飲料（可選）")
    drink_mode = st.radio(
        "飲料選項",
        ["隨機生成飲料", "我不喝飲料"],
        index=0 if st.session_state.drink_mode_state == "隨機生成飲料" else 1,
        horizontal=True,
        key="drink_mode_radio",
    )

    if drink_mode == "隨機生成飲料":
        if st.button("🔄 換一杯飲料", use_container_width=True):
            st.session_state.drink_pick = pick_one(df_all, "2") if len(df_drink) > 0 else None
            st.rerun()

    drink_cf = 0.0
    drink_name = "不喝飲料"
    if st.session_state.drink_mode_state == "隨機生成飲料" and len(df_drink) > 0:
        if st.session_state.drink_pick is None:
            st.session_state.drink_pick = pick_one(df_all, "2")
        dp = st.session_state.drink_pick
        drink_cf = float(dp["cf_kgco2e"])
        drink_name = dp["product_name"]
        st.info(f"本次飲料：**{drink_name}**（{drink_cf:.3f} kgCO₂e）")
    
    # 交通
    st.markdown("### 🧭 採買交通（以你的定位/你設定的起點為中心）")
    origin_lat = st.session_state.origin["lat"]
    origin_lng = st.session_state.origin["lng"]

    if origin_lat and origin_lng:
        st.success(f"📍 已取得起點：{origin_lat:.6f}, {origin_lng:.6f}")

    st.markdown("#### ① 手動輸入起點座標（lat/lng）")
    lat_in = st.number_input("緯度 lat", value=float(origin_lat), format="%.6f")
    lng_in = st.number_input("經度 lng", value=float(origin_lng), format="%.6f")
    if st.button("✅ 使用此座標當起點"):
        st.session_state.origin = {"lat": float(lat_in), "lng": float(lng_in)}
        st.rerun()

    # 地圖和分店選擇
    st.markdown("#### 🗺️ 地圖（點橘色分店 marker 做決策）")
    map_state = st_folium(m, height=320, use_container_width=True, key="store_map")
    
    # 圓餅圖與長條圖
    chart_data = pd.DataFrame([
        {"cat": "Food", "kgCO2e": food_sum},
        {"cat": "Cooking", "kgCO2e": cook_sum},
        {"cat": "Drink", "kgCO2e": drink_cf},
        {"cat": "Transport", "kgCO2e": transport_cf},
    ])
    chart_data = chart_data[chart_data["kgCO2e"] > 0].copy()
    denom = float(chart_data["kgCO2e"].sum()) if float(chart_data["kgCO2e"].sum()) > 0 else 1.0
    chart_data["pct"] = chart_data["kgCO2e"] / denom
    chart_data["pct_label"] = (chart_data["pct"] * 100).round(0).astype(int).astype(str) + "%"

    pie = (
        alt.Chart(chart_data)
        .mark_arc()
        .encode(
            theta=alt.Theta("kgCO2e:Q"),
            color=alt.Color("cat:N", legend=alt.Legend(orient="right", title="Category")),
            tooltip=["cat", alt.Tooltip("kgCO2e:Q", format=".3f"), alt.Tooltip("pct:Q", format=".0%")],
        )
        .properties(height=260)
    )
    labels = (
        alt.Chart(chart_data)
        .mark_text(radius=110)
        .encode(
            theta=alt.Theta("kgCO2e:Q"),
            text=alt.Text("pct_label:N"),
        )
    )
    st.altair_chart(pie + labels, use_container_width=True)
