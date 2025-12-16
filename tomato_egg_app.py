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

# geolocation：注意不要傳 key=...（你之前 TypeError 就是因為這個）
from streamlit_geolocation import streamlit_geolocation


# =========================
# 0) 基本設定
# =========================
st.set_page_config(
    page_title="一餐的碳足跡大冒險：從農場到你的胃",
    page_icon="🍽️",
    layout="centered",
)

st.markdown(
    """
<style>
.block-container { padding-top: 1.2rem; padding-bottom: 2rem; }
h1, h2, h3 { letter-spacing: 0.2px; }
.card {
  padding: 14px 14px 10px 14px;
  border-radius: 14px;
  border: 1px solid rgba(255,255,255,0.12);
  background: rgba(255,255,255,0.03);
}
.small-note { opacity: 0.85; font-size: 0.92rem; }
</style>
""",
    unsafe_allow_html=True,
)

APP_TITLE = "🍽️ 一餐的碳足跡大冒險：從農場到你的胃"

# 交通方式的排放係數
EF_MAP = {"機車": 0.0951, "汽車": 0.115, "貨車": 2.71}


# =========================
# 1) CF 解析：統一成 gCO2e
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


def g_to_kg(g):
    return float(g) / 1000.0


# =========================
# 2) 兩點直線距離（km）
# =========================
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# =========================
# 讀取 Excel
# =========================
def load_data_from_excel(file: BytesIO) -> pd.DataFrame:
    try:
        # 讀取 Excel 檔案
        df = pd.read_excel(file, engine="openpyxl")
        
        # 確認欄位名稱
        st.write("Excel 欄位名稱：", df.columns)

        if df.shape[1] < 3:
            raise ValueError("Excel 欄位太少：至少 3 欄（族群、產品名稱、碳足跡）。")

        # 只保留前三欄：族群、產品名稱、碳足跡
        df = df.iloc[:, :3].copy()
        df.columns = ["group", "product_name", "product_carbon_footprint_data"]

        df["group"] = df["group"].astype(str).str.strip()
        df["product_name"] = df["product_name"].astype(str).str.strip()

        df["cf_gco2e"] = df["product_carbon_footprint_data"].apply(parse_cf_to_g)
        df = df.dropna(subset=["cf_gco2e"]).reset_index(drop=True)

        df["cf_kgco2e"] = df["cf_gco2e"].apply(g_to_kg)
        return df
    except Exception as e:
        st.error(f"讀取 Excel 檔案時出現錯誤：{str(e)}")
        return pd.DataFrame()


# =========================
# 抽樣工具
# =========================
def safe_sample(sub_df: pd.DataFrame, n: int) -> pd.DataFrame:
    if len(sub_df) == 0:
        return sub_df.copy()
    n2 = min(n, len(sub_df))
    return sub_df.sample(n=n2, replace=False, random_state=random.randint(1, 10_000)).reset_index(drop=True)


# =========================
# 主餐、甜點和包材選擇
# =========================
st.title(APP_TITLE)

# 讀取檔案並上傳
uploaded_file = st.file_uploader("請上傳 Excel 檔案", type=["xlsx"])

if uploaded_file is not None:
    # 使用者上傳了檔案
    df_all = load_data_from_excel(uploaded_file)

    # 主餐、甜點和包材選擇
    df_food = df_all[df_all["group"] == "1"].copy() 
    df_dessert = df_all[df_all["group"] == "3"].copy()
    df_packaging = df_all[df_all["group"].isin(["4-1", "4-2", "4-3", "4-4", "4-5", "4-6"])].copy()

    if len(df_food) == 0:
        st.error("Excel 裡找不到 code=1 的食材。請確認『族群』欄有 1。")
        st.stop()

    # 合併階段
    st.subheader("所有流程合併：主餐、甜點與交通")

    # 甜點選擇：隨機 5 種，選 2
    if len(df_dessert) == 0:
        st.warning("找不到甜點資料。")
        dessert_sum = 0.0
    else:
        st.markdown("### 甜點選擇（隨機 5 種，請選 2 種）")
        st.session_state.dessert_pool = safe_sample(df_dessert, 5)
        dessert_options = st.session_state.dessert_pool["product_name"].tolist()
        selected_desserts = st.multiselect("請選擇 2 種甜點", options=dessert_options)
        dessert_sum = df_dessert[df_dessert["product_name"].isin(selected_desserts)]["cf_kgco2e"].sum()

    # 交通選擇
    st.markdown("### 交通方式")
    transport_mode = st.selectbox("選擇交通方式", list(EF_MAP.keys()))
    ef = EF_MAP[transport_mode]
    st.number_input("交通碳足跡排放係數", value=ef, step=0.001, key="ef_final")

    # 綜合計算
    total_food_sum = df_food["cf_kgco2e"].sum()
    total_transport_sum = ef * 10  # 假設 10 km 單程
    total_sum = total_food_sum + dessert_sum + total_transport_sum

    st.write(f"總計碳足跡：{total_sum:.3f} kgCO₂e")
else:
    st.warning("請上傳 Excel 檔案來開始分析。")
