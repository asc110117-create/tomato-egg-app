# app.py（完整：主餐+料理+飲料+採買交通(地圖選分店)+甜點(隨機5選2)+餐具包材(可複選)+圖表(圓餅含比例/長條)+CSV下載+可選Google Sheet記錄）
#
# 需要套件（requirements.txt 需要有）：
# streamlit
# pandas
# openpyxl
# altair
# requests
# folium
# streamlit-folium
# streamlit-geolocation
# gspread
# google-auth

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

# 翁子（預設座標；你也可以改成你要的）
NTSU_LAT = 24.2634328
NTSU_LNG = 120.7426258


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
# 4) 讀 Excel（前 4 欄：編號/品名/碳足跡/宣告單位）
#    -> 統一生成 cf_gco2e
# =========================
@st.cache_data(show_spinner=False)
def load_data_from_excel(file_bytes: bytes) -> pd.DataFrame:
    df = pd.read_excel(BytesIO(file_bytes), engine="openpyxl")
    if df.shape[1] < 4:
        raise ValueError("Excel 欄位太少：至少 4 欄（編號、品名、碳足跡、宣告單位）。")

    df = df.iloc[:, :4].copy()
    df.columns = ["code", "product_name", "product_carbon_footprint_data", "declared_unit"]

    df["code"] = df["code"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    df["product_name"] = df["product_name"].astype(str).str.strip()
    df["declared_unit"] = df["declared_unit"].astype(str).str.strip()

    df["cf_gco2e"] = df["product_carbon_footprint_data"].apply(parse_cf_to_g)
    df = df.dropna(subset=["cf_gco2e"]).reset_index(drop=True)

    # cf_kgco2e 方便計算
    df["cf_kgco2e"] = df["cf_gco2e"].apply(g_to_kg)
    return df


def read_excel_source() -> pd.DataFrame:
    st.caption("📄 資料來源：優先讀取 repo 根目錄 Excel；若讀不到可改用上傳。")
    try:
        with open(EXCEL_PATH_DEFAULT, "rb") as f:
            return load_data_from_excel(f.read())
    except Exception:
        up = st.file_uploader("或改用上傳 Excel（.xlsx）", type=["xlsx"])
        if up is None:
            raise FileNotFoundError(f"讀取失敗：請確認 {EXCEL_PATH_DEFAULT} 放在 repo 根目錄，或改用上傳。")
        return load_data_from_excel(up.getvalue())


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
        "declared_unit": row["declared_unit"],
    }


# =========================
# 6) Google Sheet（可選）
#    沒設定 secrets 也不會壞，只是按鈕會顯示無法寫入
# =========================
def sheets_available() -> bool:
    try:
        _ = st.secrets["gcp_service_account"]
        return True
    except Exception:
        return False


def append_result_to_google_sheet(sheet_name: str, row: dict):
    # 延遲 import（避免沒裝套件或沒 secrets 就爆）
    import gspread
    from google.oauth2.service_account import Credentials

    creds_dict = dict(st.secrets["gcp_service_account"])
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    gc = gspread.authorize(creds)

    sh = gc.open(sheet_name)
    try:
        ws = sh.worksheet("results")
    except Exception:
        ws = sh.add_worksheet(title="results", rows=1000, cols=50)

    header = ws.row_values(1)
    if not header:
        ws.append_row(list(row.keys()))

    # 若 header 與 row keys 不同，保守做法：以 header 順序寫；缺的留空
    if header:
        values = [row.get(k, "") for k in header]
        ws.append_row(values)
    else:
        ws.append_row(list(row.values()))


# =========================
# 7) Session 初始化
# =========================
st.session_state.setdefault("page", "home")
st.session_state.setdefault("visitor_id", "")
st.session_state.setdefault("student_name", "")  # 依報到解析出的名字
st.session_state.setdefault("device_id", str(uuid.uuid4())[:8])

# stage: 1=主餐/交通階段；2=甜點/餐具階段
st.session_state.setdefault("stage", 1)

# 主餐
st.session_state.setdefault("meal_items", None)
st.session_state.setdefault("cook_picks", {})
st.session_state.setdefault("cook_method", {})

# 飲料
st.session_state.setdefault("drink_mode_state", "隨機生成飲料")
st.session_state.setdefault("drink_pick", None)

# 交通（採買）
st.session_state.setdefault("stores", [])     # 已確認（只留 1 家）
st.session_state.setdefault("search", [])     # 最近 5 家
st.session_state.setdefault("decision", 0)    # 目前選中 index
st.session_state.setdefault("transport_mode", "汽車（汽油）")
st.session_state.setdefault("ef_final", 1.15e-1)
st.session_state.setdefault("round_trip", True)

