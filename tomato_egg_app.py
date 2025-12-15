# app.py
# ✅ 搜尋「全聯」後，地圖出現多個可點的分店標記（不用滑桿/下拉）
# ✅ 點標記 -> 一鍵加入採買點 -> 自動計算交通碳足跡

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

    m = re.match(r"([-+]?\d*\.?\d+)(kg|g)?$", s)
    if m:
        num = float(m.group(1))
        unit = m.group(2)
        if unit == "g":
            return num / 1000.0
        return num

    m2 = re.search(r"([-+]?\d*\.?\d+)\s*(kg|g)", s)
    if m2:
        num = float(m2.group(1))
        unit = m2.group(2)
        return num / 1000.0 if unit == "g" else num

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
def nominatim_search(query: str, limit: int = 12):
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


def best_match_by_latlng(results, lat, lng, tol=1e-6):
    """
    用座標比對找出你點到哪個搜尋結果 marker。
    tol 用很小即可（folium marker 會回傳原座標）。
    """
    if not results:
        return None
    best = None
    best_d = 10**9
    for r in results:
        d = abs(r["lat"] - lat) + abs(r["lng"] - lng)
        if d < best_d:
            best_d = d
            best = r
    return best if best_d <= tol else None


# =========================
# 2) 讀 Excel：前 4 欄
# =========================
@st.cache_data(show_spinner=False)
def load_data_from_excel(file_bytes: bytes, filename: str) -> pd.DataFrame:
    df = pd.read_excel(BytesIO(file_bytes), engine="openpyxl")
    if df.shape[1] < 4:
        raise ValueError("Excel 欄位太少，至少需要 4 欄：編號、品名、碳足跡、宣告單位。")

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

if "store_points" not in st.session_state:
    st.session_state.store_points = []  # 已加入採買點（綠色）

if "search_results" not in st.session_state:
    st.session_state.search_results = []  # 搜尋出的分店（橘色）

if "clicked_search" not in st.session_state:
    st.session_state.clicked_search = None  # 你點到哪個搜尋分店


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
- **新增：搜尋「全聯」後，地圖會出現多個可點分店標記**
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
# 6) 主頁
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
        st.session_state.clicked_search = None
        st.rerun()

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

st.subheader("🍳 選擇調理方式（每道餐各選一次）")
for i in range(len(meal_df)):
    item_name = meal_df.loc[i, "product_name"]
    item_cf = float(meal_df.loc[i, "cf_kgco2e"])

    if i not in st.session_state.cook_picks:
        method = st.session_state.cook_method.get(i, "水煮")
        st.session_state.cook_picks[i] = pick_one(df_all, "1-1" if method == "煎炸" else "1-2")

    pick = st.session_state.cook_picks[i]

    oil_text = "（找不到油品資料 code=1-1）"
    water_text = "（找不到水品資料 code=1-2）"
    if len(df_oil) > 0:
        oil_text = f"（{pick['product_name']} / {pick['cf_kgco2e']:.3f}）" if pick["code"] == "1-1" else f"（隨機油品 / 參考 {df_oil.iloc[0]['cf_kgco2e']:.3f}）"
    if len(df_water) > 0:
        water_text = f"（{pick['product_name']} / {pick['cf_kgco2e']:.3f}）" if pick["code"] == "1-2" else f"（隨機水品 / 參考 {df_water.iloc[0]['cf_kgco2e']:.3f}）"

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
    st.session_state.drink_pick = None if drink_mode == "我不喝飲料" else (pick_one(df_all, "2") if len(df_drink) > 0 else None)
    st.rerun()

if st.session_state.drink_mode == "隨機生成飲料":
    if st.button("🔄 換一杯飲料", use_container_width=True):
        st.session_state.drink_pick = pick_one(df_all, "2") if len(df_drink) > 0 else None
        st.rerun()

drink_cf = 0.0
drink_name = "不喝飲料"
if st.session_state.drink_mode == "隨機生成飲料" and len(df_drink) > 0:
    if st.session_state.drink_pick is None:
        st.session_state.drink_pick = pick_one(df_all, "2")
    dp = st.session_state.drink_pick
    drink_cf = float(dp["cf_kgco2e"])
    drink_name = dp["product_name"]
    st.info(f"本次飲料：**{drink_name}**（{drink_cf:.3f} kgCO₂e）")


# =========================
# 採買地點與交通碳足跡（搜尋結果直接打點到地圖）
# =========================
st.subheader("🧭 採買地點與交通碳足跡（搜尋後地圖可點分店）")
st.caption("流程：允許定位 → 搜尋（例如全聯）→ 地圖出現多個橘色分店點 → 點其中一個 → 加入採買點")

transport_cf = 0.0
transport_km_total = 0.0

loc = streamlit_geolocation()
if not loc or not loc.get("latitude") or not loc.get("longitude"):
    st.info("請允許瀏覽器定位權限，才能計算距離（交通碳足跡目前以 0 計）。")
