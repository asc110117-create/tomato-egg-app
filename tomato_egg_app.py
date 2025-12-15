# app.py（完整可直接用）
# ✅ 以使用者定位為中心搜尋附近分店（先 5km 不足再 10km）→ 顯示最近 5 家（1~5）
# ✅ 使用者做決策（radio）→ 按確認才加入採買點
# ✅ 交通方式：走路 / 機車 / 汽車（顯示「來回」checkbox；走路係數=0）
# ✅ 修正：Excel code 型別不一致導致 sample(3) 失敗（強制 code 字串化 + safe_sample）

import re
import random
import math

import pandas as pd
import streamlit as st
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
EXCEL_PATH = "產品碳足跡3.xlsx"


# =========================
# 1) 工具：碳足跡字串 → kgCO2e
# =========================
def parse_cf_to_kg(value) -> float:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return float("nan")

    if isinstance(value, (int, float)):
        return float(value)

    s = str(value).strip().lower().replace(" ", "")
    s = s.replace("kgco2e", "kg").replace("gco2e", "g")

    # 1.00k -> 1.00kg
    if re.fullmatch(r"[-+]?\d*\.?\d+k", s):
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
    if m3:
        return float(m3.group(1))

    return float("nan")


# =========================
# 2) 工具：距離（km）Haversine
# =========================
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# =========================
# 3) 工具：附近搜尋（OSM Nominatim，強制只回傳定位附近）
# =========================
def nominatim_search_nearby(query, lat, lng, radius_km=5, limit=50):
    if not query.strip():
        return []

    lat_delta = radius_km / 111.0
    lng_delta = radius_km / (111.0 * max(0.1, math.cos(math.radians(lat))))

    # viewbox: left,top,right,bottom（經度在前）
    viewbox = f"{lng-lng_delta},{lat+lat_delta},{lng+lng_delta},{lat-lat_delta}"

    params = {
        "q": query,
        "format": "jsonv2",
        "limit": str(limit),
        "addressdetails": 1,
        "viewbox": viewbox,
        "bounded": 1,  # ✅ 只回傳 viewbox 範圍內
    }
    headers = {
        # Nominatim 要求清楚的 User-Agent（你可改成你的專案）
        "User-Agent": "carbon-footprint-edu-app/1.0",
        "Accept-Language": "zh-TW,zh,en",
    }

    r = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params=params,
        headers=headers,
        timeout=10,
    )
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
# 4) 讀 Excel（前 4 欄：編號 / 品名 / 碳足跡 / 宣告單位）
# =========================
@st.cache_data(show_spinner=False)
def load_data():
    df = pd.read_excel(EXCEL_PATH, engine="openpyxl")

    if df.shape[1] < 4:
        raise ValueError("Excel 欄位太少：至少需要 4 欄（編號、品名、碳足跡、宣告單位）。")

    df = df.iloc[:, :4].copy()
    df.columns = ["code", "name", "cf_raw", "unit"]

    # ✅ 關鍵：code 統一成字串，且把 '1.0' 變成 '1'
    df["code"] = (
        df["code"]
        .astype(str)
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
    )

    df["name"] = df["name"].astype(str).str.strip()
    df["unit"] = df["unit"].astype(str).str.strip()
    df["cf"] = df["cf_raw"].apply(parse_cf_to_kg)

    df = df.dropna(subset=["cf"]).reset_index(drop=True)
    return df


def safe_sample(df_sub: pd.DataFrame, n: int, seed=None) -> pd.DataFrame:
    if len(df_sub) == 0:
        return df_sub.copy()
    n2 = min(n, len(df_sub))
    return df_sub.sample(n=n2, replace=False, random_state=seed).reset_index(drop=True)


# =========================
# 5) 初始化
# =========================
st.title(APP_TITLE)

try:
    df = load_data()
except Exception as e:
    st.error("讀取 Excel 失敗：請確認 產品碳足跡3.xlsx 在專案根目錄，且至少 4 欄（編號/品名/碳足跡/宣告單位）。")
    st.exception(e)
    st.stop()

# session
st.session_state.setdefault("meal", None)         # 主餐抽到的食材
st.session_state.setdefault("stores", [])         # 已「確認」加入的採買點（只保留 1 家）
st.session_state.setdefault("search", [])         # 搜尋到的最近 5 家（橘點）
st.session_state.setdefault("decision", 0)        # radio index
st.session_state.setdefault("transport_mode", "汽車（汽油）")
st.session_state.setdefault("round_trip", True)
st.session_state.setdefault("ef_final", 0.115)


