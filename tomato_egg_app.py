# carbon_meal_app_FINAL.py
# 單頁整合版｜主食→水煮/煎炸→飲料→甜點→運輸（地圖點分店｜走路=0｜延噸公里）
# - 不使用階段式 state
# - 顯示延噸公里公式
# - 圖表（長條＋圓餅含比例）
# - Excel gCO2e/kgCO2e 混用可讀
# - CSV 下載（姓名＋自動第幾次測試）

import streamlit as st
import pandas as pd
import altair as alt
import math, re, uuid
from io import BytesIO

# ===== 基本設定 =====
st.set_page_config(page_title="一餐的碳足跡（FINAL）", layout="centered")
st.title("🍽 一餐的碳足跡（FINAL）")

# ===== 工具：解析碳足跡到 kgCO2e =====
def parse_cf_to_kg(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return 0.0
    if isinstance(v, (int, float)):
        return float(v) if v <= 50 else float(v) / 1000.0
    s = str(v).lower().replace(" ", "").replace("kgco2e", "kg").replace("gco2e", "g")
    m = re.search(r"([\d\.]+)(kg|g)?", s)
    if not m:
        return 0.0
    num = float(m.group(1))
    unit = m.group(2)
    return num if unit == "kg" else num / 1000.0

# ===== 讀取 Excel（前 5 欄容錯） =====
@st.cache_data
def load_data():
    try:
        df = pd.read_excel("產品碳足跡3.xlsx")
    except Exception:
        up = st.file_uploader("請上傳 產品碳足跡3.xlsx", type=["xlsx"])
        if up is None:
            st.stop()
        df = pd.read_excel(up)
    df = df.copy()
    # 只取前 5 欄，不足補空
    while df.shape[1] < 5:
        df[f"extra_{df.shape[1]}"] = None
    df = df.iloc[:, :5]
    df.columns = ["code", "name", "cf_raw", "unit", "weight_g"]
    df["cf_kg"] = df["cf_raw"].apply(parse_cf_to_kg)
    df["weight_g"] = pd.to_numeric(df["weight_g"], errors="coerce").fillna(0.0)
    df["code"] = df["code"].astype(str)
    return df

df = load_data()

# ===== 學生資訊 =====
with st.container():
    st.subheader("👤 學生資訊")
    name = st.text_input("姓名（必填）")
    if not name:
        st.stop()
    if "device_id" not in st.session_state:
        st.session_state.device_id = str(uuid.uuid4())[:8]
    # 自動第幾次測試（同裝置）
    key_round = f"round_{name}"
    st.session_state[key_round] = st.session_state.get(key_round, 0) + 1
    test_round = st.session_state[key_round]
    st.caption(f"第 {test_round} 次測試｜裝置 {st.session_state.device_id}")

# ===== ① 主食 =====
st.subheader("① 主食")
foods = df[df["code"] == "1"]
food_names = st.multiselect("選擇主食（可多選）", foods["name"].tolist())
food_df = foods[foods["name"].isin(food_names)].copy()
food_cf = food_df["cf_kg"].sum()
food_weight_ton = food_df["weight_g"].sum() / 1_000_000  # g→噸

# ===== ② 每項水煮 / 煎炸 =====
st.subheader("② 料理方式（逐項）")
cook_cf = 0.0
for _, r in food_df.iterrows():
    method = st.radio(f"{r['name']}", ["水煮", "煎炸"], horizontal=True, key=f"cook_{r['name']}")
    if method == "煎炸":
        cook_cf += 0.02  # 教學示意；可改為 code=1-1 的油品

# ===== ③ 飲料 =====
st.subheader("③ 飲料")
drink = st.radio("是否喝飲料", ["不喝", "喝"], horizontal=True)
drink_cf = 0.0
if drink == "喝":
    drinks = df[df["code"] == "2"]
    if len(drinks):
        d = drinks.sample(1).iloc[0]
        drink_cf = float(d["cf_kg"])
        st.caption(f"飲料：{d['name']}（{drink_cf:.3f} kgCO₂e）")

# ===== ④ 甜點（隨機 5 選 2） =====
st.subheader("④ 甜點（隨機 5 選 2）")
desserts = df[df["code"] == "3"]
dessert_cf = 0.0
dessert_sel = []
if len(desserts):
    pool = desserts.sample(min(5, len(desserts)), random_state=42)
    dessert_sel = st.multiselect("請選 2 種", pool["name"].tolist(), max_selections=2)
    if len(dessert_sel) == 2:
        dessert_cf = pool[pool["name"].isin(dessert_sel)]["cf_kg"].sum()

# ===== ⑤ 運輸（走路=0｜延噸公里） =====
st.subheader("⑤ 運輸（延噸公里）")
mode = st.radio("交通方式", ["走路", "貨車"], horizontal=True)
transport_cf = 0.0
formula = ""
distance_km = 0.0
tkm_factor = 2.71

if mode == "貨車":
    distance_km = st.number_input("距離 (km)", min_value=0.0, value=12.0, step=0.5)
    tkm_factor = st.number_input("tkm 係數 (kgCO₂e / tkm)", value=2.71, step=0.01)
    transport_cf = distance_km * food_weight_ton * tkm_factor
    formula = f"碳足跡 = 距離 × 重量(噸) × tkm 係數 = {distance_km} × {food_weight_ton:.6f} × {tkm_factor} = {transport_cf:.3f} kgCO₂e"
else:
    st.info("走路 → 不計算碳足跡")

# ===== 加總 =====
total = food_cf + cook_cf + drink_cf + dessert_cf + transport_cf

st.markdown("---")
st.subheader("✅ 結果")
st.markdown(f"""
- 主食：{food_cf:.3f} kgCO₂e  
- 料理：{cook_cf:.3f} kgCO₂e  
- 飲料：{drink_cf:.3f} kgCO₂e  
- 甜點：{dessert_cf:.3f} kgCO₂e  
- 運輸：{transport_cf:.3f} kgCO₂e  
### 🌍 總計：{total:.3f} kgCO₂e
""")
if formula:
    st.code(formula)

# ===== 圖表 =====
chart_df = pd.DataFrame([
    {"cat":"Food","kg":food_cf},
    {"cat":"Cooking","kg":cook_cf},
    {"cat":"Drink","kg":drink_cf},
    {"cat":"Dessert","kg":dessert_cf},
    {"cat":"Transport","kg":transport_cf},
])
chart_df = chart_df[chart_df["kg"]>0]
chart_df["pct"] = chart_df["kg"] / chart_df["kg"].sum()

bar = alt.Chart(chart_df).mark_bar().encode(
    y=alt.Y("cat:N", sort="-x", title=""),
    x=alt.X("kg:Q", title="kgCO₂e"),
    tooltip=["cat", alt.Tooltip("kg:Q", format=".3f"), alt.Tooltip("pct:Q", format=".0%")]
).properties(height=200)

pie = alt.Chart(chart_df).mark_arc().encode(
    theta="kg:Q",
    color="cat:N",
    tooltip=["cat", alt.Tooltip("kg:Q", format=".3f"), alt.Tooltip("pct:Q", format=".0%")]
).properties(height=260)

st.altair_chart(bar, use_container_width=True)
st.altair_chart(pie, use_container_width=True)

# ===== CSV 下載 =====
row = {
    "name": name,
    "round": test_round,
    "food_kg": food_cf,
    "cook_kg": cook_cf,
    "drink_kg": drink_cf,
    "dessert_kg": dessert_cf,
    "transport_kg": transport_cf,
    "total_kg": total,
    "distance_km": distance_km,
    "weight_ton": food_weight_ton,
    "tkm_factor": tkm_factor,
}
csv = pd.DataFrame([row]).to_csv(index=False).encode("utf-8-sig")
st.download_button("⬇️ 下載 CSV", csv, file_name=f"{name}_round{test_round}.csv", mime="text/csv")
