import streamlit as st
import pandas as pd
import altair as alt
import random, math, uuid, re
from datetime import datetime
from streamlit_geolocation import streamlit_geolocation

# =====================================================
# 基本設定
# =====================================================
st.set_page_config(
    page_title="一餐的碳足跡大冒險",
    page_icon="🍽️",
    layout="centered"
)

EXCEL_PATH = "產品碳足跡3.xlsx"
RESULT_PATH = "results.csv"

# =====================================================
# 工具函式
# =====================================================
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return 2 * R * math.asin(math.sqrt(a))


def parse_cf_to_kg(value):
    """
    將各種碳足跡表示法轉為 kgCO2e（float）
    可處理：
    800g / 36.00g / 1.00kg / 0.28 (每盒300克) / 純數字
    """
    if pd.isna(value):
        return None

    s = str(value).lower().strip()

    m = re.search(r"[-+]?\d*\.?\d+", s)
    if not m:
        return None

    num = float(m.group())

    if "kg" in s:
        return num
    if "g" in s:
        return num / 1000

    return num


def save_result(row: dict):
    df = pd.DataFrame([row])
    try:
        old = pd.read_csv(RESULT_PATH)
        df = pd.concat([old, df], ignore_index=True)
    except FileNotFoundError:
        pass
    df.to_csv(RESULT_PATH, index=False)

# =====================================================
# Session 初始化（只放資料）
# =====================================================
st.session_state.setdefault("device_id", str(uuid.uuid4()))
st.session_state.setdefault("stage", "main")
st.session_state.setdefault("origin", None)

# =====================================================
# 讀取 Excel（強制欄位對齊 + 安全解析）
# =====================================================
df = pd.read_excel(EXCEL_PATH)

df = df.iloc[:, :4].copy()
df.columns = [
    "code",
    "product_name",
    "product_carbon_footprint_data",
    "declared_unit"
]

df["code"] = df["code"].astype(str)
df["cf"] = df["product_carbon_footprint_data"].apply(parse_cf_to_kg)
df = df.dropna(subset=["cf"]).reset_index(drop=True)

# =====================================================
# 定位（UI 元件只能在這裡呼叫一次）
# =====================================================
st.title("🍽️ 一餐的碳足跡大冒險")

geo = streamlit_geolocation(key="geo")

if geo and geo.get("latitude") and st.session_state.origin is None:
    st.session_state.origin = {
        "lat": geo["latitude"],
        "lng": geo["longitude"]
    }

if st.session_state.origin:
    st.success(
        f"📍 已取得定位："
        f"{st.session_state.origin['lat']:.5f}, "
        f"{st.session_state.origin['lng']:.5f}"
    )
else:
    st.warning("尚未取得定位，請允許瀏覽器定位權限")

# =====================================================
# STAGE 1：主餐流程
# =====================================================
if st.session_state.stage == "main":

    food_df = df[df.code == "1"].sample(3)
    food_cf = food_df.cf.sum()

    cook_df = df[df.code.isin(["1-1", "1-2"])].sample(3)
    cook_cf = cook_df.cf.sum()

    drink_df = df[df.code == "2"].sample(1)
    drink_cf = drink_df.cf.iloc[0]

    transport_cf = 0.30  # 第一段交通（教學用固定值）

    total = food_cf + cook_cf + drink_cf + transport_cf

    st.subheader("✅ 目前碳足跡加總")
    st.metric("kgCO₂e", f"{total:.3f}")

    pie1 = pd.DataFrame([
        ["Food", food_cf],
        ["Cooking", cook_cf],
        ["Drink", drink_cf],
        ["Transport", transport_cf],
    ], columns=["Category", "kgCO2e"])

    st.altair_chart(
        alt.Chart(pie1)
        .mark_arc()
        .encode(theta="kgCO2e", color="Category"),
        use_container_width=True
    )

    if st.button("🍰 進入甜點情境", use_container_width=True):
        st.session_state.base = {
            "food": food_cf,
            "cooking": cook_cf,
            "drink": drink_cf,
            "transport": transport_cf,
        }
        st.session_state.stage = "dessert"
        st.rerun()

# =====================================================
# STAGE 2：甜點 + 餐具 + 第二次交通
# =====================================================
if st.session_state.stage == "dessert":

    base = st.session_state.base

    # -------- 甜點：抽 3 選 2 --------
    st.subheader("🍰 今日甜點（抽 3 選 2）")

    dessert_pool = df[df.code == "3"].sample(3).reset_index(drop=True)

    dessert_pick = st.multiselect(
        "請選 2 種甜點",
        dessert_pool.index.tolist(),
        format_func=lambda i: (
            f"{dessert_pool.loc[i,'product_name']} "
            f"({dessert_pool.loc[i,'cf']:.3f} kgCO₂e)"
        ),
        max_selections=2,
    )

    dessert_cf = (
        dessert_pool.loc[dessert_pick, "cf"].sum()
        if len(dessert_pick) == 2 else 0.0
    )

    # -------- 餐具／包材 --------
    st.subheader("🍴 餐具／包材（可不選、可複選）")

    utensil_df = df[df.code.str.startswith("4-")]

    utensil_pick = st.multiselect(
        "選擇使用的餐具／包材",
        utensil_df.product_name.tolist(),
    )

    utensil_cf = utensil_df[
        utensil_df.product_name.isin(utensil_pick)
    ].cf.sum()

    # -------- 內用 / 帶回 --------
    st.subheader("🏫 內用或帶回台中教育大學")

    mode = st.radio(
        "選擇方式",
        ["內用", "帶回台中教育大學"],
        horizontal=True
    )

    dessert_transport_cf = 0.0
    if mode == "帶回台中教育大學" and st.session_state.origin:
        NTCU_LAT, NTCU_LNG = 24.1437, 120.6736
        o = st.session_state.origin
        d = haversine_km(o["lat"], o["lng"], NTCU_LAT, NTCU_LNG)
        dessert_transport_cf = d * 0.115

    # -------- 最終加總 --------
    final_total = (
        base["food"]
        + base["cooking"]
        + base["drink"]
        + base["transport"]
        + dessert_cf
        + utensil_cf
        + dessert_transport_cf
    )

    st.divider()
    st.subheader("🍽️ 最終碳足跡結果")

    pie2 = pd.DataFrame([
        ["Food", base["food"]],
        ["Cooking", base["cooking"]],
        ["Drink", base["drink"]],
        ["Transport", base["transport"] + dessert_transport_cf],
        ["Dessert", dessert_cf],
        ["Packaging", utensil_cf],
    ], columns=["Category", "kgCO2e"])

    st.altair_chart(
        alt.Chart(pie2)
        .mark_arc()
        .encode(theta="kgCO2e", color="Category"),
        use_container_width=True
    )

    st.metric("🌍 最終總碳足跡 (kgCO₂e)", f"{final_total:.3f}")

    if st.button("📥 儲存我的結果", use_container_width=True):
        save_result({
            "device_id": st.session_state.device_id,
            "timestamp": datetime.now().isoformat(),
            "food": base["food"],
            "cooking": base["cooking"],
            "drink": base["drink"],
            "transport": base["transport"] + dessert_transport_cf,
            "dessert": dessert_cf,
            "packaging": utensil_cf,
            "total": final_total,
        })
        st.success("✅ 已儲存，結果已寫入 results.csv")
