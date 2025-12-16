# tomato_egg_app_all_in_one.py
import math, random, uuid, re
from datetime import datetime
from io import BytesIO

import pandas as pd
import streamlit as st
import altair as alt
import folium, requests
from streamlit_folium import st_folium
from streamlit_geolocation import streamlit_geolocation

# ---------------- Config ----------------
st.set_page_config(page_title="一餐的碳足跡大冒險", page_icon="🍽️", layout="centered")

# ---------------- Helpers ----------------
def haversine_km(lat1, lon1, lat2, lon2):
    R=6371.0
    p1,p2=math.radians(lat1),math.radians(lat2)
    dp=math.radians(lat2-lat1)
    dl=math.radians(lon2-lon1)
    a=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*R*math.asin(math.sqrt(a))

def nominatim_search(query, lat, lng, radius_km=5, limit=60):
    if not query: return []
    lat_d = radius_km/111.0
    lng_d = radius_km/(111.0*max(0.1, math.cos(math.radians(lat))))
    viewbox=f"{lng-lng_d},{lat+lat_d},{lng+lng_d},{lat-lat_d}"
    params=dict(q=query, format="jsonv2", limit=str(limit), viewbox=viewbox, bounded=1)
    headers={"User-Agent":"carbon-edu-app/1.0","Accept-Language":"zh-TW,zh,en"}
    r=requests.get("https://nominatim.openstreetmap.org/search", params=params, headers=headers, timeout=10)
    r.raise_for_status()
    out=[]
    for x in r.json():
        out.append({"name":x.get("display_name","").split(",")[0],
                    "display":x.get("display_name",""),
                    "lat":float(x["lat"]), "lng":float(x["lon"])})
    return out

def safe_sample(df, n):
    if len(df)==0: return df.copy()
    return df.sample(min(n,len(df)), replace=False, random_state=random.randint(1,9999)).reset_index(drop=True)

# ---------------- Load Excel ----------------
st.header("📄 載入資料")
up = st.file_uploader("請上傳 Excel（欄位：族群、產品名稱、碳足跡(kg)、重量(g)）", type=["xlsx"])
if not up:
    st.stop()

df = pd.read_excel(BytesIO(up.getvalue()))
df.columns = [c.strip() for c in df.columns]
required = ["族群","產品名稱","碳足跡(kg)","重量(g)"]
for c in required:
    if c not in df.columns:
        st.error(f"缺少欄位：{c}")
        st.stop()

df["族群"] = df["族群"].astype(str)
df["碳足跡(kg)"] = pd.to_numeric(df["碳足跡(kg)"], errors="coerce").fillna(0.0)
df["重量(g)"] = pd.to_numeric(df["重量(g)"], errors="coerce").fillna(0.0)

g1 = df[df["族群"]=="1"]
g11 = df[df["族群"]=="1-1"]   # 油
g12 = df[df["族群"]=="1-2"]   # 水
g2 = df[df["族群"]=="2"]      # 飲料
g3 = df[df["族群"]=="3"]      # 甜點

# ---------------- Name & Round ----------------
st.header("👤 使用者")
name = st.text_input("請輸入姓名")
st.session_state.setdefault("round", 0)
if name:
    if st.button("開始一次新測試"):
        st.session_state.round += 1

round_no = st.session_state.round
st.info(f"目前測試次數：第 {round_no} 次")

# ---------------- Main Dish ----------------
st.header("🍚 主食（5 選 2）")
pool = safe_sample(g1, 5)
opts = [f"{r['產品名稱']}（{r['碳足跡(kg)']:.2f} kgCO₂e）" for _,r in pool.iterrows()]
picked = st.multiselect("請選 2 種主食", options=opts, max_selections=2)

selected_rows = []
for s in picked:
    name_only = s.split("（")[0]
    selected_rows.append(pool[pool["產品名稱"]==name_only].iloc[0])

cook_rows=[]
for r in selected_rows:
    st.subheader(r["產品名稱"])
    method = st.radio("料理方式", ["水煮","油炸"], horizontal=True, key=f"cook_{r['產品名稱']}")
    if method=="水煮":
        w = safe_sample(g12,1).iloc[0]
        cook_rows.append(("水煮", w))
        st.caption(f"使用：{w['產品名稱']}（{w['碳足跡(kg)']:.3f} kg）")
    else:
        o = safe_sample(g11,1).iloc[0]
        cook_rows.append(("油炸", o))
        st.caption(f"使用：{o['產品名稱']}（{o['碳足跡(kg)']:.3f} kg）")

