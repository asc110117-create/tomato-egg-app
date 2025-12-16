import pandas as pd
import streamlit as st
import random

# =========================
# 讀取 Excel（簡化過的版本，只有三個欄位）
# =========================
def load_data_from_excel(file_bytes):
    df = pd.read_excel(file_bytes)
    # 假設文件有三個欄位：族群、產品名稱、碳足跡(kg)
    df.columns = ['group', 'product_name', 'cf_kg']
    df['cf_kg'] = df['cf_kg'].astype(float)  # 碳足跡轉換為數字格式
    return df

# =========================
# 主食隨機選擇
# =========================
def random_main_dish(df):
    # 隨機選擇5個主食
    main_dish_options = df.sample(n=5)
    return main_dish_options

# =========================
# 主食選擇與碳足跡計算
# =========================
def main_dish_selection():
    # 讀取Excel文件
    uploaded_file = st.file_uploader("請上傳碳足跡檔案", type=["xlsx"])
    if uploaded_file is not None:
        df = load_data_from_excel(uploaded_file)
        
        # 顯示隨機選擇的5項食材
        main_dish_options = random_main_dish(df)
        st.write("請選擇2種主食：")
        main_dish_selection = st.multiselect(
            "選擇兩種主食",
            options=main_dish_options['product_name'],
            default=[main_dish_options['product_name'].iloc[0], main_dish_options['product_name'].iloc[1]]
        )

        # 顯示選擇的主食和對應碳足跡
        selected_dishes = main_dish_options[main_dish_options['product_name'].isin(main_dish_selection)]
        for index, row in selected_dishes.iterrows():
            st.write(f"{row['product_name']} - {row['cf_kg']} kgCO2e")

# =========================
# 烹飪方式選擇
# =========================
def cooking_method_selection():
    cooking_method = st.selectbox(
        "請選擇烹飪方式（水煮或油炸）",
        ["水煮", "油炸"]
    )
    return cooking_method

# =========================
# 計算碳足跡
# =========================
def calculate_total_carbon_footprint(selected_dishes, cooking_method):
    total_carbon_footprint = 0
    for index, row in selected_dishes.iterrows():
        # 根據選擇的烹飪方式增加相應的碳足跡
        if cooking_method == "油炸":
            total_carbon_footprint += row['cf_kg'] * 1.1  # 假設油炸會增加10%的碳足跡
        else:
            total_carbon_footprint += row['cf_kg']
    return total_carbon_footprint

# =========================
# 顯示總碳足跡
# =========================
def show_total_carbon_footprint(total_carbon_footprint):
    st.write(f"總碳足跡：{total_carbon_footprint:.2f} kgCO2e")

# =========================
# 主要功能執行
# =========================
def main():
    st.title("一餐的碳足跡計算器")
    
    # 主食選擇
    main_dish_selection()

    # 烹飪方式選擇
    cooking_method = cooking_method_selection()

    # 碳足跡計算
    total_carbon_footprint = calculate_total_carbon_footprint(selected_dishes, cooking_method)
    
    # 顯示總碳足跡
    show_total_carbon_footprint(total_carbon_footprint)

if __name__ == "__main__":
    main()
