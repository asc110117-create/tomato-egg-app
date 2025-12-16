
import random
import pandas as pd
import streamlit as st
import altair as alt
import math
from io import BytesIO
from datetime import datetime

# 碳足跡數據（每公里）
TRANSPORT_CO2 = {
    "motorcycle": 0.0951,  # 機車 (kgCO2e per km)
    "car": 0.115,          # 汽車 (kgCO2e per km)
    "truck": 2.71,         # 貨車 (kgCO2e per km)
}

# 檢查數據是否有效
def is_valid_data(value):
    return isinstance(value, (int, float)) and not math.isnan(value) and value >= 0

# 渲染圓餅圖
def create_pie_chart(data, labels):
    if any(not is_valid_data(x) for x in data):
        st.error("數據包含無效值，無法繪製圓餅圖。")
        return
    
    data = [float(x) for x in data]  # 確保所有數據都是 float 型態
    denom = sum(data) if sum(data) > 0 else 1  # 防止除以 0
    pct_labels = [f"{(x / denom) * 100:.1f}%" for x in data]  # 計算百分比標籤
    
    pie = (
        alt.Chart(pd.DataFrame({'data': data, 'labels': labels}))
        .mark_arc()
        .encode(
            theta=alt.Theta(field="data", type="quantitative"),
            color=alt.Color(field="labels", type="nominal"),
            tooltip=['labels', 'data'],
        )
        .properties(height=400)
    )
    
    st.altair_chart(pie, use_container_width=True)

# 渲染長條圖
def create_bar_chart(data, labels):
    if any(not is_valid_data(x) for x in data):
        st.error("數據包含無效值，無法繪製長條圖。")
        return
    
    data = [float(x) for x in data]  # 確保所有數據都是 float 型態
    chart_data = pd.DataFrame({
        'category': labels,
        'value': data
    })
    
    bar = (
        alt.Chart(chart_data)
        .mark_bar()
        .encode(
            x=alt.X('value', title='kgCO₂e'),
            y=alt.Y('category', sort='-x', title='Category'),
            color='category',
            tooltip=['category', 'value']
        )
        .properties(height=400)
    )
    
    st.altair_chart(bar, use_container_width=True)

# 食材抽取
def safe_sample(sub_df: pd.DataFrame, n: int) -> pd.DataFrame:
    if len(sub_df) == 0:
        return sub_df.copy()
    n2 = min(n, len(sub_df))
    return sub_df.sample(n=n2, replace=False, random_state=random.randint(1, 10_000)).reset_index(drop=True)

# 讀取 Excel
def read_excel_source() -> pd.DataFrame:
    st.caption("📄 資料來源：優先讀取 repo 根目錄 Excel；若讀不到可改用上傳。")
    try:
        with open("產品碳足跡3.xlsx", "rb") as f:
            return load_data_from_excel(f.read())
    except Exception:
        up = st.file_uploader("或改用上傳 Excel（.xlsx）", type=["xlsx"])
        if up is None:
            raise FileNotFoundError("讀取失敗，請確認 Excel 檔案放在正確的位置，或改用上傳。")
        return load_data_from_excel(up.getvalue())

# 載入數據並解析碳足跡
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

# 計算 CF
def parse_cf_to_g(value) -> float:
    if value is None or isinstance(value, float) and pd.isna(value):
        return float("nan")

    if isinstance(value, (int, float)):
        v = float(value)
        if v <= 50:
            return v * 1000.0
        return v

    s = str(value).strip().lower()
    s = s.replace(" ", "")
    s = s.replace("kgco2e", "kg").replace("gco2e", "g")

    if re.fullmatch(r"[-+]?\d*\.?\d+k", s):
        kg = float(s[:-1])
        return kg * 1000.0

    m = re.match(r"([-+]?\d*\.?\d+)(kg|g)?$", s)
    if m:
        num = float(m.group(1))
        unit = m.group(2)
        if unit == "kg":
            return num * 1000.0
        if unit == "g":
            return num
        return num * 1000.0 if num <= 50 else num

    m2 = re.search(r"([-+]?\d*\.?\d+)\s*(kg|g)", s)
    if m2:
        num = float(m2.group(1))
        unit = m2.group(2)
        return num * 1000.0 if unit == "kg" else num

    m3 = re.search(r"([-+]?\d*\.?\d+)", s)
    if m3:
        num = float(m3.group(1))
        return num * 1000.0 if num <= 50 else num

    return float("nan")

def g_to_kg(g):
    return float(g) / 1000.0

# 主頁面：讀取 Excel / 分類
df_all = read_excel_source()

df_food = df_all[df_all["code"] == "1"].copy()  # 食材
df_oil = df_all[df_all["code"] == "1-1"].copy()  # 油
df_water = df_all[df_all["code"] == "1-2"].copy()  # 水
df_drink = df_all[df_all["code"] == "2"].copy()  # 飲料
df_dessert = df_all[df_all["code"] == "3"].copy()  # 甜點

if len(df_food) == 0:
    st.error("Excel 裡找不到 code=1 的食材。請確認『編號』欄有 1。")
    st.stop()

# 食材抽取
st.subheader("🍛 第一階段：抽取食材與料理方式")
c1, c2 = st.columns([1, 1])
with c1:
    if st.button("🎲 抽取 3 項食材（主餐）", use_container_width=True):
        st.session_state.meal_items = safe_sample(df_food, 3)
        st.session_state.cook_method = {i: "水煮" for i in range(len(st.session_state.meal_items))}
        st.session_state.cook_picks = {}
        st.session_state.drink_pick = None
        st.session_state.drink_mode_state = "隨機生成飲料"
        st.rerun()

# 料理方式與飲料選擇
st.markdown("### 料理方式（每道餐選一次）")
for i in range(len(st.session_state.meal_items)):
    item_name = st.session_state.meal_items.loc[i, "product_name"]
    item_cf_kg = float(st.session_state.meal_items.loc[i, "cf_kgco2e"])
    st.markdown(f"**第 {i+1} 道：{item_name}**（食材 {item_cf_kg:.3f} kgCO₂e）")
    st.radio("選擇料理方式", ["水煮", "煎炸"], index=0, horizontal=True, key=f"cook_choice_{i}")

# 交通碳足跡
transport_mode = st.selectbox("選擇交通方式", ["motorcycle", "car", "truck"])
distance_km = st.number_input("輸入交通距離（公里）", min_value=0.1, value=10.0)
transport_cf = TRANSPORT_CO2.get(transport_mode, 0.0) * distance_km

# 顯示最終碳足跡結果
total = food_sum + cook_sum + drink_cf + dessert_sum + transport_cf
st.markdown(f"### ✅ 總碳足跡：{total:.3f} kgCO₂e")

# 結果下載
if st.button("⬇️ 下載結果 CSV"):
    result_df = pd.DataFrame({
        '項目': ['主食', '料理', '飲料', '甜點', '交通'],
        '碳足跡 (kgCO₂e)': [food_sum, cook_sum, drink_cf, dessert_sum, transport_cf]
    })
    st.download_button(
        label="下載結果",
        data=result_df.to_csv(index=False).encode('utf-8-sig'),
        file_name="carbon_footprint_result.csv",
        mime="text/csv"
    )
