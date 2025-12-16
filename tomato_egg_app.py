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

# 你 repo 內的預設 Excel 檔名（在 repo 根目錄）
EXCEL_PATH_DEFAULT = "產品碳足跡4.xlsx"

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

    # 1.00k 代表 1.00kg
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
# 2) 讀取 Excel（前 3 欄：族群/品名/碳足跡）
# =========================
@st.cache_data(show_spinner=False)
def load_data_from_excel(file_bytes: bytes) -> pd.DataFrame:
    # 檢查檔案是否為 None 或空
    if file_bytes is None or len(file_bytes) == 0:
        raise ValueError("無效的檔案資料，請確保檔案已上傳。")
    
    try:
        # 嘗試讀取 Excel 檔案
        df = pd.read_excel(BytesIO(file_bytes), engine="openpyxl")
        if df.shape[1] < 3:
            raise ValueError("Excel 欄位太少：至少 3 欄（族群、產品名稱、碳足跡）。")
        
        df.columns = ["group", "product_name", "cf_kgco2e"]
        return df
    except Exception as e:
        st.error(f"檔案讀取錯誤: {e}")
        raise e


def read_excel_source() -> pd.DataFrame:
    st.caption("📄 資料來源：優先讀取 repo 根目錄 Excel；若讀不到可改用上傳。")
    try:
        # 嘗試讀取預設的 Excel 檔案
        with open(EXCEL_PATH_DEFAULT, "rb") as f:
            return load_data_from_excel(f.read())
    except Exception:
        # 如果讀取失敗，提供上傳選項
        up = st.file_uploader("或改用上傳 Excel（.xlsx）", type=["xlsx"])
        if up is None:
            raise FileNotFoundError(f"讀取失敗：請確認 {EXCEL_PATH_DEFAULT} 放在 repo 根目錄，或改用上傳。")
        return load_data_from_excel(up.getvalue())


# =========================
# 3) 兩點直線距離（km）
# =========================
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# =========================
# 4) Session 初始化
# =========================
st.session_state.setdefault("page", "home")
st.session_state.setdefault("visitor_id", "")
st.session_state.setdefault("student_name", "")
st.session_state.setdefault("device_id", str(uuid.uuid4())[:8])
st.session_state.setdefault("stage", 1)  # 1=第一階段，2=第二階段
st.session_state.setdefault("meal_items", None)  # 主餐
st.session_state.setdefault("cook_method", {})  # 料理方式
st.session_state.setdefault("drink_pick", None)  # 飲料


# =========================
# 5) 讀取資料並顯示
# =========================
df_all = read_excel_source()

# 抽取食材資料
df_food = df_all[df_all["group"] == "1"].copy()
df_dessert = df_all[df_all["group"] == "3"].copy()

if len(df_food) == 0:
    st.error("找不到食材資料，請確認資料檔案正確。")
    st.stop()


# =========================
# 6) 主餐設定
# =========================
if st.session_state.stage == 1:
    st.title("🍛 主餐與交通階段")
    
    if st.button("🎲 抽 3 項食材（主餐）"):
        st.session_state.meal_items = df_food.sample(n=3).reset_index(drop=True)
        st.session_state.cook_method = {i: "水煮" for i in range(len(st.session_state.meal_items))}
        st.session_state.drink_pick = None
        st.session_state.stage = 2
        st.rerun()

    # 顯示已抽食材
    if st.session_state.meal_items is not None:
        meal_df = st.session_state.meal_items
        st.subheader("主餐選擇")
        st.dataframe(meal_df)

    st.markdown("---")
    
    # 完成第一階段
    if st.button("➡️ 進入第二階段：甜點與餐具包材"):
        st.session_state.stage = 2
        st.rerun()


# =========================
# 7) 第二階段設定
# =========================
if st.session_state.stage == 2:
    st.title("🍰 第二階段：甜點與餐具包材")

    # 隨機選擇 5 種甜點
    if len(df_dessert) == 0:
        st.warning("未找到甜點資料，請檢查檔案。")
    else:
        st.session_state.dessert_pool = df_dessert.sample(n=5).reset_index(drop=True)
        st.multiselect("選擇甜點（請選擇 2 種）", st.session_state.dessert_pool["product_name"].tolist())

    # 顯示結果
    st.markdown("### 甜點總碳足跡")
    # 碳足跡計算及顯示（依您的需求可以進行調整）
    total_carbon_footprint = st.session_state.meal_items["cf_kgco2e"].sum()
    st.write(f"總碳足跡: {total_carbon_footprint:.2f} kg CO₂e")