# =========================
# 6)（可選）除錯：看 code 分布
# =========================
with st.expander("（除錯）目前 Excel code 分布", expanded=False):
    st.write(df["code"].value_counts(dropna=False))


# =========================
# 7) 主餐：抽 3 項食材
# =========================
st.subheader("🍛 主餐（抽 3 項食材）")

food_pool = df[df["code"] == "1"].copy()
if len(food_pool) == 0:
    st.error("Excel 找不到 code=1 的食材資料。請確認『編號』欄中有 1。")
    st.stop()

c1, c2 = st.columns([1, 1])
with c1:
    if st.button("🎲 抽 3 項食材", use_container_width=True):
        st.session_state.meal = safe_sample(food_pool, 3, seed=random.randint(1, 10_000))
with c2:
    if st.button("♻️ 全部重置", use_container_width=True):
        st.session_state.meal = None
        st.session_state.search = []
        st.session_state.stores = []
        st.session_state.decision = 0
        st.rerun()

if st.session_state.meal is None:
    st.session_state.meal = safe_sample(food_pool, 3, seed=42)

meal = st.session_state.meal
if len(meal) < 3:
    st.warning(f"食材筆數不足 3（目前池子只有 {len(food_pool)} 筆），已改為抽取 {len(meal)} 筆。")

st.dataframe(meal[["name", "cf", "unit"]], use_container_width=True)


# =========================
# 8) 採買地點與交通碳足跡（你要的重點）
# =========================
st.subheader("🧭 採買地點與交通碳足跡（以你的定位為中心）")
st.caption("搜尋後只顯示『你附近』的分店，依距離排序取最近 5 家。你必須做決策（選 1 家）再按確認才加入計算。")

loc = streamlit_geolocation()
if not loc or not loc.get("latitude") or not loc.get("longitude"):
    st.warning("請允許瀏覽器定位權限，才能搜尋你附近的分店與計算距離。")
    user_lat = user_lng = None
else:
    user_lat = float(loc["latitude"])
    user_lng = float(loc["longitude"])
    st.success(f"你的位置：{user_lat:.6f}, {user_lng:.6f}")

# 交通方式（含你給的係數；走路=0）
EF_MAP = {
    "走路": 0.0,
    "機車": 9.51e-2,          # 0.0951 kgCO2e/km
    "汽車（汽油）": 1.15e-1,   # 0.115 kgCO2e/km
}