food_cf = sum(r["碳足跡(kg)"] for r in selected_rows)
cook_cf = sum(x[1]["碳足跡(kg)"] for x in cook_rows)
food_w_kg = sum(r["重量(g)"] for r in selected_rows)/1000.0

# ---------------- Drink & Dessert ----------------
st.header("🥤 飲料 / 🍰 甜點")
drink_opt = ["不喝"] + [f"{r['產品名稱']}（{r['碳足跡(kg)']:.2f} kg）" for _,r in g2.iterrows()]
drink_pick = st.selectbox("飲料", drink_opt)
drink_cf = 0.0
if drink_pick!="不喝":
    dn = drink_pick.split("（")[0]
    drink_cf = float(g2[g2["產品名稱"]==dn]["碳足跡(kg)"].iloc[0])

dessert_opts = [f"{r['產品名稱']}（{r['碳足跡(kg)']:.2f} kg）" for _,r in g3.iterrows()]
desserts = st.multiselect("甜點（可選）", dessert_opts)
dessert_cf = 0.0
for d in desserts:
    dn = d.split("（")[0]
    dessert_cf += float(g3[g3["產品名稱"]==dn]["碳足跡(kg)"].iloc[0])

# ---------------- Transport ----------------
st.header("🧭 交通（選分店 + 來回）")
geo = streamlit_geolocation()
if geo and geo.get("latitude") and geo.get("longitude"):
    lat, lng = float(geo["latitude"]), float(geo["longitude"])
else:
    lat, lng = 24.1477, 120.6736

stores = nominatim_search("全聯", lat, lng)
stores = sorted(stores, key=lambda s: haversine_km(lat,lng,s["lat"],s["lng"]))[:5]

m = folium.Map(location=[lat,lng], zoom_start=14)
folium.Marker([lat,lng], tooltip="你的位置").add_to(m)
for i,s in enumerate(stores,1):
    folium.Marker([s["lat"],s["lng"]], tooltip=f"{i}. {s['name']}").add_to(m)
st_folium(m, height=300, use_container_width=True)

idx = st.selectbox("選擇分店", list(range(1,len(stores)+1)))
picked_store = stores[idx-1]
dist_km = haversine_km(lat,lng,picked_store["lat"],picked_store["lng"])*2

mode = st.selectbox("交通工具", [
    "走路（0）",
    "機車 0.0951 kgCO₂e/pkm",
    "自用小客車 0.115 kgCO₂e/pkm",
    "低溫貨車 2.71 kgCO₂e/tkm"
])

transport_cf = 0.0
if mode.startswith("機車"):
    transport_cf = dist_km * 0.0951
elif mode.startswith("自用"):
    transport_cf = dist_km * 0.115
elif mode.startswith("低溫"):
    transport_cf = dist_km * food_w_kg/1000.0 * 2.71

st.info(f"來回距離：{dist_km:.2f} km；交通碳足跡：{transport_cf:.3f} kg")

# ---------------- Total & Charts ----------------
total = food_cf + cook_cf + drink_cf + dessert_cf + transport_cf
st.success(f"總碳足跡：{total:.3f} kgCO₂e")

chart_df = pd.DataFrame({
    "項目":["主食","料理","飲料","甜點","交通"],
    "kgCO2e":[food_cf, cook_cf, drink_cf, dessert_cf, transport_cf]
})
bar = alt.Chart(chart_df).mark_bar().encode(x="項目", y="kgCO2e")
pie = alt.Chart(chart_df).mark_arc().encode(theta="kgCO2e", color="項目")
st.altair_chart(bar, use_container_width=True)
st.altair_chart(pie, use_container_width=True)

# ---------------- CSV Download ----------------
row = dict(
    time=datetime.now().isoformat(),
    name=name, round=round_no,
    food_kg=food_cf, cook_kg=cook_cf, drink_kg=drink_cf, dessert_kg=dessert_cf,
    transport_kg=transport_cf, total_kg=total
)
csv = pd.DataFrame([row]).to_csv(index=False).encode("utf-8-sig")
st.download_button("⬇️ 下載 CSV", csv, "result.csv", "text/csv")
