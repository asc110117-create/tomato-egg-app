import streamlit as st
import pandas as pd
import random
import re
import matplotlib.pyplot as plt

st.set_page_config(page_title="一餐的碳足跡大冒險：從農場到你的胃", page_icon="🍽️", layout="wide")

EXCEL_PATH = "產品碳足跡3.xlsx"

# -----------------------------
# 讀檔 + 碳足跡欄位轉成 kgCO2e（float）
# -----------------------------
@st.cache_data
def load_data(path: str = EXCEL_PATH) -> pd.DataFrame:
    df = pd.read_excel(path)

    # 統一欄名
    df = df.rename(columns={"Unnamed: 0": "code"})
    for c in ["product_name", "product_carbon_footprint_data", "declared_unit"]:
        if c not in df.columns:
            raise ValueError(f"Excel 缺少欄位：{c}")

    def parse_cf_to_kg(value):
        """
        把 '450.00g' / '1.00kg' / 數字 轉成 kgCO2e(float)
        """
        if pd.isna(value):
            return None
        if isinstance(value, (int, float)):
            return float(value)

        v = str(value).strip().lower().replace(" ", "")
        # 例：900.00g
        if v.endswith("g"):
            num = float(v[:-1])
            return num / 1000.0
        # 例：1.00kg
        if v.endswith("kg"):
            num = float(v[:-2])
            return num
        # 其他怪格式：盡量抓數字
        m = re.search(r"(\d+(\.\d+)?)", v)
        if m:
            return float(m.group(1))
        return None

    df["cf_kgco2e"] = df["product_carbon_footprint_data"].apply(parse_cf_to_kg)
    return df


def pick_random_rows(df: pd.DataFrame, code_value, n: int) -> pd.DataFrame:
    pool = df[df["code"].astype(str) == str(code_value)].dropna(subset=["cf_kgco2e"])
    if len(pool) == 0:
        return pool
    n = min(n, len(pool))
    return pool.sample(n=n, replace=False, random_state=random.randint(1, 10**9))


def looks_like_beverage(name: str) -> bool:
    """
    飲料簡易判斷：含水/茶/咖啡/飲料/氣泡 等字；排除 酒/高粱 等
    你之後也可以改成用 code 分類
    """
    if not isinstance(name, str):
        return False
    bad = ["酒", "高粱", "威士忌", "啤酒"]
    if any(b in name for b in bad):
        return False
    good = ["水", "茶", "咖啡", "飲料", "氣泡", "可樂", "果汁", "豆漿", "牛奶"]
    return any(g in name for g in good)


# -----------------------------
# 主程式
# -----------------------------
st.title("🍽️ 一餐的碳足跡大冒險：從農場到你的胃")
st.caption("規則：編號 1 算食材；編號 1-1 / 1-2 算料理方式（油 / 水）。選項一改，表格與圖表會即時更新。")

try:
    df = load_data(EXCEL_PATH)
except Exception as e:
    st.error("讀取 Excel 失敗：請確認 `產品碳足跡3.xlsx` 放在專案根目錄，且欄位正確。")
    st.exception(e)
    st.stop()

# 顯示檔案內有哪些 code
with st.expander("（查看）這份 Excel 有哪些數字編號 code？"):
    codes = sorted(df["code"].astype(str).unique().tolist())
    st.write(codes)

# 初始化 session
if "ingredients" not in st.session_state:
    st.session_state.ingredients = pd.DataFrame()

if "addons" not in st.session_state:
    # 每個食材對應一個 addon（油或水）
    st.session_state.addons = {}

if "drink" not in st.session_state:
    st.session_state.drink = None

# -----------------------------
# Step 1：抽三個食材（code=1）
# -----------------------------
left, right = st.columns([1, 1])

