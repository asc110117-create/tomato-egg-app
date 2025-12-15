# tomato_egg_app.py
# 一餐的碳足跡大冒險（Streamlit）
# 功能：讀取 Excel（自動把 g/kg 統一成 gCO2e）、主餐/料理/飲料/交通/甜點/餐具包材、圖表、CSV下載、可選寫入 Google Sheet
#
# requirements.txt 建議至少包含：
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
#
# ------------------------
# ⚠️ 安全提醒：
# 你剛剛把「Service Account JSON」貼到公開對話裡了，等同於私鑰外洩。
# 請立刻到 Google Cloud Console → IAM & Admin → Service Accounts → Keys：把那把 Key 刪掉（revoke），再重建一把新的。
# 新的 JSON 只放在 Streamlit Secrets（不要 commit 到 GitHub）。
# ------------------------

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
EXCEL_PATH_DEFAULT = "產品碳足跡3.xlsx"  # repo 根目錄

# 台中教育大學（預設座標）
NTSU_LAT = 24.1477
NTSU_LNG = 120.6736

# 報到名單（可自行加）
VALID_IDS = {
    "BEE114105黃文瑜": {"name": "文瑜"},
    "BEE114108陳依萱": {"name": "依萱"},
}


# =========================
# 1) CF 解析：統一成 gCO2e
# =========================
def parse_cf_to_g(value) -> float:
    """
    把各種格式的碳足跡值統一轉成「gCO2e」(float)。

    支援：
    - 800, 800.0 -> 預設當 g（但若 <= 50 則偏向視為 kg）
    - "800g", "800 gCO2e"
    - "0.8kg", "0.8 kgCO2e"
    - "1.00k"（視為 1.00kg）
    - "800g(每瓶)" 這類含文字
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return float("nan")

    # 純數字：很難判斷單位，採保守 heuristic
    if isinstance(value, (int, float)):
        v = float(value)
        return v * 1000.0 if v <= 50 else v

    s = str(value).strip().lower().replace(" ", "")
    s = s.replace("kgco2e", "kg").replace("gco2e", "g")

    # 1.00k 代表 1.00kg
    if re.fullmatch(r"[-+]?\d*\.?\d+k", s):
        kg = float(s[:-1])
        return kg * 1000.0

    # 末尾單位（完全匹配）
    m = re.match(r"([-+]?\d*\.?\d+)(kg|g)?$", s)
    if m:
        num = float(m.group(1))
        unit = m.group(2)
        if unit == "kg":
            return num * 1000.0
        if unit == "g":
            return num
        return num * 1000.0 if num <= 50 else num

    # 字串中含單位（例如：800g(每瓶...)）
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
# 4) 讀 Excel（前 4 欄：編號/品名/碳足跡/宣告單位）-> 統一生成 cf_gco2e
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
# 6) Google Sheet（重點修正）
#    ✅ 不再用 gc.open(sheet_name)（那會走 Drive API，Drive 沒開就 403）
#    ✅ 改成 open_by_key(spreadsheet_id)（只需要 Sheets API）
# =========================
def sheets_available() -> bool:
    try:
        _ = st.secrets["gcp_service_account"]
        _ = st.secrets["google_sheet"]["spreadsheet_id"]
        _ = st.secrets["google_sheet"]["worksheet_name"]
        return True
    except Exception:
        return False


def append_result_to_google_sheet(row: dict):
    import gspread
    from google.oauth2.service_account import Credentials

    creds_dict = dict(st.secrets["gcp_service_account"])

    # ✅ 只要 spreadsheets scope 就夠（不需要 Drive scope）
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    gc = gspread.authorize(creds)

    sheet_id = st.secrets["google_sheet"]["spreadsheet_id"]
    ws_name = st.secrets["google_sheet"]["worksheet_name"]

    sh = gc.open_by_key(sheet_id)

    try:
        ws = sh.worksheet(ws_name)
    except Exception:
        ws = sh.add_worksheet(title=ws_name, rows=2000, cols=50)

    header = ws.row_values(1)
    if not header:
        ws.append_row(list(row.keys()))

    # 以 header 欄位順序寫入（避免欄位對不齊）
    header = ws.row_values(1)
    values = [row.get(k, "") for k in header]
    ws.append_row(values)


# =========================
# 7) Session 初始化
# =========================
st.session_state.setdefault("page", "home")
st.session_state.setdefault("visitor_id", "")
st.session_state.setdefault("student_name", "")
st.session_state.setdefault("device_id", str(uuid.uuid4())[:8])

st.session_state.setdefault("stage", 1)

st.session_state.setdefault("meal_items", None)
st.session_state.setdefault("cook_picks", {})
st.session_state.setdefault("cook_method", {})

st.session_state.setdefault("drink_mode_state", "隨機生成飲料")
st.session_state.setdefault("drink_pick", None)

st.session_state.setdefault("stores", [])
st.session_state.setdefault("search", [])
st.session_state.setdefault("decision", 0)
st.session_state.setdefault("transport_mode", "汽車（汽油）")
st.session_state.setdefault("ef_final", 1.15e-1)
st.session_state.setdefault("round_trip", True)

st.session_state.setdefault("geo", None)
st.session_state.setdefault("origin", {"lat": None, "lng": None})

st.session_state.setdefault("dessert_pool", None)
st.session_state.setdefault("dessert_pick_names", [])
st.session_state.setdefault("packaging_pick", [])
st.session_state.setdefault("dine_mode", "內用")

st.session_state.setdefault("local_results", [])


# =========================
# 8) 取得定位（只抓一次）
# =========================
if st.session_state.geo is None:
    st.session_state.geo = streamlit_geolocation()

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
        placeholder="例如：BEE114108陳依萱",
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

df_food = df_all[df_all["code"] == "1"].copy()     # 食材
df_oil = df_all[df_all["code"] == "1-1"].copy()    # 油
df_water = df_all[df_all["code"] == "1-2"].copy()  # 水
df_drink = df_all[df_all["code"] == "2"].copy()    # 飲料

df_dessert = df_all[df_all["code"] == "3"].copy()  # 甜點
df_packaging = df_all[df_all["code"].isin(["4-1","4-2","4-3","4-4","4-5","4-6"])].copy()

if len(df_food) == 0:
    st.error("Excel 裡找不到 code=1 的食材。請確認『編號』欄有 1。")
    st.stop()


# =========================
# 11) 第一階段：主餐/料理/飲料/交通
# =========================
if st.session_state.stage == 1:
    st.subheader("🍛 第一階段：主餐與採買")

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
            st.session_state.origin = {"lat": geo_lat, "lng": geo_lng}
            st.rerun()

    if st.session_state.meal_items is None:
        st.session_state.meal_items = safe_sample(df_food, 3)
        st.session_state.cook_method = {i: "水煮" for i in range(len(st.session_state.meal_items))}
        st.session_state.cook_picks = {}
        st.session_state.drink_pick = None

    meal_df = st.session_state.meal_items.reset_index(drop=True)

    st.markdown("### 主餐（3 項）")
    # ✅ 這裡就是你之前 KeyError 的地方：一定要先確定 meal_df 有 cf_gco2e 欄位
    # 由 load_data_from_excel() 已保證產生 cf_gco2e / cf_kgco2e。
    food_table = meal_df[["product_name", "cf_gco2e", "declared_unit"]].copy()
    food_table.columns = ["食材名稱", "食材碳足跡(gCO₂e)", "宣告單位"]
    food_table["食材碳足跡(gCO₂e)"] = food_table["食材碳足跡(gCO₂e)"].astype(float).round(1)
    st.dataframe(food_table, use_container_width=True, height=160)

    st.markdown("### 🍳 料理方式（每道餐選一次）")
    for i in range(len(meal_df)):
        item_name = meal_df.loc[i, "product_name"]
        item_cf_kg = float(meal_df.loc[i, "cf_kgco2e"])

        if i not in st.session_state.cook_picks:
            method = st.session_state.cook_method.get(i, "水煮")
            st.session_state.cook_picks[i] = pick_one(df_all, "1-1" if method == "煎炸" else "1-2")

        st.markdown(f"**第 {i+1} 道：{item_name}**（食材 {item_cf_kg:.3f} kgCO₂e）")
        current_method = st.session_state.cook_method.get(i, "水煮")
        current_idx = 0 if current_method == "水煮" else 1

        chosen = st.radio(
            " ",
            ["水煮", "煎炸"],
            index=current_idx,
            horizontal=True,
            key=f"cook_choice_{i}",
            label_visibility="collapsed",
        )

        new_method = "水煮" if chosen == "水煮" else "煎炸"
        if new_method != st.session_state.cook_method.get(i, "水煮"):
            st.session_state.cook_method[i] = new_method
            st.session_state.cook_picks[i] = pick_one(df_all, "1-2" if new_method == "水煮" else "1-1")
            st.rerun()

        pick = st.session_state.cook_picks[i]
        st.caption(f"料理耗材：{pick['product_name']}（{pick['cf_kgco2e']:.3f} kgCO₂e）")
        st.divider()

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
        st.session_state.drink_pick = None if drink_mode == "我不喝飲料" else (pick_one(df_all, "2") if len(df_drink) > 0 else None)
        st.rerun()

    if st.session_state.drink_mode_state == "隨機生成飲料" and st.button("🔄 換一杯飲料", use_container_width=True):
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

    # ---- 交通（同你原本邏輯，略，保留）
    st.markdown("### 🧭 採買交通（略）")
    st.caption("這份檔案重點是修 Google Sheet 寫入。交通/地圖段落可用你原本版本。")

    food_sum = float(meal_df["cf_kgco2e"].sum())
    cook_sum = sum(float(st.session_state.cook_picks[i]["cf_kgco2e"]) for i in range(len(meal_df)))
    transport_cf = 0.0  # 你可把原本 transport 計算貼回來
    stage1_total = food_sum + cook_sum + drink_cf + transport_cf

    st.markdown("## ✅ 第一階段結果")
    st.write({"Food": food_sum, "Cooking": cook_sum, "Drink": drink_cf, "Transport": transport_cf, "Total": stage1_total})

    st.markdown("---")
    if st.button("➡️ 進入第二階段：甜點 / 餐具包材", use_container_width=True):
        st.session_state.stage = 2
        st.rerun()


# =========================
# 12) 第二階段：甜點/餐具包材 + 最終 + CSV + Google Sheet
# =========================
if st.session_state.stage == 2:
    st.subheader("🍰 第二階段：甜點與餐具包材")

    meal_df = st.session_state.meal_items.reset_index(drop=True)
    food_sum = float(meal_df["cf_kgco2e"].sum())
    cook_sum = sum(float(st.session_state.cook_picks[i]["cf_kgco2e"]) for i in range(len(meal_df)))

    drink_cf = 0.0
    drink_name = "不喝飲料"
    if st.session_state.drink_mode_state == "隨機生成飲料" and len(df_drink) > 0:
        dp = st.session_state.drink_pick or pick_one(df_all, "2")
        st.session_state.drink_pick = dp
        drink_cf = float(dp["cf_kgco2e"])
        drink_name = dp["product_name"]

    transport_cf = 0.0
    extra_takeout_cf = 0.0

    # 甜點：5 選 2
    dessert_sum = 0.0
    dessert_selected = []
    if len(df_dessert) > 0:
        if st.session_state.dessert_pool is None:
            st.session_state.dessert_pool = safe_sample(df_dessert, 5)
        dessert_pool = st.session_state.dessert_pool.copy()
        options = dessert_pool["product_name"].tolist()
        chosen = st.multiselect("請選 2 種甜點", options=options, default=[x for x in st.session_state.dessert_pick_names if x in options])
        st.session_state.dessert_pick_names = chosen
        dessert_selected = chosen
        if len(chosen) == 2:
            dessert_sum = float(dessert_pool[dessert_pool["product_name"].isin(chosen)]["cf_kgco2e"].sum())
        else:
            st.warning("甜點需選 2 種才會納入計算。")

    # 餐具/包材
    packaging_sum = 0.0
    if len(df_packaging) > 0:
        pk_opts = df_packaging["product_name"].tolist()
        pk_selected = st.multiselect("選擇餐具/包材（可空）", options=pk_opts, default=[x for x in st.session_state.packaging_pick if x in pk_opts])
        st.session_state.packaging_pick = pk_selected
        packaging_sum = float(df_packaging[df_packaging["product_name"].isin(pk_selected)]["cf_kgco2e"].sum()) if pk_selected else 0.0

    total = food_sum + cook_sum + drink_cf + transport_cf + dessert_sum + packaging_sum + extra_takeout_cf
    st.markdown(f"## ✅ 最終碳足跡：**{total:.3f} kgCO₂e**")

    # ---- CSV（個人 + 本機累積）
    student_name = st.session_state.student_name or st.session_state.visitor_id or "未報到"
    row = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "student_name": student_name,
        "visitor_id": st.session_state.visitor_id,
        "device_id": st.session_state.device_id,
        "total_kgco2e": round(total, 6),
        "food_kgco2e": round(food_sum, 6),
        "cooking_kgco2e": round(cook_sum, 6),
        "drink_kgco2e": round(drink_cf, 6),
        "transport_kgco2e": round(transport_cf, 6),
        "dessert_kgco2e": round(dessert_sum, 6),
        "packaging_kgco2e": round(packaging_sum, 6),
        "takeout_kgco2e": round(extra_takeout_cf, 6),
        "drink_name": drink_name,
        "dessert_selected": ", ".join(dessert_selected) if dessert_selected else "",
        "packaging_selected": ", ".join(st.session_state.packaging_pick) if st.session_state.packaging_pick else "",
    }

    col1, col2 = st.columns([1, 1])
    with col1:
        st.download_button(
            "⬇️ 下載我的結果 CSV",
            data=pd.DataFrame([row]).to_csv(index=False).encode("utf-8-sig"),
            file_name=f"{student_name}_carbon_result.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with col2:
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

    # ---- Google Sheet 寫入（可選）
    st.markdown("### 🧾 全班總表（Google Sheet，可選）")
    if sheets_available():
        if st.button("📤 送出並寫入 Google Sheet（全班彙整）", use_container_width=True):
            try:
                append_result_to_google_sheet(row)
                st.success("✅ 已成功寫入 Google Sheet（回去刷新試算表）")
            except Exception as e:
                st.error("寫入失敗：請檢查 ①服務帳戶是否已被共用為「編輯者」 ② spreadsheet_id / worksheet_name 是否正確 ③ Sheets API 是否已啟用。")
                st.exception(e)
    else:
        st.warning("尚未設定 Google Sheet secrets。請在 Streamlit Cloud → App → Settings → Secrets 貼上。")

    st.markdown("---")
    if st.button("↩️ 回到第一階段", use_container_width=True):
        st.session_state.stage = 1
        st.rerun()

