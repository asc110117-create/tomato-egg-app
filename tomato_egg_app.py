import random
import math
from io import BytesIO
import pandas as pd
import streamlit as st
import altair as alt
import folium
from streamlit_folium import st_folium
from streamlit_geolocation import streamlit_geolocation
import gspread
from google.oauth2.service_account import Credentials

# =========================
# 基本設定
# =========================
st.set_page_config(page_title="碳足跡大冒險", page_icon="🍽️", layout="centered")

# 讀取 Google Sheet secrets
def sheets_available() -> bool:
    try:
        _ = st.secrets["gcp_service_account"]
        _ = st.secrets["google_sheet"]["spreadsheet_id"]
        _ = st.secrets["google_sheet"]["worksheet_name"]
        return True
    except Exception:
        return False

# =========================
# 定位及地圖
# =========================
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))

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
            {"display_name": display_name, "name": (display_name.split(",")[0] if display_name else "").strip(),
             "lat": float(x["lat"]), "lng": float(x["lon"])}
        )
    return out

# =========================
# 讀取Excel資料
# =========================
@st.cache_data(show_spinner=False)
def load_data_from_excel(file_bytes: bytes) -> pd.DataFrame:
    df = pd.read_excel(BytesIO(file_bytes), engine="openpyxl")
    if df.shape[1] < 4:
        raise ValueError("Excel 欄位太少：至少 4 欄（編號、品名、碳足跡、宣告單位）。")
    df = df.iloc[:, :4].copy()
    df.columns = ["code", "product_name", "product_carbon_footprint_data", "declared_unit"]
    df["cf_gco2e"] = df["product_carbon_footprint_data"].apply(lambda x: float(str(x).replace('gCO2e','').replace('kgCO2e', '').replace('g', '').replace('kg','').strip()) if isinstance(x, str) else 0)
    df["cf_kgco2e"] = df["cf_gco2e"] / 1000  # convert g to kg
    return df

def read_excel_source() -> pd.DataFrame:
    st.caption("📄 資料來源：優先讀取 repo 根目錄 Excel；若讀不到可改用上傳。")
    try:
        with open("碳足跡4.xlsx", "rb") as f:
            return load_data_from_excel(f.read())
    except Exception:
        up = st.file_uploader("或改用上傳 Excel（.xlsx）", type=["xlsx"])
        if up is None:
            raise FileNotFoundError(f"讀取失敗：請確認 '碳足跡4.xlsx' 放在 repo 根目錄，或改用上傳。")
        return load_data_from_excel(up.getvalue())

# =========================
# 進行選擇與計算
# =========================
def calculate_transport_cf(distance, weight, tkm):
    return distance * weight * tkm

# =========================
# 主食選擇
# =========================
def choose_main_dish(df_food):
    food_options = df_food.sample(5)
    selected_food = st.multiselect("選擇2個主食", options=food_options['product_name'].tolist(), default=food_options['product_name'].tolist()[:2])
    selected_food_data = food_options[food_options['product_name'].isin(selected_food)]
    return selected_food_data

# =========================
# 交通工具選擇
# =========================
def choose_transport():
    transport_options = ["走路", "機車", "汽車", "貨車"]
    transport = st.selectbox("選擇交通工具", transport_options)
    return transport

# =========================
# 寫入 Google Sheet
# =========================
def write_to_google_sheet(row_dict: dict):
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"])
    gc = gspread.authorize(creds)
    sheet = gc.open_by_key(st.secrets["google_sheet"]["spreadsheet_id"])
    worksheet = sheet.get_worksheet(0)
    worksheet.append_row(list(row_dict.values()))

# =========================
# 主程式
# =========================
def main():
    st.title("一餐的碳足跡大冒險：從農場到你的胃")
    
    df_all = read_excel_source()

    # 主食選擇
    selected_food = choose_main_dish(df_all[df_all['code'] == '1'])

    # 交通選擇
    transport_mode = choose_transport()

    # 計算交通碳足跡
    transport_distance = 10  # 預設為10km
    transport_weight = selected_food["cf_kgco2e"].sum() / 1000  # 食材總重（公斤）
    transport_tkm = {"機車": 0.0951, "汽車": 0.115, "貨車": 2.71}.get(transport_mode, 0.0)
    transport_cf = calculate_transport_cf(transport_distance, transport_weight, transport_tkm)
    
    st.write(f"您選擇的交通工具是：{transport_mode}，碳足跡為：{transport_cf:.3f} kgCO₂e")

    # 顯示選擇的食材
    st.write(f"您選擇的食材為：{', '.join(selected_food['product_name'].tolist())}")

    # 統計結果
    total_cf = selected_food['cf_kgco2e'].sum() + transport_cf
    st.write(f"您的總碳足跡為：{total_cf:.3f} kgCO₂e")

    # 寫入 Google Sheet
    if st.button("將結果寫入 Google Sheet"):
        row_dict = {
            "食材": ", ".join(selected_food['product_name'].tolist()),
            "交通工具": transport_mode,
            "碳足跡": f"{total_cf:.3f}",
        }
        write_to_google_sheet(row_dict)
        st.success("結果已成功寫入 Google Sheet！")

# =========================
# 程式執行
# =========================
if __name__ == "__main__":
    main()
