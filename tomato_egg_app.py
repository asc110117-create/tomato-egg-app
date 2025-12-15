# app.py（完整：食材 + 料理 + 飲料 + 採買交通(可點地圖選分店) + 長條圖/圓餅圖）
# ✅ 定位可用：自動抓定位
# ✅ 定位不可用：可用「手動座標」或「地圖點一下當起點」
# ✅ 搜尋附近分店 → 最近 5 家 → 點橘色分店點選擇 → 按確認才加入計算
# ✅ 交通方式：走路/機車/汽車（可算來回）
# ✅ 圖表：長條圖 + 圓餅圖（Altair）
# ⚠️ 需要套件：streamlit, pandas, openpyxl, altair, requests, folium, streamlit-folium, streamlit-geolocation

import re
import random
import math
from io import BytesIO

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
EXCEL_PATH_DEFAULT = "產品碳足跡3.xlsx"

VALID_IDS = {
    "BEE114105黃文瑜": {"name": "文瑜"},
    "BEE114108陳依萱": {"name": "依萱"},
}


# =========================
# 1) 工具：碳足跡字串解析 → kgCO2e
# =========================
def parse_cf_to_kg(value) -> float:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return float("nan")
    if isinstance(value, (int, float)):
        return float(value)

    s = str(value).strip().lower().replace(" ", "")
    s = s.replace("kgco2e", "kg").replace("gco2e", "g")

    if re.fullmatch(r"[-+]?\d*\.?\d+k", s):  # 1.00k -> 1.00kg
        return float(s[:-1])

    m = re.match(r"([-+]?\d*\.?\d+)(kg|g)?$", s)
    if m:
        num = float(m.group(1))
        unit = m.group(2)
        return num / 1000.0 if unit == "g" else num

    m2 = re.search(r"([-+]?\d*\.?\d+)\s*(kg|g)", s)
    if m2:
        num = float(m2.group(1))
        unit = m2.group(2)
        return num / 1000.0 if unit == "g" else num

    m3 = re.search(r"([-+]?\d*\.?\d+)", s)
    return float(m3.group(1)) if m3 else float("nan")


# =========================
# 2) 工具：兩點直線距離（km）
# =========================
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# =========================
# 3) 附近搜尋（OSM Nominatim：以中心點 + bounded）
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
# 4) 讀取 Excel（直接取前 4 欄）
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

    df["cf_kgco2e"] = df["product_carbon_footprint_data"].apply(parse_cf_to_kg)
    df = df.dropna(subset=["cf_kgco2e"]).reset_index(drop=True)
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
        "cf_kgco2e": float(row["cf_kgco2e"]),
        "declared_unit": row["declared_unit"],
    }


# =========================
# 6) Session 初始化
# =========================
st.session_state.setdefault("page", "home")
st.session_state.setdefault("visitor_id", "")

st.session_state.setdefault("meal_items", None)
st.session_state.setdefault("cook_picks", {})
st.session_state.setdefault("cook_method", {})

st.session_state.setdefault("drink_mode_state", "隨機生成飲料")
st.session_state.setdefault("drink_pick", None)

st.session_state.setdefault("stores", [])     # 已確認（只留 1 家）
st.session_state.setdefault("search", [])     # 最近 5 家
st.session_state.setdefault("decision", 0)    # 目前選中 index (0~4)

st.session_state.setdefault("transport_mode", "汽車（汽油）")
st.session_state.setdefault("ef_final", 1.15e-1)
st.session_state.setdefault("round_trip", True)

# ✅ geo 只抓一次
st.session_state.setdefault("geo", None)
# ✅ 起點座標（真正拿來算距離的）
st.session_state.setdefault("origin", {"lat": None, "lng": None})


# =========================
# 7) 定位：嘗試抓一次（拿不到也沒關係，有替代方案）
# =========================
if st.session_state.geo is None:
    # 只呼叫一次；若使用者拒絕，latitude/longitude 會是 None
    st.session_state.geo = streamlit_geolocation()

geo = st.session_state.geo or {}
geo_lat = geo.get("latitude")
geo_lng = geo.get("longitude")
geo_lat = float(geo_lat) if geo_lat is not None else None
geo_lng = float(geo_lng) if geo_lng is not None else None

# 若 origin 還沒設定且 geolocation 有值 → 先用 geolocation 當 origin
if st.session_state.origin["lat"] is None and geo_lat is not None and geo_lng is not None:
    st.session_state.origin = {"lat": geo_lat, "lng": geo_lng}