if user_lat is not None:
    colA, colB, colC = st.columns([1.1, 1.2, 1.0])

    with colA:
        transport_mode = st.selectbox(
            "交通方式",
            list(EF_MAP.keys()),
            index=list(EF_MAP.keys()).index(st.session_state.get("transport_mode", "汽車（汽油）")),
            key="transport_mode",
        )

    with colB:
        # 走路鎖 0；其他可微調
        if EF_MAP[transport_mode] == 0.0:
            ef = st.number_input(
                "排放係數（kgCO₂e/km）",
                min_value=0.0,
                value=0.0,
                step=0.01,
                disabled=True,
                key="ef_locked_walk",
            )
        else:
            ef = st.number_input(
                "排放係數（kgCO₂e/km，可微調）",
                min_value=0.0,
                value=float(EF_MAP[transport_mode]),
                step=0.01,
                key="ef_by_mode",
            )

    with colC:
        round_trip = st.checkbox("算來回（去＋回）", value=bool(st.session_state.get("round_trip", True)), key="round_trip")

    # 統一存一個係數（給「決策即時顯示」與「最後加總」使用）
    st.session_state["ef_final"] = float(ef)
    st.session_state["round_trip"] = bool(round_trip)

    st.markdown("### 🔎 搜尋附近分店（例如：全聯）")
    q = st.text_input("搜尋關鍵字", value="全聯", key="place_query")

    s1, s2 = st.columns([1, 1])
    with s1:
        if st.button("🔍 搜尋附近分店（最近 5 家）", use_container_width=True):
            try:
                raw = nominatim_search_nearby(q, user_lat, user_lng, radius_km=5, limit=60)
                if len(raw) < 5:
                    raw = nominatim_search_nearby(q, user_lat, user_lng, radius_km=10, limit=60)

                results = []
                for r in raw:
                    d = haversine_km(user_lat, user_lng, r["lat"], r["lng"])
                    rr = dict(r)
                    rr["dist_km"] = d
                    results.append(rr)

                results.sort(key=lambda x: x["dist_km"])
                st.session_state.search = results[:5]
                st.session_state.decision = 0
            except Exception as e:
                st.session_state.search = []
                st.session_state.decision = 0
                st.error("搜尋失敗（可能是網路或服務限制）。請換關鍵字或稍後再試。")
                st.exception(e)
            st.rerun()

    with s2:
        if st.button("🧹 清空搜尋結果/已選分店", use_container_width=True):
            st.session_state.search = []
            st.session_state.stores = []
            st.session_state.decision = 0
            st.rerun()

    # 地圖：藍=你，橘=搜尋結果（1~5），綠=已確認加入
    st.markdown("### 🗺️ 地圖（最近 5 家分店：1～5）")

    m = folium.Map(location=[user_lat, user_lng], zoom_start=14)
    folium.Marker(
        [user_lat, user_lng],
        tooltip="你的位置",
        icon=folium.Icon(color="blue", icon="user"),
    ).add_to(m)

    for p in st.session_state.stores:
        folium.Marker(
            [p["lat"], p["lng"]],
            tooltip=f"已選：{p['name']}",
            popup=p.get("display_name", p["name"]),
            icon=folium.Icon(color="green", icon="shopping-cart"),
        ).add_to(m)

    bounds = [[user_lat, user_lng]]
    for i, r in enumerate(st.session_state.search, start=1):
        bounds.append([r["lat"], r["lng"]])

        folium.Marker(
            [r["lat"], r["lng"]],
            tooltip=f"{i}. {r['name']}（{r['dist_km']:.2f} km）",
            popup=r["display_name"],
            icon=folium.Icon(color="orange", icon="info-sign"),
        ).add_to(m)

        # 編號貼紙
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

    st.caption(f"目前顯示分店數：{len(st.session_state.search)}（以你的位置為中心）")
    st_folium(m, height=420, use_container_width=True)

    # 決策：選 1 家，按確認才加入
    st.markdown("### 🧠 做決策：你要去哪一家？（選 1 家再確認）")

    if st.session_state.search:
        options = []
        for i, r in enumerate(st.session_state.search, start=1):
            options.append(f"{i}. {r['name']}（約 {r['dist_km']:.2f} km）")

        chosen = st.radio(
            "請選擇一個你『實際會去』的分店",
            options,
            index=int(st.session_state.decision),
            key="decision_radio",
        )

        idx = int(chosen.split(".")[0]) - 1
        st.session_state.decision = idx
        picked = st.session_state.search[idx]

        trip_km = picked["dist_km"] * (2 if st.session_state["round_trip"] else 1)
        trip_cf = trip_km * float(st.session_state["ef_final"])

        st.info(
            f"你目前選擇：**{picked['name']}**\n\n"
            f"- 單程距離：約 **{picked['dist_km']:.2f} km**\n"
            f"- 里程（{'來回' if st.session_state['round_trip'] else '單程'}）：約 **{trip_km:.2f} km**\n"
            f"- 交通方式：**{st.session_state['transport_mode']}**\n"
            f"- 排放係數：**{st.session_state['ef_final']:.4f} kgCO₂e/km**\n"
            f"- 交通碳足跡：約 **{trip_cf:.3f} kgCO₂e**"
        )

        if st.button("✅ 確認此分店（加入採買點並納入計算）", use_container_width=True):
            # 只保留 1 家（決策式）
            st.session_state.stores = [picked]
            st.success("已加入採買點（綠色）。")
            st.rerun()
    else:
        st.warning("尚未搜尋到附近分店。請先按『搜尋附近分店（最近 5 家）』。")


# =========================
# 9) 最終加總（示範：食材 + 交通）
# =========================
food_cf = float(meal["cf"].sum()) if len(meal) else 0.0

transport_cf = 0.0
if user_lat is not None and st.session_state.stores:
    picked = st.session_state.stores[0]
    one_way = haversine_km(user_lat, user_lng, picked["lat"], picked["lng"])
    trip_km = one_way * (2 if st.session_state.get("round_trip", True) else 1)
    transport_cf = trip_km * float(st.session_state.get("ef_final", 0.0))

total = food_cf + transport_cf

st.subheader("✅ 碳足跡加總（sum）")
st.write(f"食材合計：**{food_cf:.3f} kgCO₂e**")
st.write(f"交通合計：**{transport_cf:.3f} kgCO₂e**（{st.session_state.get('transport_mode','-')}；{'來回' if st.session_state.get('round_trip', True) else '單程'}）")
st.success(f"總計：✅ **{total:.3f} kgCO₂e**")
