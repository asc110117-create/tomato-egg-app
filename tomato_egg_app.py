# app.py
# ✅ 一餐的碳足跡大冒險：從農場到你的胃
# ✅ 新增：搜尋「全聯」等關鍵字 → 地圖顯示最近 5 個分店（1~5 編號）→ 使用者做決策（radio）→ 按「確認」才加入採買點並計算交通碳足跡
#
# 依賴套件（requirements.txt 建議）
# streamlit
# pandas
# openpyxl
# altair
# requests
# folium
# streamlit-folium
# streamlit-geolocation

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
  border: 1px solid rgba(255,255,255,0.10);
  background: rgba(255,255,255,0.03);
}
.small-note { opacity: 0.8; font-size: 0.92rem; }
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
# 1) 工具：碳足跡字串解析 -> kgCO2e
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

    # number + optional unit
    m = re.match(r"([-+]?\d*\.?\d+)(kg|g)?$", s)
    if m:
        num = float(m.group(1))
        unit = m.group(2)
        return num / 1000.0 if unit == "g" else num

    # embedded unit
    m2 = re.search(r"([-+]?\d*\.?\d+)\s*(kg|g)", s)
    if m2:
        num = float(m2.group(1))
        unit = m2.group(2)
        return num / 1000.0 if unit == "g" else num

    # fallback first number as kg
    m3 = re.search(r"([-+]?\d*\.?\d+)", s)
    if m3:
        return float(m3.group(1))

    raise ValueError(f"無法解析碳足跡數值：{value}")


# =========================
# 1-2) 工具：兩點直線距離（km）
# =========================
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# =========================
# 1-3) 工具：地點搜尋（OSM Nominatim）
# =========================
def nominatim_search(query: str, limit: int = 25):
    if not query.strip():
        return []

    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": query,
        "format": "jsonv2",
        "limit": str(limit),
        "addressdetails": 1,
    }
    headers = {
        # Nominatim 需要清楚的 User-Agent（請改成你的專案資訊）
        "User-Agent": "carbon-footprint-streamlit-app/1.0 (contact: your-project)",
        "Accept-Language": "zh-TW,zh,en",
    }
    r = requests.get(url, params=params, headers=headers, timeout=10)
    r.raise_for_status()
    data = r.json()

    out = []
    for x in data:
        out.append(
            {
                "display_name": x.get("display_name", ""),
                "lat": float(x["lat"]),
                "lng": float(x["lon"]),
                "category": x.get("category", ""),
                "type": x.get("type", ""),
            }
        )
    return out


# =========================
# 2) 讀取 Excel：前 4 欄 -> code/name/cf/unit
# =========================
@st.cache_data(show_spinner=False)
def load_data_from_excel(file_bytes: bytes, filename: str) -> pd.DataFrame:
    df = pd.read_excel(BytesIO(file_bytes), engine="openpyxl")

    if df.shape[1] < 4:
        raise ValueError(
            f"Excel 欄位太少（目前 {df.shape[1]} 欄）。至少需要 4 欄：編號、品名、碳足跡、宣告單位。"
        )

    cols = list(df.columns[:4])
    df = df[cols].copy()
    df.columns = ["code", "product_name", "product_carbon_footprint_data", "declared_unit"]

    df["code"] = df["code"].astype(str).str.strip()
    df["product_name"] = df["product_name"].astype(str).str.strip()
    df["declared_unit"] = df["declared_unit"].astype(str).str.strip()
    df["cf_kgco2e"] = df["product_carbon_footprint_data"].apply(parse_cf_to_kg)

    df = df.dropna(subset=["cf_kgco2e"]).reset_index(drop=True)
    return df