# =========================
# 8) 母頁
# =========================
st.title(APP_TITLE)

if st.session_state.page == "home":
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("🏷️ 母頁：報到與入場")
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
            st.session_state.page = "main"
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

    vid = st.session_state.visitor_id.strip()
    if vid:
        if vid in VALID_IDS:
            name = VALID_IDS[vid]["name"]
            st.success(f"{name}您好，報到成功 ✅")
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.write(
                f"""
{name}您好，歡迎來到「碳足跡觀光工廠」！

- 抽 3 項食材（主餐）
- 每道餐選擇水煮/煎炸（系統配對油或水）
- 飲料可選（隨機或不喝）
- 採買交通：搜尋附近分店 → 地圖點選一間 → 確認後納入計算
"""
            )
            if st.button("🍴 開始點餐", use_container_width=True):
                st.session_state.page = "main"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.warning("目前此預約號碼不在名單內（可按「直接開始（跳過）」當訪客進入）。")
    st.stop()


# =========================
# 9) 主頁：讀 Excel / 分類
# =========================
df_all = read_excel_source()

df_food = df_all[df_all["code"] == "1"].copy()
df_oil = df_all[df_all["code"] == "1-1"].copy()
df_water = df_all[df_all["code"] == "1-2"].copy()
df_drink = df_all[df_all["code"] == "2"].copy()

if len(df_food) == 0:
    st.error("Excel 裡找不到 code=1 的食材。請確認『編號』欄有 1。")
    st.stop()


# =========================
# 10) 抽食材 / 重置
# =========================
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
    if st.button("♻️ 全部重置", use_container_width=True):
        st.session_state.meal_items = None
        st.session_state.cook_method = {}
        st.session_state.cook_picks = {}
        st.session_state.drink_mode_state = "隨機生成飲料"
        st.session_state.drink_pick = None

        st.session_state.search = []
        st.session_state.stores = []
        st.session_state.decision = 0

        # 不清 geo（避免重複 component），但清 origin 讓使用者重新選
        st.session_state.origin = {"lat": geo_lat, "lng": geo_lng}
        st.rerun()

if st.session_state.meal_items is None:
    st.session_state.meal_items = safe_sample(df_food, 3)
    st.session_state.cook_method = {i: "水煮" for i in range(len(st.session_state.meal_items))}
    st.session_state.cook_picks = {}
    st.session_state.drink_pick = None

meal_df = st.session_state.meal_items.reset_index(drop=True)

st.subheader("🍛 主餐（3 項食材）")
food_table = meal_df[["product_name", "cf_kgco2e", "declared_unit"]].copy()
food_table.columns = ["食材名稱", "食材碳足跡(kgCO₂e)", "宣告單位"]
food_table["食材碳足跡(kgCO₂e)"] = food_table["食材碳足跡(kgCO₂e)"].astype(float).round(3)

st.dataframe(
    food_table.style.apply(
        lambda _: ["background-color: rgba(46, 204, 113, 0.20)"] * food_table.shape[1],
        axis=1,
    ),
    use_container_width=True,
    height=160,
)


# =========================
# 11) 料理方式（每道餐）
# =========================
st.subheader("🍳 選擇調理方式（每道餐各選一次）")

for i in range(len(meal_df)):
    item_name = meal_df.loc[i, "product_name"]
    item_cf = float(meal_df.loc[i, "cf_kgco2e"])

    if i not in st.session_state.cook_picks:
        method = st.session_state.cook_method.get(i, "水煮")
        st.session_state.cook_picks[i] = pick_one(df_all, "1-1" if method == "煎炸" else "1-2")

    pick = st.session_state.cook_picks[i]

    oil_text = "（找不到油品 code=1-1）"
    water_text = "（找不到水品 code=1-2）"
    if len(df_oil) > 0:
        oil_text = f"（{pick['product_name']} / {pick['cf_kgco2e']:.3f}）" if pick["code"] == "1-1" else "（隨機油品）"
    if len(df_water) > 0:
        water_text = f"（{pick['product_name']} / {pick['cf_kgco2e']:.3f}）" if pick["code"] == "1-2" else "（隨機水品）"

    st.markdown(f"**第 {i+1} 道餐：{item_name}**（食材 {item_cf:.3f} kgCO₂e）")

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


