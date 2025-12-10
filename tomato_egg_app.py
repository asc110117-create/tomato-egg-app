import streamlit as st

st.title("番茄炒蛋碳足跡計算練習")

st.markdown("""
**情境說明**  
- 雞蛋排放係數：`0.162 kgCO₂e / kg`  
- 番茄排放係數：`0.50 kgCO₂e / kg`（示意用）  
- 烹調方式：**炒**（倍率 1.2）  
- 機車排放係數：`0.08 kgCO₂e / km`  
- 預設來回距離：`6 km`
""")

# === 固定參數（你也可以把這些做成可調整） ===
EF_EGG = 0.162
EF_TOMATO = 0.50
COOKING_FACTOR = 1.2       # 炒
EF_SCOOTER = 0.08          # kgCO2e/km
DEFAULT_DISTANCE = 6       # 來回距離

st.subheader("請輸入你這份番茄炒蛋的設定")

egg_g = st.number_input("雞蛋總重量 (g)", min_value=0, value=100, step=10)
tomato_g = st.number_input("番茄重量 (g)", min_value=0, value=150, step=10)
distance_km = st.number_input("來回買菜距離 (km)", min_value=0.0, value=float(DEFAULT_DISTANCE), step=0.5)

user_answer = st.text_input("👉 請自己先算一算，輸入你估計的【總碳足跡】(kgCO₂e)，例如 0.589：")

if st.button("顯示系統計算結果"):
    # 食材排放
    food_emission = EF_EGG * (egg_g / 1000) + EF_TOMATO * (tomato_g / 1000)
    # 烹調
    food_with_cooking = food_emission * COOKING_FACTOR
    # 交通
    transport_emission = distance_km * EF_SCOOTER
    # 總碳排
    total_emission = food_with_cooking + transport_emission

    st.markdown("### 計算步驟")
    st.write(f"1️⃣ 食材碳排 = 雞蛋 + 番茄 = {food_emission:.5f} kgCO₂e")
    st.write(f"2️⃣ 加上炒的烹調倍率 (×1.2) = {food_with_cooking:.5f} kgCO₂e")
    st.write(f"3️⃣ 機車交通碳排 = {distance_km} km × 0.08 = {transport_emission:.5f} kgCO₂e")
    st.write(f"4️⃣ 總碳足跡 = {total_emission:.5f} kgCO₂e")

    if user_answer:
        try:
            ua = float(user_answer)
            diff = abs(ua - total_emission)
            if diff < 0.01:
                st.success(f"🎉 很接近！你的答案 {ua:.3f} 與系統值 {total_emission:.3f} 相差 {diff:.3f} 以內。")
            else:
                st.warning(f"你的答案是 {ua:.3f}，系統計算是 {total_emission:.3f}（差 {diff:.3f}）。可以對照上面的步驟再看一次。")
        except ValueError:
            st.error("請用數字格式輸入，例如 0.589")