def read_excel_source() -> pd.DataFrame:
    st.caption("📄 資料來源：優先讀取專案根目錄的 Excel；若讀不到可改用上傳。")

    try:
        with open(EXCEL_PATH_DEFAULT, "rb") as f:
            file_bytes = f.read()
        return load_data_from_excel(file_bytes, EXCEL_PATH_DEFAULT)
    except Exception:
        pass

    up = st.file_uploader("或改用上傳 Excel（.xlsx）", type=["xlsx"])
    if up is None:
        raise FileNotFoundError(f"讀取失敗：請確認 {EXCEL_PATH_DEFAULT} 放在 repo 根目錄，或改用上傳。")
    return load_data_from_excel(up.getvalue(), up.name)


# =========================
# 3) 隨機抽題
# =========================
def sample_rows(df: pd.DataFrame, code_value: str, n: int) -> pd.DataFrame:
    sub = df[df["code"] == code_value].copy()
    if len(sub) == 0:
        raise ValueError(f"在 Excel 中找不到 code = {code_value} 的資料。")
    n = min(n, len(sub))
    return sub.sample(n=n, replace=False, random_state=random.randint(1, 10_000)).reset_index(drop=True)


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
# 4) Session 初始化
# =========================
if "page" not in st.session_state:
    st.session_state.page = "home"

if "visitor_id" not in st.session_state:
    st.session_state.visitor_id = ""

if "meal_items" not in st.session_state:
    st.session_state.meal_items = None

if "cook_picks" not in st.session_state:
    st.session_state.cook_picks = {}

if "cook_method" not in st.session_state:
    st.session_state.cook_method = {}

if "drink_mode" not in st.session_state:
    st.session_state.drink_mode = "隨機生成飲料"

if "drink_pick" not in st.session_state:
    st.session_state.drink_pick = None

# 採買點（已加入、會納入交通計算）
if "store_points" not in st.session_state:
    st.session_state.store_points = []  # [{"name":..., "lat":..., "lng":...}]

# 搜尋出來、顯示在地圖上用（不會自動加入）
if "search_results" not in st.session_state:
    st.session_state.search_results = []  # 最近 5 家

# 決策：目前選中的 index
if "decision_idx" not in st.session_state:
    st.session_state.decision_idx = 0


# =========================
# 5) 母頁
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

- 抽 3 項食材
- 每道餐選擇水煮/煎炸（系統配對油或水）
- 飲料可選
- **新增：搜尋店名（例如全聯）→ 地圖顯示最近 5 家（1~5）→ 你要做決策選一間 → 按確認才加入計算**
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
# 6) 主頁：讀 Excel
# =========================
try:
    df_all = read_excel_source()
except Exception as e:
    st.error("讀取 Excel 失敗：請確認檔案在 repo 根目錄，或用上傳功能。")
    st.exception(e)
    st.stop()

df_food = df_all[df_all["code"] == "1"].copy()
df_oil = df_all[df_all["code"] == "1-1"].copy()
df_water = df_all[df_all["code"] == "1-2"].copy()
df_drink = df_all[df_all["code"] == "2"].copy()

if len(df_food) == 0:
    st.error("Excel 裡找不到 code=1 的食材。請確認你的『編號』欄有 1。")
    st.stop()

# 上方控制：抽食材 / 重置
c1, c2 = st.columns([1, 1])
with c1:
    if st.button("🎲 抽 3 項食材（主餐）", use_container_width=True):
        st.session_state.meal_items = sample_rows(df_all, "1", 3)
        st.session_state.cook_method = {i: "水煮" for i in range(len(st.session_state.meal_items))}
        st.session_state.cook_picks = {}
        st.session_state.drink_pick = None
        st.rerun()

with c2:
    if st.button("♻️ 全部重置", use_container_width=True):
        for k in ["meal_items", "cook_picks", "cook_method", "drink_pick"]:
            st.session_state[k] = None if k in ["meal_items", "drink_pick"] else {}
        st.session_state.store_points = []
        st.session_state.search_results = []
        st.session_state.decision_idx = 0
        st.rerun()

# 預設先抽一次
if st.session_state.meal_items is None:
    st.session_state.meal_items = sample_rows(df_all, "1", 3)
    st.session_state.cook_method = {i: "水煮" for i in range(len(st.session_state.meal_items))}
    st.session_state.cook_picks = {}
    st.session_state.drink_pick = None

