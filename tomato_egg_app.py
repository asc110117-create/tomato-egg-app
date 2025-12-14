import re
import random
import pandas as pd
import streamlit as st

st.set_page_config(page_title="一餐的碳足跡大冒險：從農場到你的胃", page_icon="🍽️", layout="wide")

EXCEL_PATH = "產品碳足跡3.xlsx"

# -----------------------------
# 讀檔 + 解析碳足跡（g/kg -> kg）
# -----------------------------
@st.cache_data
def load_products(path: str) -> pd.DataFrame:
    df = pd.read_excel(path)

    # 兼容第一欄可能叫 Unnamed: 0
    first_col = df.columns[0]
    df = df.rename(columns={first_col: "code"})
    df["code"] = df["code"].astype(str).str.strip()

    def parse_cf_to_kg(v):
        """
        將 '900.00g' / '1.00kg' 轉成 kgCO2e (float)
        """
        if pd.isna(v):
            return None
        if isinstance(v, (int, float)):
            return float(v)  # 視為 kg
        s = str(v).strip().lower().replace(" ", "")
        # 常見格式：900.00g / 1.00kg
        if s.endswith("kg"):
            return float(s[:-2])
        if s.endswith("g"):
            return float(s[:-1]) / 1000.0
        # 其他：嘗試抓數字
        m = re.search(r"[-+]?\d*\.?\d+", s)
        return float(m.group()) if m else None

    df["cf_kg"] = df["product_carbon_footprint_data"].apply(parse_cf_to_kg)

    # 只保留必要欄位
    keep = ["code", "product_name", "product_carbon_footprint_data", "declared_unit", "cf_kg"]
    df = df[keep].copy()

    # 去掉 cf_kg 解析失敗的列（避免後面加總出錯）
    df = df.dropna(subset=["cf_kg"]).reset_index(drop=True)
    return df


def pick_random_index(pool_df: pd.DataFrame) -> int:
    return int(random.choice(pool_df.index.tolist()))


def build_drink_pool(df: pd.DataFrame) -> pd.DataFrame:
    """
    你說飲料先不分類，但要「隨機生成飲料」。
    這裡用簡單規則：優先挑出看起來像飲品（含 ml/毫升/飲/茶/咖啡/水/氣泡 等）
    並排除明顯酒類關鍵字。
    """
    drink_like = df[df["code"].isin(["2", "2-1"])].copy()
    if drink_like.empty:
        # 若你的檔案飲料不在 2 / 2-1，就退回用全表關鍵字找
        drink_like = df.copy()

    text = (drink_like["product_name"].fillna("") + " " + drink_like["declared_unit"].fillna("")).str.lower()

    include_kw = r"(ml|毫升|飲|茶|咖啡|水|氣泡|cola|coke|juice|milk|乳|豆漿|果汁)"
    exclude_kw = r"(酒|高粱|威士忌|伏特加|啤|紅酒|白酒|紹興|烈酒|米酒)"

    mask_inc = text.str.contains(include_kw, regex=True)
    mask_exc = text.str.contains(exclude_kw, regex=True)

    pool = drink_like[mask_inc & ~mask_exc].copy()
    if pool.empty:
        pool = drink_like[~mask_exc].copy()  # 至少排除酒
    return pool.reset_index(drop=True)


# -----------------------------
# 主程式
# -----------------------------
st.title("🍽️ 一餐的碳足跡大冒險：從農場到你的胃")

try:
    df = load_products(EXCEL_PATH)
except Exception as e:
    st.error(f"讀取 `{EXCEL_PATH}` 失敗：請確認它和 app.py 在同一個資料夾。")
    st.exception(e)
    st.stop()

foods = df[df["code"] == "1"].copy().reset_index(drop=True)
oils = df[df["code"] == "1-1"].copy().reset_index(drop=True)
waters = df[df["code"] == "1-2"].copy().reset_index(drop=True)
drink_pool = build_drink_pool(df)