# geolocation component 只能呼叫一次，避免 DuplicateElementKey/元件重複
st.session_state.setdefault("geo", None)
st.session_state.setdefault("origin", {"lat": None, "lng": None})

# 第二階段：甜點/餐具
st.session_state.setdefault("dessert_pool", None)     # 隨機 5 種
st.session_state.setdefault("dessert_pick_names", []) # 使用者選 2 種
st.session_state.setdefault("packaging_pick", [])     # 多選
st.session_state.setdefault("dine_mode", "內用")      # 內用 / 帶回台中教育大學

# 儲存本機彙整（同一台裝置可累積）
st.session_state.setdefault("local_results", [])


# =========================
# 8) 取得定位（只抓一次）
# =========================
if st.session_state.geo is None:
    st.session_state.geo = streamlit_geolocation()  # 不要傳 key=...

geo = st.session_state.geo or {}
geo_lat = geo.get("latitude")
geo_lng = geo.get("longitude")
geo_lat = float(geo_lat) if geo_lat is not None else None
geo_lng = float(geo_lng) if geo_lng is not None else None

if st.session_state.origin["lat"] is None and geo_lat is not None and geo_lng is not None:
    st.session_state.origin = {"lat": geo_lat, "lng": geo_lng}


# =========================
# 9) 母頁（報到）
# =========================
st.title(APP_TITLE)

if st.session_state.page == "home":
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("🏷️ 報到與入場")
    st.write("請輸入您的預約號碼（學號＋姓名）。")

    visitor_id = st.text_input(
        "您的預約號碼：",
        value=st.session_state.visitor_id,
        placeholder="例如：24號黃文瑜",
    )

    colA, colB = st.columns([1, 1])
    with colA:
        if st.button("確認報到", use_container_width=True):
            st.session_state.visitor_id = visitor_id.strip()

    with colB:
        if st.button("直接開始（跳過）", use_container_width=True):
            if not st.session_state.visitor_id:
                st.session_state.visitor_id = "訪客"
            st.session_state.student_name = st.session_state.visitor_id
            st.session_state.page = "main"
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

    vid = st.session_state.visitor_id.strip()
    if vid:
        if vid in VALID_IDS:
            name = VALID_IDS[vid]["name"]
            st.session_state.student_name = name
            st.success(f"{name}您好，報到成功 ✅")
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.write(
                f"""
{name}您好，歡迎來到「碳足跡觀光工廠」！

**第一階段**
- 抽 3 項主餐食材
- 每道餐選擇水煮/煎炸（系統配對油/水）
- 飲料可選
- 採買交通：搜尋附近分店 → 地圖點選 → 確認後加入計算

**第二階段**
- 甜點：隨機 5 種，複選 2 種
- 餐具/包材：可不選、可複選
"""
            )
            if st.button("🍴 開始", use_container_width=True):
                st.session_state.page = "main"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.warning("目前此預約號碼不在名單內（可按「直接開始（跳過）」當訪客進入）。")
    st.stop()


# =========================
# 10) 主頁：讀 Excel / 分類
# =========================
df_all = read_excel_source()

# 你目前的分類規則（依你前面 app）
df_food = df_all[df_all["code"] == "1"].copy()     # 食材
df_oil = df_all[df_all["code"] == "1-1"].copy()    # 油
df_water = df_all[df_all["code"] == "1-2"].copy()  # 水
df_drink = df_all[df_all["code"] == "2"].copy()    # 飲料

# 第二階段
df_dessert = df_all[df_all["code"] == "3"].copy()  # 甜點（你要「從 3 中」）
df_packaging = df_all[df_all["code"].isin(["4-1","4-2","4-3","4-4","4-5","4-6"])].copy()

if len(df_food) == 0:
    st.error("Excel 裡找不到 code=1 的食材。請確認『編號』欄有 1。")
    st.stop()


