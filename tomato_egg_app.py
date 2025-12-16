import pandas as pd
import streamlit as st
from io import BytesIO

# 解析碳足跡為 gCO2e
def parse_cf_to_g(value) -> float:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return float("nan")

    # 數字：預設當作「g」還是「kg」？若數字 <= 50 當作 g，否則當作 kg
    if isinstance(value, (int, float)):
        v = float(value)
        if v <= 50:
            return v * 1000.0
        return v

    s = str(value).strip().lower()
    s = s.replace(" ", "")
    s = s.replace("kgco2e", "kg").replace("gco2e", "g")

    # 1.00k 代表 1.00kg
    if re.fullmatch(r"[-+]?\d*\.?\d+k", s):
        kg = float(s[:-1])
        return kg * 1000.0

    # 末尾單位
    m = re.match(r"([-+]?\d*\.?\d+)(kg|g)?$", s)
    if m:
        num = float(m.group(1))
        unit = m.group(2)
        if unit == "kg":
            return num * 1000.0
        if unit == "g":
            return num
        # 沒單位：同上，<=50 當 kg
        return num * 1000.0 if num <= 50 else num

    # 字串內含單位（例如：'800.00g(每瓶...)'）
    m2 = re.search(r"([-+]?\d*\.?\d+)\s*(kg|g)", s)
    if m2:
        num = float(m2.group(1))
        unit = m2.group(2)
        return num * 1000.0 if unit == "kg" else num

    # 兜底：抓第一個數字
    m3 = re.search(r"([-+]?\d*\.?\d+)", s)
    if m3:
        num = float(m3.group(1))
        return num * 1000.0 if num <= 50 else num

    return float("nan")


# 轉換 g 為 kg
def g_to_kg(g):
    return float(g) / 1000.0


# 讀取 Excel 檔案並處理
@st.cache_data(show_spinner=False)
def load_data_from_excel(file_bytes: bytes) -> pd.DataFrame:
    df = pd.read_excel(BytesIO(file_bytes), engine="openpyxl")
    if df.shape[1] < 3:
        raise ValueError("Excel 欄位太少：至少 3 欄（族群、產品名稱、碳足跡(kg)）。")

    df = df.iloc[:, :3].copy()
    df.columns = ["族群", "產品名稱", "碳足跡(kg)"]

    # 處理碳足跡（將 kg 轉換為 gCO2e）
    df["碳足跡(gCO2e)"] = df["碳足跡(kg)"].apply(parse_cf_to_g)
    df["碳足跡(kgCO2e)"] = df["碳足跡(gCO2e)"].apply(g_to_kg)

    # 移除有缺失值的行
    df = df.dropna(subset=["碳足跡(gCO2e)"]).reset_index(drop=True)

    return df


# 讀取資料檔案
def read_excel_source() -> pd.DataFrame:
    st.caption("📄 資料來源：優先讀取 repo 根目錄 Excel；若讀不到可改用上傳。")
    try:
        with open("產品碳足跡4.xlsx", "rb") as f:
            return load_data_from_excel(f.read())
    except Exception:
        up = st.file_uploader("或改用上傳 Excel（.xlsx）", type=["xlsx"])
        if up is None:
            raise FileNotFoundError("讀取失敗：請確認資料檔案，或改用上傳。")
        return load_data_from_excel(up.getvalue())


# 讀取資料並顯示
df_all = read_excel_source()

# 顯示資料的前幾行，檢查資料格式
st.write(df_all.head())

# 抽取食材資料
df_food = df_all[df_all["族群"] == "1"].copy()
if len(df_food) == 0:
    st.error("找不到食材資料，請確認資料檔案正確。")
    st.stop()

# 顯示食材資料
st.write(df_food)