# =========================
# 12) 飲料（隨機 or 不喝）
# =========================
st.subheader("🥤 飲料（可選）")

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
# 13) 採買地點與交通碳足跡（定位可用/不可用都能用）
# =========================
st.subheader("🧭 採買地點與交通碳足跡（以你的起點為中心）")
st.caption("若瀏覽器定位被拒絕：請用『手動座標』或『地圖點一下』設定起點。")

# --- 起點設定區 ---
origin_lat = st.session_state.origin["lat"]
origin_lng = st.session_state.origin["lng"]

if origin_lat is not None and origin_lng is not None:
    st.success(f"目前起點：{origin_lat:.6f}, {origin_lng:.6f}")
else:
    st.warning("目前拿不到定位（或尚未設定起點）。請用下方方式設定起點。")

st.markdown("#### ① 手動輸入起點座標（lat/lng）")
colO1, colO2, colO3 = st.columns([1, 1, 1])
with colO1:
    lat_in = st.number_input("緯度 lat", value=float(origin_lat) if origin_lat else 24.1435, format="%.6f")
with colO2:
    lng_in = st.number_input("經度 lng", value=float(origin_lng) if origin_lng else 120.6734, format="%.6f")
with colO3:
    if st.button("✅ 使用此座標當起點", use_container_width=True):
        st.session_state.origin = {"lat": float(lat_in), "lng": float(lng_in)}
        st.rerun()

st.markdown("#### ② 或在地圖上點一下，直接把「點的位置」當起點")
# 讓地圖一定能顯示：若完全沒起點就用台中市中心當預設
fallback_center = [origin_lat if origin_lat else 24.1477, origin_lng if origin_lng else 120.6736]
m_origin = folium.Map(location=fallback_center, zoom_start=13)
folium.Marker(fallback_center, tooltip="目前地圖中心（可點地圖改起點）").add_to(m_origin)
origin_map_state = st_folium(m_origin, height=320, use_container_width=True, key="origin_map")

clicked_origin = origin_map_state.get("last_clicked")
if clicked_origin:
    st.info(f"你點到：{clicked_origin['lat']:.6f}, {clicked_origin['lng']:.6f}")
    if st.button("✅ 將此點設為起點", use_container_width=True):
        st.session_state.origin = {"lat": float(clicked_origin["lat"]), "lng": float(clicked_origin["lng"])}
        st.rerun()

# --- 交通方式 ---
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

# --- 搜尋分店（需要起點） ---
st.markdown("### 🔎 搜尋附近分店（例如：全聯）")
q = st.text_input("搜尋關鍵字", value="全聯", key="place_query")

s1, s2 = st.columns([1, 1])
with s1:
    if st.button("🔍 搜尋附近分店（最近 5 家）", use_container_width=True):
        if st.session_state.origin["lat"] is None or st.session_state.origin["lng"] is None:
            st.error("尚未設定起點，無法搜尋附近分店。請先用上方方式設定起點。")
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
                st.error("搜尋失敗（可能是網路或服務限制）。請換關鍵字或稍後再試。")
                st.exception(e)

with s2:
    if st.button("🧹 清空搜尋結果/已選分店", use_container_width=True):
        st.session_state.search = []
        st.session_state.stores = []
        st.session_state.decision = 0
        st.rerun()


# --- 地圖（可點橘色分店 marker 選） ---
st.markdown("### 🗺️ 地圖（點橘色分店點即可選）")

transport_cf = 0.0
transport_km = 0.0

if st.session_state.origin["lat"] is None or st.session_state.origin["lng"] is None:
    st.warning("尚未設定起點，因此目前無法顯示附近分店地圖。")
