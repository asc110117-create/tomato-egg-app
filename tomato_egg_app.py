
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

# 主程式邏輯
st.title("🍽️ 一餐的碳足跡大冒險")

# 模擬數據：這些數據應該來自於您的處理邏輯
food_sum = 2.5  # 假設數據
cook_sum = 1.2
drink_cf = 0.3
dessert_sum = 0.8

# 交通碳足跡計算
transport_mode = st.selectbox("選擇交通方式", ["motorcycle", "car", "truck"])
distance_km = st.number_input("輸入交通距離（公里）", min_value=0.1, value=10.0)

# 計算交通碳足跡
transport_cf = TRANSPORT_CO2.get(transport_mode, 0.0) * distance_km

# 渲染圖表
st.markdown("### 📊 圓餅圖")
create_pie_chart([food_sum, cook_sum, drink_cf, dessert_sum, transport_cf], ["主食", "料理", "飲料", "甜點", "交通"])

st.markdown("### 📊 長條圖")
create_bar_chart([food_sum, cook_sum, drink_cf, dessert_sum, transport_cf], ["主食", "料理", "飲料", "甜點", "交通"])

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

# 進行碳足跡計算的過程，這裡是示範數據
# 您可以將食材、料理、飲料的數據從 Excel 讀取或其他來源進行處理

# 假設的總碳足跡數據 (來自食材、烹飪方式等的計算結果)
food_sum = 2.5  # 主食碳足跡
cook_sum = 1.2  # 料理碳足跡
drink_cf = 0.3  # 飲料碳足跡
dessert_sum = 0.8  # 甜點碳足跡

# 顯示碳足跡計算的過程
st.markdown("### ✅ 計算過程")
st.write(f"主食碳足跡：{food_sum} kgCO₂e")
st.write(f"料理碳足跡：{cook_sum} kgCO₂e")
st.write(f"飲料碳足跡：{drink_cf} kgCO₂e")
st.write(f"甜點碳足跡：{dessert_sum} kgCO₂e")
st.write(f"交通碳足跡：{transport_cf} kgCO₂e")

# 計算總碳足跡
total_footprint = food_sum + cook_sum + drink_cf + dessert_sum + transport_cf
st.markdown(f"### ✅ 總碳足跡：{total_footprint:.3f} kgCO₂e")
