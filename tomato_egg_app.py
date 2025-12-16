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

# =========================
# 基本設定
# =========================
st.set_page_config(
    page_title="一餐的碳足跡大冒險：從農場到你的胃",
    page_icon="🍽️",
    layout="centered",
)

APP_TITLE = "🍽️ 一餐的碳足跡大冒險：從農場到你的胃"

# 交通方式的排放係數
EF_MAP = {"機車": 0.0951, "汽車": 0.115, "貨車": 2.71}

# =========================
# CF 解析：統一成 gCO2e
# =========================
def parse_cf_to_g(value) -> float:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return float("nan")
    
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

    return float("nan")


def g_to_kg(g):
    return float(g) / 1000.0


# =========================
# 讀 Excel（前 3 欄：品名/碳足跡/宣告單位）
# =========================
def load_data_from_excel(file_bytes: bytes) -> pd.DataFrame:
    df = pd.read_excel(BytesIO(file_bytes), engine="openpyxl")
    if df.shape[1] < 3:
        raise ValueError("Excel 欄位太少：至少 3 欄（品名、碳足跡、宣告單位）。")
    
    df = df.iloc[:, :3].copy()  # 只保留前三欄
    df.columns = ["product_name", "product_carbon_footprint_data", "declared_unit"]
    
    df["product_name"] = df["product_name"].astype(str).str.strip()
    df["declared_unit"] = df["declared_unit"].astype(str).str.strip()
    
    # 解析碳足跡
    df["cf_gco2e"] = df["product_carbon_footprint_data"].apply(parse_cf_to_g)
    df = df.dropna(subset=["cf_gco2e"]).reset_index(drop=True)
    
    # 轉換成 kgCO2e
    df["cf_kgco2e"] = df["cf_gco2e"].apply(g_to_kg)
    return df


# =========================
# 讀取 Excel 資料
# =========================
def read_excel_source() -> pd.DataFrame:
    st.caption("📄 資料來源：優先讀取 repo 根目錄 Excel；若讀不到可改用上傳。")
    try:
        with open("產品碳足跡3.xlsx", "rb") as f:
            return load_data_from_excel(f.read())
    except Exception:
        up = st.file_uploader("或改用上傳 Excel（.xlsx）", type=["xlsx"])
        if up is None:
            raise FileNotFoundError(f"讀取失敗：請確認 產品碳足跡3.xlsx 放在 repo 根目錄，或改用上傳。")
        return load_data_from_excel(up.getvalue())


# =========================
# 抽樣工具
# =========================
def safe_sample(sub_df: pd.DataFrame, n: int) -> pd.DataFrame:
    if len(sub_df) == 0:
        return sub_df.copy()
    n2 = min(n, len(sub_df))
    return sub_df.sample(n=n2, replace=False, random_state=random.randint(1, 10_000)).reset_index(drop=True)


# =========================
# 讀取 Excel 資料並分類
# =========================
df_all = read_excel_source()

# 分類
df_food = df_all[df_all["product_name"] == "主餐"].copy()
df_dessert = df_all[df_all["product_name"] == "甜點"].copy()
df_packaging = df_all[df_all["product_name"].isin(["包材"])].copy()

# =========================
# 顯示主餐、甜點和包材選擇
# =========================
st.title(APP_TITLE)

# 顯示主餐選擇
st.markdown("### 主餐選擇")
if len(df_food) > 0:
    food = df_food.sample(n=1)
    st.write(f"主餐名稱：{food['product_name'].values[0]}")
    st.write(f"碳足跡：{food['cf_kgco2e'].values[0]:.2f} kgCO₂e")

# 顯示甜點選擇
st.markdown("### 甜點選擇（隨機 5 選 2）")
if len(df_dessert) > 0:
    st.session_state.dessert_pool = safe_sample(df_dessert, 5)
    dessert_options = st.session_state.dessert_pool["product_name"].tolist()
    selected_desserts = st.multiselect("請選擇 2 種甜點", options=dessert_options)
    if len(selected_desserts) == 2:
        dessert_sum = df_dessert[df_dessert["product_name"].isin(selected_desserts)]["cf_kgco2e"].sum()
        st.success(f"甜點總碳足跡：{dessert_sum:.2f} kgCO₂e")
    else:
        st.warning("請選擇 2 種甜點")

# 顯示包材選擇
st.markdown("### 包材選擇（可複選）")
if len(df_packaging) > 0:
    packaging_options = df_packaging["product_name"].tolist()
    selected_packaging = st.multiselect("請選擇包材", options=packaging_options)
    packaging_sum = df_packaging[df_packaging["product_name"].isin(selected_packaging)]["cf_kgco2e"].sum()
    st.write(f"選擇的包材總碳足跡：{packaging_sum:.2f} kgCO₂e")

# =========================
# 交通選擇
# =========================
st.markdown("### 交通方式")
transport_mode = st.selectbox("選擇交通方式", list(EF_MAP.keys()))
ef = EF_MAP[transport_mode]
st.number_input("交通碳足跡排放係數", value=ef, step=0.001, key="ef_final")

# =========================
# 最終加總
# =========================
total_sum = food["cf_kgco2e"].values[0] + dessert_sum + packaging_sum + (ef * 10)  # 假設 10 km 單程
st.write(f"總碳足跡：{total_sum:.3f} kgCO₂e")
