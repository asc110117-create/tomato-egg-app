
# carbon_meal_app_final_working.py
# 完整版：食材＋水煮/煎炸＋飲料＋甜點＋地圖選分店＋延噸公里運輸＋圖表
# 不做階段切換，全部一次呈現
#
# 需要套件：
# streamlit, pandas, openpyxl, altair, folium, streamlit-folium, requests

import streamlit as st
import pandas as pd
import random
import math
import altair as alt
import requests
import folium
from streamlit_folium import st_folium
from io import BytesIO

st.set_page_config(page_title="一餐的碳足跡", page_icon="🍽️", layout="centered")
st.title("🍽️ 一餐的碳足跡計算器（完整版）")

# =====================
# 工具
# =====================
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(a))

def parse_cf(value):
    """統一回傳 kgCO2e"""
    if pd.isna(value):
        return 0.0
    s = str(value).lower().replace(" ", "")
    if "kg" in s:
        return float(s.replace("kgco2e","").replace("kg",""))
    if "g" in s:
        return float(s.replace("gco2e","").replace("g","")) / 1000
    try:
        v = float(s)
        return v if v < 20 else v/1000
    except:
        return 0.0

# =====================
# 讀 Excel
# =====================
@st.cache_data
def load_data():
    df = pd.read_excel("產品碳足跡3.xlsx")
    df = df.iloc[:, :4]
    df.columns = ["code","name","cf_raw","unit"]
    df["cf"] = df["cf_raw"].apply(parse_cf)
    return df

df = load_data()

food_df   = df[df.code=="1"]
oil_df    = df[df.code=="1-1"]
water_df  = df[df.code=="1-2"]
drink_df  = df[df.code=="2"]
dessert_df= df[df.code=="3"]

# =====================
# 食材抽選
# =====================
st.subheader("🥬 主食（可重新抽）")
if "meal" not in st.session_state:
    st.session_state.meal = food_df.sample(n=min(3,len(food_df))).reset_index(drop=True)

if st.button("🔄 更換食材"):
    st.session_state.meal = food_df.sample(n=min(3,len(food_df))).reset_index(drop=True)

meal = st.session_state.meal
st.dataframe(meal[["name","cf","unit"]])

# =====================
# 水煮 / 煎炸
# =====================
st.subheader("🍳 烹調方式（使用 1-1 / 1-2）")
cook_cf_total = 0.0
cook_rows = []

for i,row in meal.iterrows():
    method = st.radio(
        f"{row['name']}",
        ["水煮","煎炸"],
        key=f"cook_{i}",
        horizontal=True
    )
    if method=="水煮" and len(water_df)>0:
        pick = water_df.sample(1).iloc[0]
    elif method=="煎炸" and len(oil_df)>0:
        pick = oil_df.sample(1).iloc[0]
    else:
        pick = None

    cf = pick.cf if pick is not None else 0.0
    cook_cf_total += cf
    cook_rows.append({
        "食材": row["name"],
        "方式": method,
        "使用項目": pick.name if pick is not None else "-",
        "碳足跡(kgCO2e)": round(cf,4)
    })

st.dataframe(pd.DataFrame(cook_rows))

# =====================
# 飲料 / 甜點
# =====================
st.subheader("🥤 飲料")
drink_cf = 0.0
if len(drink_df)>0:
    if st.checkbox("我要飲料"):
        d = drink_df.sample(1).iloc[0]
        drink_cf = d.cf
        st.info(f"{d.name} / {drink_cf:.3f} kgCO2e")

st.subheader("🍰 甜點")
dessert_cf = 0.0
if len(dessert_df)>0:
    choices = st.multiselect(
        "選 2 種甜點",
        dessert_df.name.tolist()
    )
    if len(choices)==2:
        dessert_cf = dessert_df[dessert_df.name.isin(choices)].cf.sum()

# =====================
# 地圖選分店 + 運輸
# =====================
st.subheader("🗺️ 採買地點與運輸")

transport_mode = st.selectbox(
    "交通方式",
    ["走路","機車","汽車","3.49噸低溫貨車"]
)

EF = {
    "走路": 0.0,
    "機車": 0.0951,
    "汽車": 0.115,
    "3.49噸低溫貨車": 2.71
}

origin_lat, origin_lng = 24.1477, 120.6736
m = folium.Map(location=[origin_lat, origin_lng], zoom_start=13)
folium.Marker([origin_lat, origin_lng], tooltip="起點").add_to(m)
map_state = st_folium(m, height=300)

transport_cf = 0.0
formula_text = ""

if map_state.get("last_clicked"):
    lat = map_state["last_clicked"]["lat"]
    lng = map_state["last_clicked"]["lng"]
    dist = haversine_km(origin_lat, origin_lng, lat, lng)

    if transport_mode=="3.49噸低溫貨車":
        weight_ton = meal.cf.sum() / 1000
        transport_cf = dist * weight_ton * EF[transport_mode]
        formula_text = f"{dist:.1f} × {weight_ton:.4f} × {EF[transport_mode]} = {transport_cf:.3f} kgCO2e"
    else:
        transport_cf = dist * EF[transport_mode]
        formula_text = f"{dist:.1f} × {EF[transport_mode]} = {transport_cf:.3f} kgCO2e"

    st.info("運輸公式：" + formula_text)

# =====================
# 加總
# =====================
food_cf = meal.cf.sum()
total = food_cf + cook_cf_total + drink_cf + dessert_cf + transport_cf

st.subheader("✅ 碳足跡總計")
st.write(f"""
- 主食：{food_cf:.3f}
- 烹調：{cook_cf_total:.3f}
- 飲料：{drink_cf:.3f}
- 甜點：{dessert_cf:.3f}
- 運輸：{transport_cf:.3f}

### **總計：{total:.3f} kgCO₂e**
""")

# =====================
# 圖表
# =====================
chart_df = pd.DataFrame([
    {"項目":"主食","kgCO2e":food_cf},
    {"項目":"烹調","kgCO2e":cook_cf_total},
    {"項目":"飲料","kgCO2e":drink_cf},
    {"項目":"甜點","kgCO2e":dessert_cf},
    {"項目":"運輸","kgCO2e":transport_cf},
])

bar = alt.Chart(chart_df).mark_bar().encode(
    x="kgCO2e:Q",
    y=alt.Y("項目:N", sort="-x")
)
pie = alt.Chart(chart_df[chart_df.kgCO2e>0]).mark_arc().encode(
    theta="kgCO2e:Q",
    color="項目:N"
)

st.altair_chart(bar, use_container_width=True)
st.altair_chart(pie, use_container_width=True)