# =========================
# 11) 第一階段：主餐/料理/飲料/交通（可收起）
# =========================
if st.session_state.stage == 1:
    st.subheader("🍛 第一階段：主餐與採買")

    # 抽食材 / 重置
    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("🎲 抽 3 項食材（主餐）", use_container_width=True):
            st.session_state.meal_items = safe_sample(df_food, 3)
            st.session_state.cook_method = {i: "水煮" for i in range(len(st.session_state.meal_items))}
            st.session_state.cook_picks = {}
            st.session_state.drink_pick = None
            st.session_state.drink_mode_state = "隨機生成飲料"
            st.rerun()

    with c2:
        if st.button("♻️ 全部重置（第一階段）", use_container_width=True):
            st.session_state.meal_items = None
            st.session_state.cook_method = {}
            st.session_state.cook_picks = {}
            st.session_state.drink_mode_state = "隨機生成飲料"
            st.session_state.drink_pick = None
            st.session_state.search = []
            st.session_state.stores = []
            st.session_state.decision = 0
            # 不清 geo 元件，只重設起點
            st.session_state.origin = {"lat": geo_lat, "lng": geo_lng}
            st.rerun()

    if st.session_state.meal_items is None:
        st.session_state.meal_items = safe_sample(df_food, 3)
        st.session_state.cook_method = {i: "水煮" for i in range(len(st.session_state.meal_items))}
        st.session_state.cook_picks = {}
        st.session_state.drink_pick = None

    meal_df = st.session_state.meal_items.reset_index(drop=True)

    # 主餐表
    st.markdown("### 主餐（3 項）")
    food_table = meal_df[["product_name", "cf_gco2e", "declared_unit"]].copy()
    food_table.columns = ["食材名稱", "食材碳足跡(gCO₂e)", "宣告單位"]
    food_table["食材碳足跡(gCO₂e)"] = food_table["食材碳足跡(gCO₂e)"].astype(float).round(1)
    st.dataframe(
        food_table.style.apply(
            lambda _: ["background-color: rgba(46, 204, 113, 0.20)"] * food_table.shape[1],
            axis=1,
        ),
        use_container_width=True,
        height=160,
    )

    # 料理方式
    st.markdown("### 🍳 料理方式（每道餐選一次）")
    for i in range(len(meal_df)):
        item_name = meal_df.loc[i, "product_name"]
        item_cf_kg = float(meal_df.loc[i, "cf_kgco2e"])

        if i not in st.session_state.cook_picks:
            method = st.session_state.cook_method.get(i, "水煮")
            st.session_state.cook_picks[i] = pick_one(df_all, "1-1" if method == "煎炸" else "1-2")

        pick = st.session_state.cook_picks[i]
        oil_text = "（找不到油品 code=1-1）"
        water_text = "（找不到水品 code=1-2）"
        if len(df_oil) > 0:
            oil_text = f"（{pick['product_name']} / {pick['cf_kgco2e']:.3f} kgCO₂e）" if pick["code"] == "1-1" else "（隨機油品）"
        if len(df_water) > 0:
            water_text = f"（{pick['product_name']} / {pick['cf_kgco2e']:.3f} kgCO₂e）" if pick["code"] == "1-2" else "（隨機水品）"

        st.markdown(f"**第 {i+1} 道：{item_name}**（食材 {item_cf_kg:.3f} kgCO₂e）")

        options = [f"水煮 {water_text}", f"煎炸 {oil_text}"]
        current_method = st.session_state.cook_method.get(i, "水煮")
        current_idx = 0 if current_method == "水煮" else 1

        chosen = st.radio(
            " ",
            options,
            index=current_idx,
            horizontal=True,
            key=f"cook_choice_{i}",
            label_visibility="collapsed",
        )

        new_method = "水煮" if chosen.startswith("水煮") else "煎炸"
        if new_method != st.session_state.cook_method.get(i, "水煮"):
            st.session_state.cook_method[i] = new_method
            st.session_state.cook_picks[i] = pick_one(df_all, "1-2" if new_method == "水煮" else "1-1")
            st.rerun()

        st.divider()

    # 飲料
    st.markdown("### 🥤 飲料（可選）")
    drink_mode = st.radio(
        "飲料選項",
        ["隨機生成飲料", "我不喝飲料"],
        index=0 if st.session_state.drink_mode_state == "隨機生成飲料" else 1,
        horizontal=True,
        key="drink_mode_radio",
    )

    if drink_mode != st.session_state.drink_mode_state:
        st.session_state.drink_mode_state = drink_mode
        if drink_mode == "我不喝飲料":
            st.session_state.drink_pick = None
        else:
            st.session_state.drink_pick = pick_one(df_all, "2") if len(df_drink) > 0 else None
        st.rerun()

    if st.session_state.drink_mode_state == "隨機生成飲料":
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
    elif st.session_state.drink_mode_state == "隨機生成飲料" and len(df_drink) == 0:
        st.warning("找不到 code=2 的飲料資料，飲料目前固定為：不喝飲料。")

    # =========================
    # 交通：採買地點（定位中心 + 地圖點分店）
    # =========================
    st.markdown("### 🧭 採買交通（以你的定位/你設定的起點為中心）")
    st.caption("若定位被拒絕：可用手動座標或在地圖點一下當起點。")

    origin_lat = st.session_state.origin["lat"]
    origin_lng = st.session_state.origin["lng"]

    if origin_lat is not None and origin_lng is not None:
        st.success(f"📍 已取得起點：{origin_lat:.6f}, {origin_lng:.6f}")
    else:
        st.warning("目前拿不到定位或尚未設定起點。")

    st.markdown("#### ① 手動輸入起點座標（lat/lng）")
    colO1, colO2, colO3 = st.columns([1, 1, 1])
    with colO1:
        lat_in = st.number_input("緯度 lat", value=float(origin_lat) if origin_lat else NTSU_LAT, format="%.6f")
    with colO2:
        lng_in = st.number_input("經度 lng", value=float(origin_lng) if origin_lng else NTSU_LNG, format="%.6f")
    with colO3:
        if st.button("✅ 使用此座標當起點", use_container_width=True):
            st.session_state.origin = {"lat": float(lat_in), "lng": float(lng_in)}
            st.rerun()

    st.markdown("#### ② 或在地圖上點一下，把「點的位置」當起點")
    fallback_center = [origin_lat if origin_lat else NTSU_LAT, origin_lng if origin_lng else NTSU_LNG]
    m_origin = folium.Map(location=fallback_center, zoom_start=13)
    folium.Marker(fallback_center, tooltip="地圖中心（點地圖可改起點）").add_to(m_origin)
    origin_map_state = st_folium(m_origin, height=320, use_container_width=True, key="origin_map")

    clicked_origin = origin_map_state.get("last_clicked")
    if clicked_origin:
        st.info(f"你點到：{clicked_origin['lat']:.6f}, {clicked_origin['lng']:.6f}")
        if st.button("✅ 將此點設為起點", use_container_width=True):
            st.session_state.origin = {"lat": float(clicked_origin["lat"]), "lng": float(clicked_origin["lng"])}
            st.rerun()

    # 交通方式
    EF_MAP = {"走路": 0.0, "機車": 9.51e-2, "汽車（汽油）": 1.15e-1}
    colA, colB, colC = st.columns([1.1, 1.2, 1.0])

    with colA:
        st.selectbox(
            "交通方式",
            list(EF_MAP.keys()),
            index=list(EF_MAP.keys()).index(st.session_state.get("transport_mode", "汽車（汽油）")),
            key="transport_mode",
        )

    with colB:
        mode = st.session_state["transport_mode"]
        if EF_MAP[mode] == 0.0:
            st.number_input("排放係數（kgCO₂e/km）", min_value=0.0, value=0.0, step=0.01, disabled=True, key="ef_final")
        else:
            st.number_input("排放係數（kgCO₂e/km，可微調）", min_value=0.0, value=float(EF_MAP[mode]), step=0.01, key="ef_final")

    with colC:
        st.checkbox("算來回（去＋回）", value=bool(st.session_state.get("round_trip", True)), key="round_trip")

    ef = float(st.session_state.get("ef_final", 0.0))
    round_trip = bool(st.session_state.get("round_trip", True))

    # 搜尋分店
    st.markdown("#### 🔎 搜尋附近分店（例如：全聯）")
    q = st.text_input("搜尋關鍵字", value="全聯", key="place_query")

    s1, s2 = st.columns([1, 1])
    with s1:
        if st.button("🔍 搜尋附近分店（最近 5 家）", use_container_width=True):
            if st.session_state.origin["lat"] is None or st.session_state.origin["lng"] is None:
                st.error("尚未設定起點，無法搜尋附近分店。請先設定起點。")
            else:
                try:
                    o_lat = st.session_state.origin["lat"]
                    o_lng = st.session_state.origin["lng"]

                    raw = nominatim_search_nearby(q, o_lat, o_lng, radius_km=5, limit=60)
                    if len(raw) < 5:
                        raw = nominatim_search_nearby(q, o_lat, o_lng, radius_km=10, limit=60)

                    results = []
                    for r in raw:
                        d = haversine_km(o_lat, o_lng, r["lat"], r["lng"])
                        rr = dict(r)
                        rr["dist_km"] = d
                        results.append(rr)

                    results.sort(key=lambda x: x["dist_km"])
                    st.session_state.search = results[:5]
                    st.session_state.decision = 0
                    st.rerun()
                except Exception as e:
                    st.session_state.search = []
                    st.session_state.decision = 0
                    st.error("搜尋失敗（可能是服務限制或網路）。請換關鍵字或稍後再試。")
                    st.exception(e)

    with s2:
        if st.button("🧹 清空搜尋結果/已選分店", use_container_width=True):
            st.session_state.search = []
            st.session_state.stores = []
            st.session_state.decision = 0
            st.rerun()

    # 地圖點選分店
    st.markdown("#### 🗺️ 地圖（點橘色分店 marker 做決策）")

    transport_cf = 0.0
    transport_km = 0.0

    if st.session_state.origin["lat"] is None or st.session_state.origin["lng"] is None:
        st.warning("尚未設定起點，因此目前無法顯示附近分店地圖。")
    else:
        o_lat = st.session_state.origin["lat"]
        o_lng = st.session_state.origin["lng"]

        m = folium.Map(location=[o_lat, o_lng], zoom_start=14)
        folium.Marker([o_lat, o_lng], tooltip="起點", icon=folium.Icon(color="blue", icon="user")).add_to(m)

        # 已確認分店（綠色）
        for p in st.session_state.stores:
            folium.Marker(
                [p["lat"], p["lng"]],
                tooltip=f"已確認：{p['name']}",
                popup=p.get("display_name", p["name"]),
                icon=folium.Icon(color="green", icon="shopping-cart"),
            ).add_to(m)

        # 搜尋到的 5 家（橘色＋編號）
        bounds = [[o_lat, o_lng]]
        for i, r in enumerate(st.session_state.search, start=1):
            bounds.append([r["lat"], r["lng"]])

            folium.Marker(
                [r["lat"], r["lng"]],
                tooltip=f"{i}. {r['name']}（{r['dist_km']:.2f} km）",
                popup=r["display_name"],
                icon=folium.Icon(color="orange", icon="info-sign"),
            ).add_to(m)

            folium.Marker(
                [r["lat"], r["lng"]],
                icon=folium.DivIcon(
                    html=f"""
                    <div style="
                        background: rgba(255,255,255,0.92);
                        border: 2px solid #ff9800;
                        border-radius: 999px;
                        width: 26px; height: 26px;
                        text-align: center;
                        line-height: 22px;
                        font-weight: 700;
                        font-size: 14px;
                    ">{i}</div>
                    """
                ),
            ).add_to(m)

        if len(bounds) >= 2:
            m.fit_bounds(bounds)

        map_state = st_folium(m, height=420, use_container_width=True, key="store_map")

        def nearest_store_index(clicked_lat, clicked_lng, stores):
            best_i = None
            best_d = 10**9
            for i, s in enumerate(stores):
                d = haversine_km(clicked_lat, clicked_lng, s["lat"], s["lng"])
                if d < best_d:
                    best_d = d
                    best_i = i
            return best_i, best_d

        st.markdown("##### 🧠 做決策：點橘色分店 → 再按確認加入計算")

        if not st.session_state.search:
            st.warning("尚未搜尋到附近分店。請先按『搜尋附近分店（最近 5 家）』。")
        else:
            clicked = map_state.get("last_object_clicked")  # 點 marker 才會有
            if clicked:
                ci, cd = nearest_store_index(clicked["lat"], clicked["lng"], st.session_state.search)
                # 閾值避免點空白也亂選（0.25 km 內算同一點）
                if ci is not None and cd <= 0.25:
                    st.session_state.decision = ci

            picked = st.session_state.search[int(st.session_state.decision)]
            trip_km_preview = picked["dist_km"] * (2 if round_trip else 1)
            transport_cf_preview = trip_km_preview * ef

            st.info(
                f"目前選擇：**{picked['name']}**\n\n"
                f"- 單程距離：約 **{picked['dist_km']:.2f} km**\n"
                f"- 里程（{'來回' if round_trip else '單程'}）：約 **{trip_km_preview:.2f} km**\n"
                f"- 交通方式：**{st.session_state['transport_mode']}**\n"
                f"- 交通碳足跡（預估）：**{transport_cf_preview:.3f} kgCO₂e**"
            )

            if st.button("✅ 確認此分店（納入計算）", use_container_width=True):
                st.session_state.stores = [picked]  # 只保留 1 家
                st.success("已確認分店 ✅")
                st.rerun()

        # 若已確認分店 → 算交通
        if st.session_state.stores:
            picked = st.session_state.stores[0]
            one_way = haversine_km(o_lat, o_lng, picked["lat"], picked["lng"])
            transport_km = one_way * (2 if round_trip else 1)
            transport_cf = transport_km * ef

    # =========================
    # 第一階段：加總與圖表
    # =========================
    food_sum = float(meal_df["cf_kgco2e"].sum())

    cook_sum = 0.0
    for i in range(len(meal_df)):
        pick = st.session_state.cook_picks.get(i)
        cook_sum += float(pick["cf_kgco2e"]) if pick else 0.0

    stage1_total = food_sum + cook_sum + drink_cf + transport_cf

    st.markdown("## ✅ 第一階段結果")
    st.markdown(
        f"""
- **Food（主餐食材）**：`{food_sum:.3f}` kgCO₂e  
- **Cooking（油/水）**：`{cook_sum:.3f}` kgCO₂e  
- **Drink（飲料）**：`{drink_cf:.3f}` kgCO₂e（{drink_name}）  
- **Transport（採買交通）**：`{transport_cf:.3f}` kgCO₂e（{st.session_state.get("transport_mode","-")}；{'來回' if st.session_state.get("round_trip", True) else '單程'}；{transport_km:.2f} km）  
- **第一階段總計**：✅ **`{stage1_total:.3f}` kgCO₂e**
"""
    )

    # 圓餅/長條（含比例）
    chart_data = pd.DataFrame(
        [
            {"cat": "Food", "kgCO2e": food_sum},
            {"cat": "Cooking", "kgCO2e": cook_sum},
            {"cat": "Drink", "kgCO2e": drink_cf},
            {"cat": "Transport", "kgCO2e": transport_cf},
        ]
    )
    chart_data = chart_data[chart_data["kgCO2e"] > 0].copy()
    if len(chart_data) == 0:
        chart_data = pd.DataFrame([{"cat": "Food", "kgCO2e": 0.0}])

    denom = float(chart_data["kgCO2e"].sum()) if float(chart_data["kgCO2e"].sum()) > 0 else 1.0
    chart_data["pct"] = chart_data["kgCO2e"] / denom
    chart_data["pct_label"] = (chart_data["pct"] * 100).round(0).astype(int).astype(str) + "%"

    st.markdown("### 📊 第一階段圖表")
    bar = (
        alt.Chart(chart_data)
        .mark_bar()
        .encode(
            y=alt.Y("cat:N", sort="-x", title=""),
            x=alt.X("kgCO2e:Q", title="kgCO₂e"),
            tooltip=["cat", alt.Tooltip("kgCO2e:Q", format=".3f"), alt.Tooltip("pct:Q", format=".0%")],
        )
        .properties(height=170)
    )
    st.altair_chart(bar, use_container_width=True)

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

    # 進入第二階段（收起上面所有流程）
    st.markdown("---")
    if st.button("➡️ 進入第二階段：甜點 / 餐具包材（收起第一階段流程）", use_container_width=True):
        st.session_state.stage = 2
        st.rerun()


