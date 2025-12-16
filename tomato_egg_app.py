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
#    支援：800.00g、0.8kg、1.00k、"155.00gCO2e"、"1.00kgCO2e"... 
# =========================
def parse_cf_to_g(value) -> float:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return float("nan")

    # 數字：預設當作「g」還是「kg」？  
    # 你的資料混用，單純數字很難判斷  
    # 這裡採最保守：若數字 <= 50 當 kg（多數產品 kgCO2e 不會 >50）、否則當 g  
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

    # 末尾單位
    m = re.match(r"([-+]?\d*\.?\d+)(kg|g)?$", s)
    if m:
        num = float(m.group(1))
        unit = m.group(2)
        if unit == "kg":
            return num * 1000.0
        if unit == "g":
            return num
        # 沒單位：同上，<=50 當 kg
        return num * 1000.0 if num <= 50 else num

    # 字串內含單位（例如：'800.00g(每瓶...)'）
    m2 = re.search(r"([-+]?\d*\.?\d+)\s*(kg|g)", s)
    if m2:
        num = float(m2.group(1))
        unit = m2.group(2)
        return num * 1000.0 if unit == "kg" else num

    # 兜底：抓第一個數字
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
# 3) 以中心點搜尋附近分店（OSM Nominatim）
# =========================
def nominatim_search_nearby(query, lat, lng, radius_km=5, limit=60):
    if not query.strip():
        return []

    lat_delta = radius_km / 111.0
    lng_delta = radius_km / (111.0 * max(0.1, math.cos(math.radians(lat))))
    viewbox = f"{lng-lng_delta},{lat+lat_delta},{lng+lng_delta},{lat-lat_delta}"

    params = {
        "q": query,
        "format": "jsonv2",
        "limit": str(limit),
        "addressdetails": 1,
        "viewbox": viewbox,
        "bounded": 1,
    }
    headers = {
        "User-Agent": "carbon-footprint-edu-app/1.0",
        "Accept-Language": "zh-TW,zh,en",
    }

    r = requests.get("https://nominatim.openstreetmap.org/search", params=params, headers=headers, timeout=10)
    r.raise_for_status()
    data = r.json()

    out = []
    for x in data:
        display_name = x.get("display_name", "")
        out.append(
            {
                "display_name": display_name,
                "name": (display_name.split(",")[0] if display_name else "").strip(),
                "lat": float(x["lat"]),
                "lng": float(x["lon"]),
            }
        )
    return out


# =========================
# 4) 讀 Excel（前 3 欄：族群、品名、碳足跡）
#    -> 統一生成 cf_gco2e
# =========================
@st.cache_data(show_spinner=False)
def load_data_from_excel(file_bytes: bytes) -> pd.DataFrame:
    df = pd.read_excel(BytesIO(file_bytes), engine="openpyxl")
    if df.shape[1] < 3:
        raise ValueError("Excel 欄位太少：至少 3 欄（族群、品名、碳足跡）。")

    df = df.iloc[:, :3].copy()  # 取前 3 欄
    df.columns = ["code", "product_name", "product_carbon_footprint_data"]

    df["code"] = df["code"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    df["product_name"] = df["product_name"].astype(str).str.strip()

    df["cf_gco2e"] = df["product_carbon_footprint_data"].apply(parse_cf_to_g)
    df = df.dropna(subset=["cf_gco2e"]).reset_index(drop=True)

    # cf_kgco2e 方便計算
    df["cf_kgco2e"] = df["cf_gco2e"].apply(g_to_kg)
    return df


# =========================
# 5) 抽樣工具
# =========================
def safe_sample(sub_df: pd.DataFrame, n: int) -> pd.DataFrame:
    if len(sub_df) == 0:
        return sub_df.copy()
    n2 = min(n, len(sub_df))
    return sub_df.sample(n=n2, replace=False, random_state=random.randint(1, 10_000)).reset_index(drop=True)


def pick_one(df: pd.DataFrame, code_value: str) -> dict:
    sub = df[df["code"] == code_value]
    if len(sub) == 0:
        raise ValueError(f"在 Excel 中找不到 code = {code_value} 的資料。")
    row = sub.sample(n=1, random_state=random.randint(1, 10_000)).iloc[0]
    return {
        "code": row["code"],
        "product_name": row["product_name"],
        "cf_gco2e": float(row["cf_gco2e"]),
        "cf_kgco2e": float(row["cf_kgco2e"]),
    }


# =========================
# 6) 取得定位（只抓一次）
# =========================
# 初始化 origin
if "origin" not in st.session_state:
    st.session_state.origin = {"lat": None, "lng": None}

# 取得定位資料
if st.session_state.geo is None:
    st.session_state.geo = streamlit_geolocation()  # 不要傳 key=...

geo = st.session_state.geo or {}
geo_lat = geo.get("latitude")
geo_lng = geo.get("longitude")
geo_lat = float(geo_lat) if geo_lat is not None else None
geo_lng = float(geo_lng) if geo_lng is not None else None

# 當 origin 尚未設置並且已經取得定位資料時，設置 origin
if st.session_state.origin["lat"] is None and geo_lat is not None and geo_lng is not None:
    st.session_state.origin = {"lat": geo_lat, "lng": geo_lng}


# =========================
# 10) 主頁：讀 Excel / 分類
# =========================
df_all = load_data_from_excel(EXCEL_PATH_DEFAULT)

# 你目前的分類規則（依你前面 app）
df_food = df_all[df_all["code"] == "1"].copy()     # 食材
df_oil = df_all[df_all["code"] == "1-1"].copy()    # 油
df_water = df_all[df_all["code"] == "1-2"].copy()  # 水
df_drink = df_all[df_all["code"] == "2"].copy()    # 飲料

# 第二階段
df_dessert = df_all[df_all["code"] == "3"].copy()  # 甜點（你要「從 3 中」）
df_packaging = df_all[df_all["code"].isin(["4-1","4-2","4-3","4-4","4-5","4-6"])].copy()

# =========================
# 11) 第一階段：主餐/料理/飲料/交通（可收起）
# =========================
# 略過較長部分，請將主餐碳足跡加總並顯示交通