with left:
    st.subheader("Step 1｜抽三項食材（編號 1）")

    if st.button("🎲 重新隨機抽 3 個食材", use_container_width=True):
        ing = pick_random_rows(df, 1, 3).reset_index(drop=True)
        st.session_state.ingredients = ing
        st.session_state.addons = {}   # 重抽就清掉料理配件
        st.session_state.drink = None  # 重抽就清掉飲料

    if st.session_state.ingredients is None or len(st.session_state.ingredients) == 0:
        st.info("請先按「重新隨機抽 3 個食材」。")
        st.stop()

    ingredients = st.session_state.ingredients.copy()

    # 食材表格（先只顯示食材）
    show_ing = ingredients[["product_name", "product_carbon_footprint_data", "declared_unit", "cf_kgco2e"]].copy()
    show_ing = show_ing.rename(columns={
        "product_name": "食材名稱",
        "product_carbon_footprint_data": "碳足跡(原始格式)",
        "declared_unit": "宣告單位",
        "cf_kgco2e": "碳足跡(kgCO₂e)"
    })
    show_ing["碳足跡(kgCO₂e)"] = show_ing["碳足跡(kgCO₂e)"].round(3)

    st.markdown("**本次食材（每項 1 份 / 依宣告單位）**")
    st.dataframe(show_ing, use_container_width=True, hide_index=True)

# -----------------------------
# Step 2：每個食材選料理方式（煎/炸 → 1-1；水煮 → 1-2）
# -----------------------------
with right:
    st.subheader("Step 2｜分別選料理方式（會自動配油/水）")

    oils_pool = df[df["code"].astype(str) == "1-1"].dropna(subset=["cf_kgco2e"])
    waters_pool = df[df["code"].astype(str) == "1-2"].dropna(subset=["cf_kgco2e"])

    if len(oils_pool) == 0 or len(waters_pool) == 0:
        st.warning("找不到 1-1（油品）或 1-2（水品）資料，請檢查 Excel。")

    # 逐一詢問三個食材
    cooking_choices = []
    for i, row in ingredients.reset_index(drop=True).iterrows():
        st.markdown(f"### 食材 {i+1}")
        st.write(f"**{row['product_name']}**（食材碳足跡：約 {row['cf_kgco2e']:.3f} kgCO₂e）")

        method = st.radio(
            f"這個食材要怎麼料理？",
            ["水煮", "煎/炸"],
            key=f"method_{i}",
            horizontal=True
        )

        # 決定配件池
        if method == "煎/炸":
            pool = oils_pool
            pool_code = "1-1"
        else:
            pool = waters_pool
            pool_code = "1-2"

        # 若尚未為該食材建立配件，或料理方式變了，就重新抽一個配件
        prev = st.session_state.addons.get(i)
        need_new = (
            prev is None
            or prev.get("pool_code") != pool_code
        )
        if need_new and len(pool) > 0:
            addon_row = pool.sample(1, random_state=random.randint(1, 10**9)).iloc[0].to_dict()
            st.session_state.addons[i] = {
                "pool_code": pool_code,
                "product_name": addon_row["product_name"],
                "product_carbon_footprint_data": addon_row["product_carbon_footprint_data"],
                "declared_unit": addon_row["declared_unit"],
                "cf_kgco2e": float(addon_row["cf_kgco2e"]),
            }

        addon = st.session_state.addons.get(i)
        if addon:
            tag = "油品(1-1)" if addon["pool_code"] == "1-1" else "水品(1-2)"
            st.info(
                f"系統配對的{tag}：**{addon['product_name']}**｜"
                f"{addon['product_carbon_footprint_data']}｜{addon['declared_unit']}｜"
                f"≈ {addon['cf_kgco2e']:.3f} kgCO₂e"
            )

        cooking_choices.append(method)

# -----------------------------
# Step 3：飲料（隨機生成 / 不喝）
# -----------------------------
st.divider()
st.subheader("Step 3｜飲料（兩個選項）")

drink_col1, drink_col2 = st.columns([1, 2])

with drink_col1:
    drink_choice = st.radio("你要喝飲料嗎？", ["隨機生成飲料", "我不喝飲料"], horizontal=True)