else:
    o_lat = st.session_state.origin["lat"]
    o_lng = st.session_state.origin["lng"]

    m = folium.Map(location=[o_lat, o_lng], zoom_start=14)
    folium.Marker([o_lat, o_lng], tooltip="起點（你的位置/你設定的點）", icon=folium.Icon(color="blue", icon="user")).add_to(m)

    # 已確認的分店（綠色）
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

    st.markdown("### 🧠 做決策：點地圖選 1 家 → 再按確認加入計算")

    if not st.session_state.search:
        st.warning("尚未搜尋到附近分店。請先按『搜尋附近分店（最近 5 家）』。")
    else:
        clicked = map_state.get("last_object_clicked")  # marker 點擊
        if clicked:
            ci, cd = nearest_store_index(clicked["lat"], clicked["lng"], st.session_state.search)
            # 閾值：避免點空白也亂選
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

        if st.button("✅ 確認此分店（加入採買點並納入計算）", use_container_width=True):
            st.session_state.stores = [picked]  # 只保留 1 家做決策
            st.success("已確認分店，已納入交通碳足跡計算。")
            st.rerun()

        st.caption("提示：請點橘色分店標記附近；若點空白處不會改變選擇。")

    # 若已確認分店 → 立刻算交通
    if st.session_state.stores:
        picked = st.session_state.stores[0]
        one_way = haversine_km(o_lat, o_lng, picked["lat"], picked["lng"])
        transport_km = one_way * (2 if round_trip else 1)
        transport_cf = transport_km * ef


# =========================
# 14) 組合表格 + 加總
# =========================
rows = []
food_sum = 0.0
cook_sum = 0.0

for i in range(len(meal_df)):
    food_name = meal_df.loc[i, "product_name"]
    food_cf_i = float(meal_df.loc[i, "cf_kgco2e"])
    food_unit_i = str(meal_df.loc[i, "declared_unit"])

    method = st.session_state.cook_method.get(i, "水煮")
    pick = st.session_state.cook_picks.get(i)

    cook_type = "水品" if method == "水煮" else "油品"
    pick_name = pick["product_name"] if pick else "（未抽到）"
    pick_cf = float(pick["cf_kgco2e"]) if pick else 0.0
    pick_unit = pick["declared_unit"] if pick else ""

    food_sum += food_cf_i
    cook_sum += pick_cf

    rows.append(
        {
            "食材名稱": food_name,
            "食材碳足跡(kgCO₂e)": round(food_cf_i, 3),
            "宣告單位": food_unit_i,
            "料理方式": method,
            "油/水類型": cook_type,
            "油/水名稱": pick_name,
            "油/水碳足跡(kgCO₂e)": round(pick_cf, 3),
            "油/水宣告單位": pick_unit,
        }
    )

combo_df = pd.DataFrame(rows)

def style_combo(df_):
    food_cols = ["食材名稱", "食材碳足跡(kgCO₂e)", "宣告單位"]
    def row_style(_row):
        return ["background-color: rgba(46, 204, 113, 0.18)" if c in food_cols else "" for c in df_.columns]
    return df_.style.apply(row_style, axis=1)

st.subheader("📋 本餐組合（表格即時更新）")
st.dataframe(style_combo(combo_df), use_container_width=True, height=220)

total = food_sum + cook_sum + drink_cf + transport_cf

st.subheader("✅ 碳足跡加總（sum）")
st.markdown(
    f"""
- **食材合計**：`{food_sum:.3f}` kgCO₂e  
- **料理方式（油/水）合計**：`{cook_sum:.3f}` kgCO₂e  
- **飲料**：`{drink_cf:.3f}` kgCO₂e（{drink_name}）  
- **交通（採買）合計**：`{transport_cf:.3f}` kgCO₂e（{st.session_state.get("transport_mode","-")}；{'來回' if st.session_state.get("round_trip", True) else '單程'}；{transport_km:.2f} km）  
- **總計**：✅ **`{total:.3f}` kgCO₂e**
"""
)

# =========================
# 15) 圖表（長條圖 + 圓餅圖）
# =========================
st.subheader("📊 圖表（選項一改就更新）")

chart_data = pd.DataFrame(
    [
        {"項目": "Food", "kgCO2e": food_sum},
        {"項目": "Cooking", "kgCO2e": cook_sum},
        {"項目": "Drink", "kgCO2e": drink_cf},
        {"項目": "Transport", "kgCO2e": transport_cf},
    ]
)

bar = (
    alt.Chart(chart_data)
    .mark_bar()
    .encode(
        y=alt.Y("項目:N", sort="-x", title=""),
        x=alt.X("kgCO2e:Q", title="kgCO₂e"),
        tooltip=["項目", alt.Tooltip("kgCO2e:Q", format=".3f")],
    )
    .properties(height=170)
)
st.altair_chart(bar, use_container_width=True)

pie = (
    alt.Chart(chart_data[chart_data["kgCO2e"] > 0])
    .mark_arc()
    .encode(
        theta=alt.Theta("kgCO2e:Q"),
        color=alt.Color("項目:N", legend=alt.Legend(orient="right", title="")),
        tooltip=["項目", alt.Tooltip("kgCO2e:Q", format=".3f")],
    )
    .properties(height=240)
)
st.altair_chart(pie, use_container_width=True)

