
# tomato_egg_app_all_in_one_NO_WEIGHT_COLUMN.py
# ------------------------------------------------------------
# 使用者 Excel 欄位【嚴格】：族群 | 產品名稱 | 碳足跡(kg)
# 不假設重量欄；重量在程式中計算
# ------------------------------------------------------------

import streamlit as st
import pandas as pd
import math
import random
from io import BytesIO
from datetime import datetime
import requests
import folium
from streamlit_folium import st_folium
from streamlit_geolocation import streamlit_geolocation

st.set_page_config(page_title="一餐的碳足跡", layout="centered")

# =============================
# 參數設定（可教學調整）
# =============================
DEFAULT_ITEM_WEIGHT_KG = 0.4   # 每樣主食預設重量（kg）
TRUCK_EF_TKM = 2.71            # kgCO2e / tkm
MOTOR_EF_PKM = 9.51e-2         # kgCO2e / pkm
CAR_EF_PKM   = 1.15e-1         # kgCO2e / pkm

# =============================
# 工具函式
# =============================
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2-lat1)
    dl = math.radians(lon2-lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*R*math.asin(math.sqrt(a))

def load_excel(file_bytes):
    df = pd.read_excel(BytesIO(file_bytes))
    df.columns = [c.strip() for c in df.columns]
    required = ["族群","產品名稱","碳足跡(kg)"]
    for r in required:
        if r not in df.columns:
            raise ValueError(f"Excel 缺少必要欄位：{r}")
    df["族群"] = df["族群"].astype(str)
    df["碳足跡(kg)"] = pd.to_numeric(df["碳足跡(kg)"], errors="coerce").fillna(0.0)
    return df

def nominatim_pxmart(lat, lng, limit=5):
    params = {
        "q":"全聯",
        "format":"jsonv2",
        "limit":20,
        "lat":lat,
        "lon":lng
    }
    r = requests.get("https://nominatim.openstreetmap.org/search", params=params, headers={"User-Agent":"edu-app"})
    r.raise_for_status()
    data = r.json()
    out=[]
    for x in data:
        out.append({
            "name":x.get("display_name","").split(",")[0],
            "lat":float(x["lat"]),
            "lng":float(x["lon"])
        })
    return out[:limit]

# =============================
# UI：上傳 Excel
# =============================
st.title("🍽️ 一餐的碳足跡計算器")

uploaded = st.file_uploader("請上傳 Excel（族群 / 產品名稱 / 碳足跡(kg)）", type=["xlsx"])
if uploaded is None:
    st.stop()

df = load_excel(uploaded.getvalue())

# 分群
df_food    = df[df["族群"]=="1"]
df_oil     = df[df["族群"]=="1-1"]
df_water   = df[df["族群"]=="1-2"]
df_drink   = df[df["族群"]=="2"]
df_dessert = df[df["族群"]=="3"]

# =============================
# 主食：5 選 2
# =============================
st.subheader("🍚 主食選擇（5 選 2）")
pool = df_food.sample(n=min(5,len(df_food)), random_state=42)
options = [f'{r["產品名稱"]}（{r["碳足跡(kg)"]:.3f} kgCO₂e）' for _,r in pool.iterrows()]
chosen = st.multiselect("請選 2 種主食", options, max_selections=2)

chosen_rows = []
for c in chosen:
    name = c.split("（")[0]
    chosen_rows.append(pool[pool["產品名稱"]==name].iloc[0])

# 料理方式
cook_total = 0.0
st.markdown("### 🍳 料理方式")
for r in chosen_rows:
    method = st.radio(r["產品名稱"], ["水煮","油炸"], horizontal=True, key=r["產品名稱"])
    if method=="水煮" and len(df_water)>0:
        w = df_water.sample(1).iloc[0]
        cook_total += w["碳足跡(kg)"]
        st.caption(f'使用：{w["產品名稱"]}（{w["碳足跡(kg)"]:.3f} kgCO₂e）')
    if method=="油炸" and len(df_oil)>0:
        o = df_oil.sample(1).iloc[0]
        cook_total += o["碳足跡(kg)"]
        st.caption(f'使用：{o["產品名稱"]}（{o["碳足跡(kg)"]:.3f} kgCO₂e）')

food_total = sum(r["碳足跡(kg)"] for r in chosen_rows)

# =============================
# 飲料
# =============================
st.subheader("🥤 飲料")
drink_cf = 0.0
if len(df_drink)>0 and st.checkbox("我要飲料"):
    d = df_drink.sample(1).iloc[0]
    drink_cf = d["碳足跡(kg)"]
    st.info(f'{d["產品名稱"]}（{drink_cf:.3f} kgCO₂e）')

# =============================
# 甜點
# =============================
st.subheader("🍰 甜點（選 2）")
dessert_cf = 0.0
if len(df_dessert)>0:
    pool_d = df_dessert.sample(n=min(5,len(df_dessert)), random_state=1)
    opts_d = [f'{r["產品名稱"]}（{r["碳足跡(kg)"]:.3f} kgCO₂e）' for _,r in pool_d.iterrows()]
    ch_d = st.multiselect("甜點", opts_d, max_selections=2)
    for c in ch_d:
        name=c.split("（")[0]
        dessert_cf += pool_d[pool_d["產品名稱"]==name]["碳足跡(kg)"].iloc[0]

# =============================
# 交通（地圖）
# =============================
st.subheader("🚚 交通")
geo = streamlit_geolocation()
if geo and geo.get("latitude"):
    lat, lng = geo["latitude"], geo["longitude"]
    stores = nominatim_pxmart(lat,lng)
    store_names = [s["name"] for s in stores]
    pick = st.selectbox("選擇分店", store_names)
    s = next(x for x in stores if x["name"]==pick)
    dist = haversine_km(lat,lng,s["lat"],s["lng"])*2
    st.write(f"來回距離：約 {dist:.2f} km")

    transport = st.radio("交通方式", ["走路","機車","汽車","貨車"])
    transport_cf = 0.0
    if transport=="機車":
        transport_cf = dist*MOTOR_EF_PKM
    elif transport=="汽車":
        transport_cf = dist*CAR_EF_PKM
    elif transport=="貨車":
        total_weight_ton = (len(chosen_rows)*DEFAULT_ITEM_WEIGHT_KG)/1000
        transport_cf = dist*total_weight_ton*TRUCK_EF_TKM
else:
    transport_cf = 0.0

# =============================
# 總計 + CSV
# =============================
total = food_total + cook_total + drink_cf + dessert_cf + transport_cf
st.markdown(f"## ✅ 總碳足跡：{total:.3f} kgCO₂e")

row = {
    "timestamp":datetime.now().isoformat(),
    "food":food_total,
    "cooking":cook_total,
    "drink":drink_cf,
    "dessert":dessert_cf,
    "transport":transport_cf,
    "total":total
}
csv = pd.DataFrame([row]).to_csv(index=False).encode("utf-8-sig")
st.download_button("⬇️ 下載 CSV", csv, file_name="carbon_meal.csv", mime="text/csv")