meal_df = st.session_state.meal_items.reset_index(drop=True)

st.subheader("🍛 開始點餐：主餐（3 項食材）")
st.caption("規則：編號 1 算食材；編號 1-1 / 1-2 算料理方式（油/水）；編號 2 算飲料。")

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

# 料理選擇（逐道餐）
st.subheader("🍳 選擇調理方式（每道餐各選一次）")

for i in range(len(meal_df)):
    item_name = meal_df.loc[i, "product_name"]
    item_cf = float(meal_df.loc[i, "cf_kgco2e"])

    # 確保 cook_picks 有值
    if i not in st.session_state.cook_picks:
        method = st.session_state.cook_method.get(i, "水煮")
        st.session_state.cook_picks[i] = pick_one(df_all, "1-1" if method == "煎炸" else "1-2")

    pick = st.session_state.cook_picks[i]

    oil_text = "（找不到油品資料 code=1-1）"
    water_text = "（找不到水品資料 code=1-2）"
    if len(df_oil) > 0:
        oil_text = (
            f"（{pick['product_name']} / {pick['cf_kgco2e']:.3f}）"
            if pick["code"] == "1-1"
            else f"（隨機油品 / 參考 {df_oil.iloc[0]['cf_kgco2e']:.3f}）"
        )
    if len(df_water) > 0:
        water_text = (
            f"（{pick['product_name']} / {pick['cf_kgco2e']:.3f}）"
            if pick["code"] == "1-2"
            else f"（隨機水品 / 參考 {df_water.iloc[0]['cf_kgco2e']:.3f}）"
        )

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

# 飲料（兩個選項）
st.subheader("🥤 飲料（可選）")
drink_mode = st.radio(
    "飲料選項",
    ["隨機生成飲料", "我不喝飲料"],
    index=0 if st.session_state.drink_mode == "隨機生成飲料" else 1,
    horizontal=True,
    key="drink_mode_radio",
)

if drink_mode != st.session_state.drink_mode:
    st.session_state.drink_mode = drink_mode
    if drink_mode == "我不喝飲料":
        st.session_state.drink_pick = None
    else:
        st.session_state.drink_pick = pick_one(df_all, "2") if len(df_drink) > 0 else None
    st.rerun()

colD1, colD2 = st.columns([1, 1])
with colD1:
    if st.session_state.drink_mode == "隨機生成飲料":
        if st.button("🔄 換一杯飲料", use_container_width=True):
            st.session_state.drink_pick = pick_one(df_all, "2") if len(df_drink) > 0 else None
            st.rerun()

drink_cf = 0.0
drink_name = "不喝飲料"
if st.session_state.drink_mode == "隨機生成飲料":
    if len(df_drink) == 0:
        st.warning("找不到 code=2 的飲料資料，因此目前飲料固定為：不喝飲料。")
        st.session_state.drink_pick = None
    else:
        if st.session_state.drink_pick is None:
            st.session_state.drink_pick = pick_one(df_all, "2")
        dp = st.session_state.drink_pick
        drink_cf = float(dp["cf_kgco2e"])
        drink_name = dp["product_name"]
        st.info(f"本次飲料：**{drink_name}**（{drink_cf:.3f} kgCO₂e）")


# =========================
# ✅ 採買地點：搜尋顯示最近 5 家（1~5） + 決策後才加入
# =========================
st.subheader("🧭 採買地點與交通碳足跡（搜尋→顯示→做決策→確認）")
st.caption("流程：允許定位 → 搜尋（例如全聯）→ 地圖顯示最近 5 家（1~5）→ 你做決策選一間 → 按確認才加入採買點 → 計算交通碳足跡（直線距離）")

transport_cf = 0.0
transport_km_total = 0.0

loc = streamlit_geolocation()
if not loc or not loc.get("latitude") or not loc.get("longitude"):
    st.info("請允許瀏覽器定位權限，才能計算距離（交通碳足跡目前以 0 計）。")