with drink_col2:
    if drink_choice == "我不喝飲料":
        st.session_state.drink = {"name": "不喝飲料", "cf_kgco2e": 0.0, "unit": "-"}
        st.success("已選擇：不喝飲料（0）")
    else:
        # 從整份表中挑看起來像飲料的
        bev_pool = df[df["product_name"].apply(looks_like_beverage)].dropna(subset=["cf_kgco2e"])
        if len(bev_pool) == 0:
            st.warning("資料中找不到像飲料的項目（目前用關鍵字判斷），你可以指定飲料用哪個 code，我再幫你改。")
            st.session_state.drink = {"name": "（無可用飲料）", "cf_kgco2e": 0.0, "unit": "-"}
        else:
            if st.button("🥤 重新抽一個飲料"):
                d = bev_pool.sample(1, random_state=random.randint(1, 10**9)).iloc[0]
                st.session_state.drink = {
                    "name": d["product_name"],
                    "cf_kgco2e": float(d["cf_kgco2e"]),
                    "unit": d["declared_unit"]
                }

            if st.session_state.drink is None:
                # 第一次自動抽一杯
                d = bev_pool.sample(1, random_state=random.randint(1, 10**9)).iloc[0]
                st.session_state.drink = {
                    "name": d["product_name"],
                    "cf_kgco2e": float(d["cf_kgco2e"]),
                    "unit": d["declared_unit"]
                }

            st.success(
                f"本次飲料：**{st.session_state.drink['name']}**｜"
                f"{st.session_state.drink['unit']}｜"
                f"≈ {st.session_state.drink['cf_kgco2e']:.3f} kgCO₂e"
            )

# -----------------------------
# Step 4：彙整表格 + 總碳足跡 + 圖表（即時更新）
# -----------------------------
st.divider()
st.subheader("Step 4｜彙整與即時圖表")

rows = []
sum_food = 0.0
sum_addon = 0.0

for i, ing in ingredients.reset_index(drop=True).iterrows():
    ing_cf = float(ing["cf_kgco2e"])
    addon = st.session_state.addons.get(i)
    addon_cf = float(addon["cf_kgco2e"]) if addon else 0.0
    method = st.session_state.get(f"method_{i}", "水煮")

    rows.append({
        "食材": ing["product_name"],
        "食材碳足跡(kgCO₂e)": round(ing_cf, 3),
        "料理方式": method,
        "配對油/水": addon["product_name"] if addon else "-",
        "油/水碳足跡(kgCO₂e)": round(addon_cf, 3),
        "小計(kgCO₂e)": round(ing_cf + addon_cf, 3),
        "宣告單位(食材)": ing["declared_unit"],
        "宣告單位(油/水)": addon["declared_unit"] if addon else "-"
    })

    sum_food += ing_cf
    sum_addon += addon_cf

drink = st.session_state.drink or {"name": "不喝飲料", "cf_kgco2e": 0.0, "unit": "-"}
sum_drink = float(drink["cf_kgco2e"])
total = sum_food + sum_addon + sum_drink

summary_df = pd.DataFrame(rows)

st.markdown("### ✅ 本餐明細（會隨你的選項即時更新）")
st.dataframe(summary_df, use_container_width=True, hide_index=True)

st.markdown("### ✅ 總碳足跡")
m1, m2, m3, m4 = st.columns(4)
m1.metric("食材合計", f"{sum_food:.3f} kgCO₂e")
m2.metric("料理方式（油/水）合計", f"{sum_addon:.3f} kgCO₂e")
m3.metric("飲料", f"{sum_drink:.3f} kgCO₂e")
m4.metric("本餐總計", f"{total:.3f} kgCO₂e")

# -----------------------------
# 圖表：圓餅圖 + 長條圖
# -----------------------------
chart_left, chart_right = st.columns(2)

with chart_left:
    st.markdown("### 圓餅圖｜食材 vs 料理 vs 飲料")
    fig1 = plt.figure()
    parts = [sum_food, sum_addon, sum_drink]
    labels = ["食材", "料理（油/水）", "飲料"]
    # 避免全 0 報錯
    if sum(parts) == 0:
        plt.text(0.5, 0.5, "目前總量為 0", ha="center", va="center")
        plt.axis("off")
    else:
        plt.pie(parts, labels=labels, autopct="%1.1f%%")
    st.pyplot(fig1, clear_figure=True)

with chart_right:
    st.markdown("### 長條圖｜三個食材的小計")
    fig2 = plt.figure()
    x = [f"食材{i+1}" for i in range(len(summary_df))]
    y = summary_df["小計(kgCO₂e)"].tolist()
    plt.bar(x, y)
    plt.ylabel("kgCO₂e")
    st.pyplot(fig2, clear_figure=True)
