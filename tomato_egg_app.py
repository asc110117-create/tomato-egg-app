# app.py (修正版：避免 sample(3) 因資料不足或 code 型別不一致而炸)
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
# 基本設定
# =========================
st.set_page_config(
    page_title="一餐的碳足跡大冒險：從農場到你的胃",
    page_icon="🍽️",
    layout="centered",
)

st.markdown("""
<style>
.block-container { padding-top: 1.2rem; padding-bottom: 2rem; }
.card { padding: 14px; border-radius: 14px; border: 1px solid rgba(255,255,255,0.15); background: rgba(255,255,255,0.03); }
.small-note { opacity: 0.85; font-size: 0.92rem; }
</style>
""", unsafe_allow_html=True)

APP_TITLE = "🍽️ 一餐的碳足跡大冒險：從農場到你的胃"
EXCEL_PATH = "產品碳足跡3.xlsx"


# =========================
# 工具：碳足跡字串 → kgCO2e
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
# 工具：距離（km）
# =========================
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# =========================
# 附近搜尋（Nominatim）
# =========================
def nominatim_search_nearby(query, lat, lng, radius_km=5, limit=30):
    if not query.strip():
        return []

    lat_delta = radius_km / 111.0
    lng_delta = radius_km / (111.0 * max(0.1, math.cos(math.radians(lat))))

    params = {
        "q": query,
        "format": "jsonv2",
        "limit": str(limit),
        # left,top,right,bottom
        "viewbox": f"{lng-lng_delta},{lat+lat_delta},{lng+lng_delta},{lat-lat_delta}",
        "bounded": 1,
        "addressdetails": 1,
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
        out.append(
            {
                "display_name": x.get("display_name", ""),
                "name": (x.get("display_name", "").split(",")[0] or "").strip(),
                "lat": float(x["lat"]),
                "lng": float(x["lon"]),
            }
        )
    return out


# =========================
# 讀 Excel：前 4 欄
# =========================
@st.cache_data(show_spinner=False)
def load_data():
    df = pd.read_excel(EXCEL_PATH, engine="openpyxl")

    if df.shape[1] < 4:
        raise ValueError("Excel 欄位太少：至少要 4 欄（編號、品名、碳足跡、宣告單位）。")

    df = df.iloc[:, :4].copy()
    df.columns = ["code", "name", "cf_raw", "unit"]

    # ✅ 關鍵：code 強制字串化 + 去空白 + 去掉 .0（避免 1.0 變成 '1.0'）
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
    """
    df_sub 筆數不足 n：就抽全部（不報錯）
    df_sub 為空：回傳空 DF
    """
    if len(df_sub) == 0:
        return df_sub.copy()
    n2 = min(n, len(df_sub))
    return df_sub.sample(n=n2, replace=False, random_state=seed).reset_index(drop=True)


df = load_data()


# =========================
# Session
# =========================
st.session_state.setdefault("meal", None)
st.session_state.setdefault("stores", [])        # 已確認加入的採買點（只留 1 家也可以）
st.session_state.setdefault("search", [])        # 最近 5 家搜尋結果
st.session_state.setdefault("decision", 0)       # radio index


# =========================
# 主標題
# =========================
st.title(APP_TITLE)

# 🔎 除錯資訊（你需要就打開）
with st.expander("（除錯）目前 Excel code 分布", expanded=False):
    st.write(df["code"].value_counts(dropna=False))


# =========================
# 抽食材（修正：不足 3 也不會炸）
# =========================
st.subheader("🍛 主餐（抽 3 項食材）")

food_pool = df[df["code"] == "1"].copy()

if st.button("🎲 抽 3 項食材", use_container_width=True):
    st.session_state.meal = safe_sample(food_pool, 3, seed=random.randint(1, 10_000))

if st.session_state.meal is None:
    st.session_state.meal = safe_sample(food_pool, 3, seed=42)

if len(food_pool) == 0:
    st.error("Excel 找不到 code=1 的食材資料。請確認『編號』欄中有 1。")
    st.stop()

meal = st.session_state.meal
if len(meal) < 3:
    st.warning(f"食材資料筆數不足 3（目前只有 {len(food_pool)} 筆可用），已改為抽取 {len(meal)} 筆。")

st.dataframe(meal[["name", "cf", "unit"]], use_container_width=True)


# =========================
# 採買地點與交通碳足跡（以定位為中心 → 最近 5 家 → 做決策）
# =========================
st.subheader("🧭 採買地點與交通碳足跡（以你的定位為中心）")
st.caption("搜尋後只顯示『你附近』的分店，並依距離排序取最近 5 家。你必須做決策（選 1 家）再按確認才加入計算。")

loc = streamlit_geolocation()
if not loc or not loc.get("latitude") or not loc.get("longitude"):
    st.warning("請允許瀏覽器定位權限，才能搜尋你附近的分店與計算距離。")
else:
    u_lat = float(loc["latitude"])
    u_lng = float(loc["longitude"])
    st.success(f"你的位置：{u_lat:.6f}, {u_lng:.6f}")

    ef = st.number_input("交通排放係數（kgCO₂e/km）", min_value=0.0, value=0.115, step=0.01)
    round_trip = st.checkbox("算來回（去＋回）", value=True)

    q = st.text_input("搜尋店名/地點（例如：全聯）", value="全聯")

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("🔍 搜尋附近分店（最近 5 家）", use_container_width=True):
            try:
                raw = nominatim_search_nearby(q, u_lat, u_lng, radius_km=5, limit=50)
                # 若 5km 不夠，放到 10km
                if len(raw) < 5:
                    raw = nominatim_search_nearby(q, u_lat, u_lng, radius_km=10, limit=50)

                results = []
                for r in raw:
                    d = haversine_km(u_lat, u_lng, r["lat"], r["lng"])
                    rr = dict(r)
                    rr["dist_km"] = d
                    results.append(rr)

                results.sort(key=lambda x: x["dist_km"])
                st.session_state.search = results[:5]
                st.session_state.decision = 0
            except Exception as e:
                st.session_state.search = []
                st.session_state.decision = 0
                st.error("搜尋失敗，請稍後再試或換關鍵字。")
                st.exception(e)
            st.rerun()

    with col2:
        if st.button("🧹 清空搜尋結果/已選分店", use_container_width=True):
            st.session_state.search = []
            st.session_state.stores = []
            st.session_state.decision = 0
            st.rerun()

    # 地圖：藍=你，橘=最近 5 家（1~5），綠=已確認加入
    m = folium.Map(location=[u_lat, u_lng], zoom_start=14)

    folium.Marker([u_lat, u_lng], tooltip="你的位置", icon=folium.Icon(color="blue", icon="user")).add_to(m)

    for p in st.session_state.stores:
        folium.Marker(
            [p["lat"], p["lng"]],
            tooltip=f"已選：{p['name']}",
            popup=p.get("display_name", p["name"]),
            icon=folium.Icon(color="green", icon="shopping-cart"),
        ).add_to(m)

    bounds = [[u_lat, u_lng]]
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

    st.caption(f"目前顯示分店數：{len(st.session_state.search)}（以你的位置為中心）")
    st_folium(m, height=420, use_container_width=True)

    # 決策：選哪一家（不自動加入）
    st.markdown("### 🧠 做決策：你要去哪一家？")
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

        trip_km = picked["dist_km"] * (2 if round_trip else 1)
        trip_cf = trip_km * float(ef)

        st.info(
            f"你目前選擇：**{picked['name']}**\n\n"
            f"- 單程距離：約 **{picked['dist_km']:.2f} km**\n"
            f"- 里程（{'來回' if round_trip else '單程'}）：約 **{trip_km:.2f} km**\n"
            f"- 交通碳足跡：約 **{trip_cf:.3f} kgCO₂e**"
        )

        if st.button("✅ 確認此分店（加入採買點並納入計算）", use_container_width=True):
            # 只保留 1 家（你要做決策就是挑 1 家）；若想多家可改 append
            st.session_state.stores = [picked]
            st.success("已加入採買點。")
            st.rerun()
    else:
        st.warning("尚未搜尋到附近分店。請先按『搜尋附近分店』。")


# =========================
# 加總（示範：食材 + 交通）
# =========================
food_cf = float(meal["cf"].sum()) if len(meal) else 0.0
transport_cf = 0.0

if loc and st.session_state.stores:
    picked = st.session_state.stores[0]
    one_way = haversine_km(float(loc["latitude"]), float(loc["longitude"]), picked["lat"], picked["lng"])
    # 這裡用預設 0.115（若你要跟上面 ef 同步，可把 ef 存 session_state）
    transport_cf = one_way * 2 * 0.115

total = food_cf + transport_cf

st.subheader("✅ 碳足跡加總（示範）")
st.write(f"食材合計：{food_cf:.3f} kgCO₂e")
st.write(f"交通合計：{transport_cf:.3f} kgCO₂e")
st.success(f"總計：{total:.3f} kgCO₂e")