if foods.empty:
    st.error("找不到編號 `1` 的食材資料。請確認 Excel 的編號欄位是否正確。")
    st.stop()

if oils.empty:
    st.warning("找不到編號 `1-1` 的油品資料（煎炸用）。選煎炸時將無法抽油品。")

if waters.empty:
    st.warning("找不到編號 `1-2` 的水資料（水煮用）。選水煮時將無法抽水。")


# -----------------------------
# Session state 初始化
# -----------------------------
if "food_rows" not in st.session_state:
    st.session_state.food_rows = []         # 存 foods 的 row index（0..len(foods)-1）
if "methods" not in st.session_state:
    st.session_state.methods = {}           # key: i(0,1,2) -> "水煮"/"煎炸"
if "addons" not in st.session_state:
    st.session_state.addons = {}            # key: i -> dict{type, row, name, cf_kg, declared_unit}
if "drink_choice" not in st.session_state:
    st.session_state.drink_choice = "我不喝飲料"
if "drink_row" not in st.session_state:
    st.session_state.drink_row = None       # 存 drink_pool 的 row index


def reroll_foods():
    n = min(3, len(foods))
    st.session_state.food_rows = random.sample(range(len(foods)), n)
    st.session_state.methods = {}
    st.session_state.addons = {}
    st.session_state.drink_row = None


# -----------------------------
# UI：抽食材
# -----------------------------
colA, colB = st.columns([1, 2])
with colA:
    if st.button("🎲 抽出 3 項食材（編號 1）", use_container_width=True):
        reroll_foods()

with colB:
    st.caption("流程：先抽 3 項食材 → 每項選水煮/煎炸（系統自動抽水/油）→ 可選是否加飲料 → 產生整餐總碳足跡")

if not st.session_state.food_rows:
    reroll_foods()

picked_foods = foods.loc[st.session_state.food_rows].copy().reset_index(drop=True)

st.subheader("Step 1｜本次隨機食材（編號 1）")
st.dataframe(
    picked_foods.rename(columns={
        "product_name": "食材名稱",
        "declared_unit": "宣告單位",
        "product_carbon_footprint_data": "碳足跡原始值",
        "cf_kg": "食材碳足跡(kgCO₂e)"
    })[["食材名稱", "宣告單位", "碳足跡原始值", "食材碳足跡(kgCO₂e)"]],
    use_container_width=True,
    hide_index=True
)

# -----------------------------
# UI：逐項料理選擇（分支跳題）
# -----------------------------
st.subheader("Step 2｜分別選擇料理方式（系統自動抽水/油，並顯示碳足跡）")

def ensure_addon(i: int, method: str):
    """
    若使用者選了某方法，且該食材的 addon 尚未生成（或方法改變），就重新抽一次
    """
    prev = st.session_state.addons.get(i)
    if prev and prev.get("method") == method:
        return

    if method == "煎炸":
        if oils.empty:
            st.session_state.addons[i] = {"method": method, "type": "油品", "name": "（無油品資料）", "cf_kg": 0.0, "declared_unit": ""}
            return
        row = pick_random_index(oils)
        r = oils.loc[row]
        st.session_state.addons[i] = {
            "method": method, "type": "油品", "row": row,
            "name": r["product_name"], "cf_kg": float(r["cf_kg"]), "declared_unit": str(r["declared_unit"])
        }
    else:  # 水煮
        if waters.empty:
            st.session_state.addons[i] = {"method": method, "type": "水", "name": "（無水資料）", "cf_kg": 0.0, "declared_unit": ""}
            return
        row = pick_random_index(waters)
        r = waters.loc[row]
        st.session_state.addons[i] = {
            "method": method, "type": "水", "row": row,
            "name": r["product_name"], "cf_kg": float(r["cf_kg"]), "declared_unit": str(r["declared_unit"])
        }

breakdown_rows = []