else:
    user_lat = float(loc["latitude"])
    user_lng = float(loc["longitude"])
    st.success(f"你的位置：{user_lat:.6f}, {user_lng:.6f}")

    # 你提供的係數（kgCO2e / pkm；此處用 km 近似 pkm）
    EF_PRESET = {
        "機車（0.0951 kgCO₂e/km）": 9.51e-2,
        "自用小客車(汽油)（0.115 kgCO₂e/km）": 1.15e-1,
        "自行輸入係數（kgCO₂e/km）": None,
    }

    a1, a2, a3 = st.columns([1.2, 1.2, 1.0])
    with a1:
        mode_label = st.selectbox("交通方式", list(EF_PRESET.keys()), index=1, key="transport_mode_sel")
    with a2:
        if mode_label == "自行輸入係數（kgCO₂e/km）":
            ef = st.number_input("排放係數（kgCO₂e/km）", min_value=0.0, value=0.10, step=0.01, key="ef_custom")
        else:
            ef_default = float(EF_PRESET[mode_label])
            ef = st.number_input("排放係數（kgCO₂e/km，可調）", min_value=0.0, value=ef_default, step=0.01, key="ef_auto")
    with a3:
        round_trip = st.checkbox("算來回（去＋回）", value=True, key="transport_round_trip")

    st.markdown("### 🔎 搜尋分店並顯示最近 5 個點（例如：全聯）")
    q = st.text_input("搜尋關鍵關字", placeholder="例如：全聯、家樂福、第二市場", key="place_query")

    colS1, colS2 = st.columns([1, 1])
    with colS1:
        if st.button("🔍 搜尋並顯示最近 5 家", use_container_width=True):
            try:
                raw = nominatim_search(q, limit=25)  # 多抓再挑最近
                results = []
                for r in raw:
                    d = haversine_km(user_lat, user_lng, r["lat"], r["lng"])
                    rr = dict(r)
                    rr["dist_km"] = d
                    results.append(rr)

                results.sort(key=lambda x: x["dist_km"])  # 近→遠
                st.session_state.search_results = results[:5]  # ✅ 最近 5 家
                st.session_state.decision_idx = 0
            except Exception as e:
                st.session_state.search_results = []
                st.session_state.decision_idx = 0
                st.error("搜尋失敗（可能是網路或服務限制）。請換關鍵字或稍後再試。")
                st.exception(e)
            st.rerun()

    with colS2:
        if st.button("🧹 清空搜尋分店點", use_container_width=True):
            st.session_state.search_results = []
            st.session_state.decision_idx = 0
            st.rerun()

    # 地圖：藍=你的位置、綠=已加入採買點、橘=搜尋結果（1~5 編號）
    st.markdown("### 🗺️ 地圖（顯示最近 5 家分店：1~5）")

    m = folium.Map(location=[user_lat, user_lng], zoom_start=14)

    folium.Marker(
        [user_lat, user_lng],
        tooltip="你的位置",
        icon=folium.Icon(color="blue", icon="user"),
    ).add_to(m)

    for p in st.session_state.store_points:
        folium.Marker(
            [p["lat"], p["lng"]],
            tooltip=p["name"],
            icon=folium.Icon(color="green", icon="shopping-cart"),
        ).add_to(m)

    bounds = [[user_lat, user_lng]]
    for idx, r in enumerate(st.session_state.search_results, start=1):
        title = r["display_name"].split(",")[0].strip()
        bounds.append([r["lat"], r["lng"]])

        # 橘色 pin
        folium.Marker(
            [r["lat"], r["lng"]],
            tooltip=f"{idx}. {title}（約 {r['dist_km']:.2f} km）",
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
                ">{idx}</div>
                """
            ),
        ).add_to(m)

    if len(bounds) >= 2:
        m.fit_bounds(bounds)

    st.caption(f"🔎 目前顯示分店數：{len(st.session_state.search_results)}")
    _ = st_folium(m, height=420, use_container_width=True)

    # ✅ 決策區：你要選哪一個點（不會自動加入）
    st.markdown("### 🧠 做決策：決定要去哪一個採買點")

    if st.session_state.search_results:
        option_texts = []
        for idx, r in enumerate(st.session_state.search_results, start=1):
            name = r["display_name"].split(",")[0].strip()
            option_texts.append(f"{idx}. {name}（約 {r['dist_km']:.2f} km）")

        # 用 index 控制「選到哪一個」
        chosen_text = st.radio(
            "請選擇一個你『實際會去』的分店",
            option_texts,
            index=int(st.session_state.decision_idx),
            key="decision_radio_text",
        )
        chosen_idx = int(chosen_text.split(".")[0]) - 1
        st.session_state.decision_idx = chosen_idx

        chosen_store = st.session_state.search_results[chosen_idx]
        chosen_name = chosen_store["display_name"].split(",")[0].strip()

        st.info(
            f"你目前選擇：**{chosen_name}**\n\n"
            f"- 單程距離：約 **{chosen_store['dist_km']:.2f} km**\n"
            f"- {'來回' if round_trip else '單程'}里程："
            f"約 **{chosen_store['dist_km'] * (2 if round_trip else 1):.2f} km**"
        )

        if st.button("✅ 確認此採買點（加入計算）", use_container_width=True):
            st.session_state.store_points.append(
                {
                    "name": chosen_name,
                    "lat": float(chosen_store["lat"]),
                    "lng": float(chosen_store["lng"]),
                }
            )
            st.success("已加入採買點，會納入交通碳足跡計算。")
            st.rerun()

        if st.button("🗑️ 清空已加入採買點", use_container_width=True):
            st.session_state.store_points = []
            st.rerun()
    else:
        st.warning("請先搜尋（例如：全聯），地圖會顯示最近 5 家，才能做決策。")

    # 交通碳足跡：只計算「已加入採買點」（綠色）
    if st.session_state.store_points and ef > 0:
        rows_t = []
        for p in st.session_state.store_points:
            one_way_km = haversine_km(user_lat, user_lng, p["lat"], p["lng"])
            trip_km = one_way_km * (2 if round_trip else 1)
            cf = trip_km * float(ef)

            transport_km_total += trip_km
            transport_cf += cf

            rows_t.append(
                {
                    "採買地點": p["name"],
                    "距離(單程 km)": round(one_way_km, 3),
                    "里程(km)": round(trip_km, 3),
                    "交通碳足跡(kgCO₂e)": round(cf, 3),
                }
            )

        st.dataframe(pd.DataFrame(rows_t), use_container_width=True)
        st.success(f"交通里程合計：**{transport_km_total:.3f} km**；交通碳足跡合計：✅ **{transport_cf:.3f} kgCO₂e**")
    else:
        st.warning("尚未加入採買點（綠色），因此交通碳足跡目前為 0。")


# =========================
# 7) 組合表格（食材底色 + 料理方式資訊）
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

def style_combo(df):
    food_cols = ["食材名稱", "食材碳足跡(kgCO₂e)", "宣告單位"]
    def row_style(_row):
        return ["background-color: rgba(46, 204, 113, 0.18)" if c in food_cols else "" for c in df.columns]
    return df.style.apply(row_style, axis=1)

st.subheader("📋 本餐組合（表格即時更新）")
st.dataframe(style_combo(combo_df), use_container_width=True, height=220)


# =========================
# 8) 總碳足跡 + 圖表
# =========================
total = food_sum + cook_sum + drink_cf + transport_cf

st.subheader("✅ 碳足跡加總（sum）")
st.markdown(
    f"""
- **食材合計**：`{food_sum:.3f}` kgCO₂e  
- **料理方式（油/水）合計**：`{cook_sum:.3f}` kgCO₂e  
- **飲料**：`{drink_cf:.3f}` kgCO₂e（{drink_name}）  
- **交通（採買）合計**：`{transport_cf:.3f}` kgCO₂e  
- **總計**：✅ **`{total:.3f}` kgCO₂e**
"""
)

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
    .properties(height=160)
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
