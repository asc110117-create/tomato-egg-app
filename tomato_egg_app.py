
import random
import pandas as pd
import streamlit as st
import altair as alt
import math
from io import BytesIO
from datetime import datetime

# 檢查數據是否有效
def is_valid_data(value):
    return isinstance(value, (int, float)) and not math.isnan(value) and value >= 0

# 渲染圓餅圖
def create_pie_chart(data, labels):
    # 檢查數據有效性
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
    # 檢查數據有效性
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

# 渲染圖表
st.markdown("### 📊 圓餅圖")
create_pie_chart([food_sum, cook_sum, drink_cf], ["主食", "料理", "飲料"])

st.markdown("### 📊 長條圖")
create_bar_chart([food_sum, cook_sum, drink_cf], ["主食", "料理", "飲料"])

# 顯示最終碳足跡結果
total = food_sum + cook_sum + drink_cf
st.markdown(f"### ✅ 總碳足跡：{total:.3f} kgCO₂e")

# 結果下載
if st.button("⬇️ 下載結果 CSV"):
    result_df = pd.DataFrame({
        '項目': ['主食', '料理', '飲料'],
        '碳足跡 (kgCO₂e)': [food_sum, cook_sum, drink_cf]
    })
    st.download_button(
        label="下載結果",
        data=result_df.to_csv(index=False).encode('utf-8-sig'),
        file_name="carbon_footprint_result.csv",
        mime="text/csv"
    )