else:
    user_lat = float(loc["latitude"])
    user_lng = float(loc["longitude"])
    st.success(f"你的位置：{user_lat:.6f}, {user_lng:.6f}")

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

    st.markdown("### 🔎 搜尋分店並顯示在地圖（例如：全聯）")
    q = st.text_input("搜尋關鍵字", placeholder="例如：全聯、家樂福、第二市場", key="place_query")
    colS1, colS2 = st.columns([1, 1])
    with colS1:
        if st.button("🔍 搜尋並打點到地圖", use_container_width=True):
            try:
                raw = nominatim_search(q, limit=12)

                # 計算距離並排序（近→遠），只留前 8 個（避免太滿）
                results = []
                for r in raw:
                    d = haversine_km(user_lat, user_lng, r["lat"], r["lng"])
                    rr = dict(r)
                    rr["dist_km"] = d
                    results.append(rr)
                results.sort(key=lambda x: x["dist_km"])
                st.session_state.search_results = results[:8]

                st.session_state.clicked_search = None
            except Exception as e:
                st.session_state.search_results = []
                st.error("搜尋失敗（可能是網路或服務限制）。請換關鍵字或稍後再試。")
                st.exception(e)
            st.rerun()

    with colS2:
        if st.button("🧹 清空搜尋分店點", use_container_width=True):
            st.session_state.search_results = []
            st.session_state.clicked_search = None
            st.rerun()

    # 地圖：藍=你的位置、綠=已加入採買點、橘=搜尋到的分店（可點）
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

    for idx, r in enumerate(st.session_state.search_results):
        title = r["display_name"].split(",")[0].strip()
        folium.Marker(
            [r["lat"], r["lng"]],
            tooltip=f"{title}（約 {r['dist_km']:.2f} km）",
            popup=r["display_name"],
            icon=folium.Icon(color="orange", icon="info-sign"),
        ).add_to(m)

    st.markdown("### 🗺️ 地圖（點橘色分店點即可選）")
    map_ret = st_folium(m, height=420, use_container_width=True)

    # 判斷你點到的是「搜尋分店 marker」還是「地圖空白」
    # - 點 marker 時，streamlit-folium 通常會有 last_object_clicked
    clicked_obj = map_ret.get("last_object_clicked") if map_ret else None
    clicked_any = map_ret.get("last_clicked") if map_ret else None

    # 先嘗試 marker click（橘色分店 marker）
    if clicked_obj and isinstance(clicked_obj, dict) and "lat" in clicked_obj and "lng" in clicked_obj:
        match = best_match_by_latlng(st.session_state.search_results, float(clicked_obj["lat"]), float(clicked_obj["lng"]))
        if match:
            st.session_state.clicked_search = match

    # ---------- 點到某個搜尋分店：顯示加入按鈕 ----------
    if st.session_state.clicked_search:
        r = st.session_state.clicked_search
        default_name = r["display_name"].split(",")[0].strip()
        st.info(f"你選到的分店：**{default_name}**（約 {r.get('dist_km', 0):.2f} km）")
        rename = st.text_input("採買地點名稱（可改名）", value=default_name, key="rename_selected_store")

        if st.button("➕ 加入採買點（你剛剛點的分店）", use_container_width=True):
            st.session_state.store_points.append(
                {"name": rename.strip() or default_name, "lat": float(r["lat"]), "lng": float(r["lng"])}
            )
            st.session_state.clicked_search = None
            st.rerun()

    # ---------- 仍保留：點地圖空白處新增採買點 ----------
    st.markdown("### ➕ 也可以點地圖空白處新增採買點（非分店）")
    if clicked_any and isinstance(clicked_any, dict) and "lat" in clicked_any and "lng" in clicked_any:
        st.caption(f"你點的座標：{clicked_any['lat']:.6f}, {clicked_any['lng']:.6f}")
        manual_name = st.text_input("自訂採買點名稱", value=f"採買點 {len(st.session_state.store_points)+1}", key="manual_store_name")
        if st.button("➕ 新增採買點（由地圖點選空白處）", use_container_width=True):
            st.session_state.store_points.append(
                {"name": manual_name.strip() or "採買點", "lat": float(clicked_any["lat"]), "lng": float(clicked_any["lng"])}
            )
            st.rerun()

    colC1, colC2 = st.columns([1, 1])
    with colC1:
        if st.button("🧹 清空採買點", use_container_width=True):
            st.session_state.store_points = []
            st.rerun()
    with colC2:
        st.write("")

    # ---------- 計算交通碳足跡 ----------
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
        st.success(f"交通里程合計：{transport_km_total:.3f} km；交通碳足跡合計：{transport_cf:.3f} kgCO₂e")
    else:
        st.warning("尚未新增採買點，因此交通碳足跡目前為 0。")


# =========================
# 7) 組合表格
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
# 8) 加總 + 圖表
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