for i in range(len(picked_foods)):
    food = picked_foods.loc[i]
    left, right = st.columns([1.2, 2])

    with left:
        st.markdown(f"**食材 {i+1}：{food['product_name']}**")
        st.write(f"宣告單位：{food['declared_unit']}")
        st.write(f"食材碳足跡：**{food['cf_kg']:.3f} kgCO₂e**")

        default_method = st.session_state.methods.get(i, "水煮")
        method = st.radio(
            "料理方式",
            ["水煮", "煎炸"],
            index=0 if default_method == "水煮" else 1,
            key=f"method_{i}",
            horizontal=True,
        )
        st.session_state.methods[i] = method
        ensure_addon(i, method)

    with right:
        addon = st.session_state.addons.get(i)
        addon_cf = float(addon["cf_kg"]) if addon else 0.0
        subtotal = float(food["cf_kg"]) + addon_cf

        st.markdown("**系統隨機配對的料理材料（依你選的方式）**")
        st.table(pd.DataFrame([{
            "料理方式": method,
            "配對類型": addon.get("type", ""),
            "品名": addon.get("name", ""),
            "宣告單位": addon.get("declared_unit", ""),
            "碳足跡(kgCO₂e)": round(addon_cf, 3)
        }]))

        st.success(f"此食材小計（食材 + 料理材料）：**{subtotal:.3f} kgCO₂e**")

    breakdown_rows.append({
        "食材": food["product_name"],
        "食材碳足跡(kgCO₂e)": float(food["cf_kg"]),
        "料理方式": method,
        "配對材料": addon.get("name", ""),
        "配對材料碳足跡(kgCO₂e)": addon_cf,
        "此食材小計(kgCO₂e)": subtotal
    })

# -----------------------------
# UI：飲料（兩選一）
# -----------------------------
st.subheader("Step 3｜飲料（兩個選項）")

drink_choice = st.radio("你要不要喝飲料？", ["隨機生成飲料", "我不喝飲料"], horizontal=True)
st.session_state.drink_choice = drink_choice

drink_cf = 0.0
drink_name = ""
drink_unit = ""

if drink_choice == "隨機生成飲料":
    if drink_pool.empty:
        st.warning("目前找不到可用的飲料資料（會自動當作不加飲料）。")
    else:
        if st.session_state.drink_row is None:
            st.session_state.drink_row = random.randrange(len(drink_pool))
        d = drink_pool.loc[st.session_state.drink_row]
        drink_cf = float(d["cf_kg"])
        drink_name = d["product_name"]
        drink_unit = d["declared_unit"]

        st.table(pd.DataFrame([{
            "飲料": drink_name,
            "宣告單位": drink_unit,
            "飲料碳足跡(kgCO₂e)": round(drink_cf, 3)
        }]))

        if st.button("🔁 重新抽一杯飲料"):
            st.session_state.drink_row = random.randrange(len(drink_pool))
            st.rerun()
else:
    st.session_state.drink_row = None
    st.info("本餐不加飲料。")

# -----------------------------
# Step 4：總結
# -----------------------------
st.subheader("Step 4｜整餐碳足跡總結")

breakdown_df = pd.DataFrame(breakdown_rows)
foods_total = float(breakdown_df["此食材小計(kgCO₂e)"].sum())
grand_total = foods_total + drink_cf

st.dataframe(breakdown_df, use_container_width=True, hide_index=True)

c1, c2, c3 = st.columns(3)
c1.metric("三項食材合計", f"{foods_total:.3f} kgCO₂e")
c2.metric("飲料", f"{drink_cf:.3f} kgCO₂e")
c3.metric("整餐總碳足跡", f"{grand_total:.3f} kgCO₂e")

st.caption("註：本工具以 Excel 內的產品宣告單位碳足跡為主（每項視為 1 份）；水/油為料理方式的配對材料，由系統隨機抽取後加入加總。")