st.caption("圖表分類用英文（Food/Cooking/Drink/Transport）避免中文缺字。")

if st.session_state.stage == "dessert":
    st.divider()
    st.subheader("🍰 今日甜點與餐具選擇")

    # ========= 甜點：抽 3 選 2 =========
    df_dessert = df_all[df_all["code"] == "3"].copy()

    if len(df_dessert) < 3:
        st.error("甜點資料不足（code=3 至少需要 3 筆）")
        st.stop()

    # 第一次進來才抽
    if "dessert_pool" not in st.session_state:
        st.session_state.dessert_pool = df_dessert.sample(3).reset_index(drop=True)

    dessert_pool = st.session_state.dessert_pool

    st.markdown("### 🎲 今日甜點（請從 3 種中選 2 種）")

    dessert_choices = st.multiselect(
        "請選擇 2 種甜點",
        options=dessert_pool.index.tolist(),
        format_func=lambda i: f"{dessert_pool.loc[i,'product_name']}（{dessert_pool.loc[i,'cf_kgco2e']:.3f} kgCO₂e）",
        max_selections=2,
    )

    dessert_cf = 0.0
    if len(dessert_choices) == 2:
        dessert_cf = dessert_pool.loc[dessert_choices, "cf_kgco2e"].sum()
        st.success(f"甜點碳足跡小計：**{dessert_cf:.3f} kgCO₂e**")
    else:
        st.warning("請務必選擇 2 種甜點")

    # ========= 餐具 / 包材（可複選，可不選） =========
    st.markdown("### 🍴 餐具／包材（可不選，可複選）")

    df_utensil = df_all[df_all["code"].astype(str).str.startswith("4-")].copy()

    utensil_map = {
        row["product_name"]: row["cf_kgco2e"]
        for _, row in df_utensil.iterrows()
    }

    selected_utensils = st.multiselect(
        "請選擇使用的餐具／包材",
        list(utensil_map.keys()),
    )

    utensil_cf = sum(utensil_map[u] for u in selected_utensils)

    if selected_utensils:
        st.info(f"餐具碳足跡小計：**{utensil_cf:.3f} kgCO₂e**")
    else:
        st.caption("未使用餐具／包材")

    # ========= 內用 / 帶回 =========
    st.markdown("### 🏫 內用或帶回")

    eat_mode = st.radio(
        "請選擇方式",
        ["內用", "帶回國立臺中教育大學"],
        horizontal=True,
    )

    dessert_transport_cf = 0.0

    if eat_mode == "內用":
        st.success("內用：不增加交通碳足跡")

    else:
        st.warning("帶回將計算一次交通碳足跡")

        # 台中教育大學（固定）
        NTCU_LAT = 24.1437
        NTCU_LNG = 120.6736

        origin = st.session_state.origin
        o_lat, o_lng = origin["lat"], origin["lng"]

        one_way = haversine_km(o_lat, o_lng, NTCU_LAT, NTCU_LNG)
        rt = bool(st.session_state.get("round_trip", True))
        ef = float(st.session_state.get("ef_final", 0.0))

        trip_km = one_way * (2 if rt else 1)
        dessert_transport_cf = trip_km * ef

        st.info(
            f"""
📍 甜點帶回路線  
- 單程距離：約 **{one_way:.2f} km**  
- {'來回' if rt else '單程'}里程：約 **{trip_km:.2f} km**  
- 交通碳足跡：**{dessert_transport_cf:.3f} kgCO₂e**
"""
        )

    # ========= 最終加總 =========
    if len(dessert_choices) == 2:
        final_total = total + dessert_cf + utensil_cf + dessert_transport_cf

        st.divider()
        st.subheader("🍽️ 含甜點的最終碳足跡")

        st.markdown(
            f"""
- 原本餐點總計：`{total:.3f}` kgCO₂e  
- 甜點：`{dessert_cf:.3f}` kgCO₂e  
- 餐具／包材：`{utensil_cf:.3f}` kgCO₂e  
- 甜點交通：`{dessert_transport_cf:.3f}` kgCO₂e  

### ✅ **最終總碳足跡：{final_total:.3f} kgCO₂e**
"""
        )