# =========================
# 12) 第二階段：甜點/餐具包材（可複選） + 最終加總/圖表
# =========================
if st.session_state.stage == 2:
    st.subheader("🍰 第二階段：甜點與餐具包材")
    st.caption("第一階段流程已收起；你可以返回重做，但通常課堂上會直接進第二階段。")

    # 重新計算第一階段（避免 stage 切換後失去）
    meal_df = st.session_state.meal_items.reset_index(drop=True)
    food_sum = float(meal_df["cf_kgco2e"].sum())

    cook_sum = 0.0
    for i in range(len(meal_df)):
        pick = st.session_state.cook_picks.get(i)
        cook_sum += float(pick["cf_kgco2e"]) if pick else 0.0

    # drink
    drink_cf = 0.0
    drink_name = "不喝飲料"
    if st.session_state.drink_mode_state == "隨機生成飲料" and len(df_drink) > 0:
        if st.session_state.drink_pick is None:
            st.session_state.drink_pick = pick_one(df_all, "2")
        dp = st.session_state.drink_pick
        drink_cf = float(dp["cf_kgco2e"])
        drink_name = dp["product_name"]

    # transport（已確認分店才算）
    transport_cf = 0.0
    transport_km = 0.0
    if st.session_state.stores and st.session_state.origin["lat"] is not None:
        o_lat = st.session_state.origin["lat"]
        o_lng = st.session_state.origin["lng"]
        ef = float(st.session_state.get("ef_final", 0.0))
        round_trip = bool(st.session_state.get("round_trip", True))
        picked = st.session_state.stores[0]
        one_way = haversine_km(o_lat, o_lng, picked["lat"], picked["lng"])
        transport_km = one_way * (2 if round_trip else 1)
        transport_cf = transport_km * ef

    # -------- 甜點：隨機 5 種，複選 2 --------
    st.markdown("### 🍰 今日甜點（隨機 5 種，請複選 2 種）")
    if len(df_dessert) == 0:
        st.warning("Excel 找不到 code=3 的甜點資料，因此甜點本次為 0。")
        dessert_sum = 0.0
        dessert_selected = []
    else:
        if st.session_state.dessert_pool is None:
            st.session_state.dessert_pool = safe_sample(df_dessert, 5)

        dessert_pool = st.session_state.dessert_pool.copy()
        options = dessert_pool["product_name"].tolist()

        chosen = st.multiselect(
            "請選 2 種甜點（不夠 2 種不會算）",
            options=options,
            default=[x for x in st.session_state.dessert_pick_names if x in options],
        )
        st.session_state.dessert_pick_names = chosen

        if len(chosen) != 2:
            st.warning("請務必選 **2 種** 甜點（目前不納入計算）。")
            dessert_sum = 0.0
            dessert_selected = chosen
        else:
            dessert_selected = chosen
            dessert_sum = float(dessert_pool[dessert_pool["product_name"].isin(chosen)]["cf_kgco2e"].sum())
            st.success(f"甜點已納入計算：{dessert_sum:.3f} kgCO₂e")

    # -------- 餐具/包材：可不選、可複選 4-1~4-6 --------
    st.markdown("### 🍴 餐具 / 包材（可不選、可複選）")
    packaging_sum = 0.0
    if len(df_packaging) == 0:
        st.warning("Excel 找不到 4-1~4-6 的餐具/包材資料，本次為 0。")
    else:
        pk_opts = df_packaging["product_name"].tolist()
        pk_selected = st.multiselect(
            "選擇你使用的餐具/包材（可空）",
            options=pk_opts,
            default=[x for x in st.session_state.packaging_pick if x in pk_opts],
        )
        st.session_state.packaging_pick = pk_selected
        packaging_sum = float(df_packaging[df_packaging["product_name"].isin(pk_selected)]["cf_kgco2e"].sum()) if pk_selected else 0.0

    # -------- 內用 / 帶回台中教育大學 --------
    st.markdown("### 🏫 內用或帶回台中教育大學")
    dine_mode = st.radio(
        "選擇方式",
        ["內用", "帶回台中教育大學"],
        index=0 if st.session_state.dine_mode == "內用" else 1,
        horizontal=True,
        key="dine_mode_radio",
    )
    st.session_state.dine_mode = dine_mode

    # 若帶回：再出現一次地圖（從分店到 NTCU）
    extra_takeout_cf = 0.0
    extra_takeout_km = 0.0

    if dine_mode == "帶回台中教育大學":
        st.info("你選擇「帶回」，將計算『分店 → 台中教育大學』的交通碳足跡。")
        if not st.session_state.stores:
            st.warning("你尚未在第一階段確認分店，所以無法計算帶回交通。請回第一階段先選分店。")
        else:
            picked = st.session_state.stores[0]
            ef = float(st.session_state.get("ef_final", 0.0))  # 用同一交通係數
            # 這段視為單程
            extra_takeout_km = haversine_km(picked["lat"], picked["lng"], NTSU_LAT, NTSU_LNG)
            extra_takeout_cf = extra_takeout_km * ef

            m2 = folium.Map(location=[NTSU_LAT, NTSU_LNG], zoom_start=13)
            folium.Marker([picked["lat"], picked["lng"]], tooltip=f"分店：{picked['name']}", icon=folium.Icon(color="green")).add_to(m2)
            folium.Marker([NTSU_LAT, NTSU_LNG], tooltip="台中教育大學（預設）", icon=folium.Icon(color="blue")).add_to(m2)
            folium.PolyLine([[picked["lat"], picked["lng"]], [NTSU_LAT, NTSU_LNG]], weight=3).add_to(m2)
            st_folium(m2, height=320, use_container_width=True, key="takeout_map")

            st.success(f"帶回交通：{extra_takeout_km:.2f} km（單程）→ {extra_takeout_cf:.3f} kgCO₂e")
    else:
        st.caption("選擇「內用」：不計入帶回交通碳足跡。")

    # =========================
    # 最終加總 + 圖表（含比例）
    # =========================
    total = food_sum + cook_sum + drink_cf + transport_cf + dessert_sum + packaging_sum + extra_takeout_cf

    st.markdown("## ✅ 最終碳足跡")
    st.markdown(
        f"""
- **Food（主餐食材）**：`{food_sum:.3f}` kgCO₂e  
- **Cooking（油/水）**：`{cook_sum:.3f}` kgCO₂e  
- **Drink（飲料）**：`{drink_cf:.3f}` kgCO₂e（{drink_name}）  
- **Transport（採買交通）**：`{transport_cf:.3f}` kgCO₂e  
- **Dessert（甜點）**：`{dessert_sum:.3f}` kgCO₂e（{", ".join(dessert_selected) if dessert_selected else "未納入"}）  
- **Packaging（餐具包材）**：`{packaging_sum:.3f}` kgCO₂e  
- **Takeout（帶回交通）**：`{extra_takeout_cf:.3f}` kgCO₂e  
- **總計**：✅ **`{total:.3f}` kgCO₂e**
"""
    )

    st.markdown("### 📊 最終圖表（含比例 %）")
    chart_data = pd.DataFrame(
        [
            {"cat": "Food", "kgCO2e": food_sum},
            {"cat": "Cooking", "kgCO2e": cook_sum},
            {"cat": "Drink", "kgCO2e": drink_cf},
            {"cat": "Transport", "kgCO2e": transport_cf},
            {"cat": "Dessert", "kgCO2e": dessert_sum},
            {"cat": "Packaging", "kgCO2e": packaging_sum},
        ]
    )
    if extra_takeout_cf > 0:
        chart_data = pd.concat([chart_data, pd.DataFrame([{"cat": "Takeout", "kgCO2e": extra_takeout_cf}])], ignore_index=True)

    chart_data = chart_data[chart_data["kgCO2e"] > 0].copy()
    denom = float(chart_data["kgCO2e"].sum()) if float(chart_data["kgCO2e"].sum()) > 0 else 1.0
    chart_data["pct"] = chart_data["kgCO2e"] / denom
    chart_data["pct_label"] = (chart_data["pct"] * 100).round(0).astype(int).astype(str) + "%"

    bar = (
        alt.Chart(chart_data)
        .mark_bar()
        .encode(
            y=alt.Y("cat:N", sort="-x", title=""),
            x=alt.X("kgCO2e:Q", title="kgCO₂e"),
            tooltip=["cat", alt.Tooltip("kgCO2e:Q", format=".3f"), alt.Tooltip("pct:Q", format=".0%")],
        )
        .properties(height=200)
    )
    st.altair_chart(bar, use_container_width=True)

    pie = (
        alt.Chart(chart_data)
        .mark_arc()
        .encode(
            theta=alt.Theta("kgCO2e:Q"),
            color=alt.Color("cat:N", legend=alt.Legend(orient="right", title="Category")),
            tooltip=["cat", alt.Tooltip("kgCO2e:Q", format=".3f"), alt.Tooltip("pct:Q", format=".0%")],
        )
        .properties(height=280)
    )
    labels = (
        alt.Chart(chart_data)
        .mark_text(radius=120)
        .encode(
            theta=alt.Theta("kgCO2e:Q"),
            text=alt.Text("pct_label:N"),
        )
    )
    st.altair_chart(pie + labels, use_container_width=True)

    # =========================
    # 記錄：下載 CSV +（可選）寫入 Google Sheet
    # =========================
    student_name = st.session_state.student_name or st.session_state.visitor_id or "未報到"
    row = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "student_name": student_name,
        "visitor_id": st.session_state.visitor_id,
        "device_id": st.session_state.device_id,
        "total_kgco2e": round(total, 6),
        "Food_kgco2e": round(food_sum, 6),
        "Cooking_kgco2e": round(cook_sum, 6),
        "Drink_kgco2e": round(drink_cf, 6),
        "Transport_kgco2e": round(transport_cf, 6),
        "Dessert_kgco2e": round(dessert_sum, 6),
        "Packaging_kgco2e": round(packaging_sum, 6),
        "Takeout_kgco2e": round(extra_takeout_cf, 6),
        "drink_name": drink_name,
        "dessert_selected": ", ".join(dessert_selected) if dessert_selected else "",
        "packaging_selected": ", ".join(st.session_state.packaging_pick) if st.session_state.packaging_pick else "",
        "store_selected": st.session_state.stores[0]["name"] if st.session_state.stores else "",
        "origin_lat": st.session_state.origin["lat"],
        "origin_lng": st.session_state.origin["lng"],
    }

    colR1, colR2 = st.columns([1, 1])
    with colR1:
        # 個人 CSV
        csv_bytes = pd.DataFrame([row]).to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "⬇️ 下載我的結果 CSV",
            data=csv_bytes,
            file_name=f"{student_name}_carbon_result.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with colR2:
        # 本機彙整 CSV（同一台裝置）
        if st.button("➕ 將本次結果加入本機彙整（同裝置）", use_container_width=True):
            st.session_state.local_results.append(row)
            st.success("已加入本機彙整 ✅")

    if st.session_state.local_results:
        df_local = pd.DataFrame(st.session_state.local_results)
        st.markdown("### 📦 本機彙整（同一台裝置）")
        st.dataframe(df_local, use_container_width=True, height=220)
        st.download_button(
            "⬇️ 下載本機彙整 CSV（同一台裝置累積）",
            data=df_local.to_csv(index=False).encode("utf-8-sig"),
            file_name="local_results.csv",
            mime="text/csv",
            use_container_width=True,
        )

    st.markdown("### 🧾 全班總表（Google Sheet，可選）")
    SHEET_NAME = st.text_input("Google Sheet 檔名（要完全一樣）", value="學生碳足跡紀錄")
    if sheets_available():
        if st.button("📤 送出並寫入 Google Sheet（全班彙整）", use_container_width=True):
            try:
                append_result_to_google_sheet(SHEET_NAME, row)
                st.success("已成功寫入 Google Sheet ✅")
            except Exception as e:
                st.error("寫入失敗：請確認（1）服務帳戶已共用該 Sheet 為編輯者（2）Sheet 檔名正確。")
                st.exception(e)
    else:
        st.warning("尚未設定 Google Sheet 憑證（st.secrets['gcp_service_account']）。你仍可下載 CSV。")

    st.markdown("---")
    if st.button("↩️ 回到第一階段（重新調整主餐/交通）", use_container_width=True):
        st.session_state.stage = 1
        st.rerun()
