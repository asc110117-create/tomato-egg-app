import re
import random
from pathlib import Path

import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

# =============================
# 基本設定
# =============================
st.set_page_config(
    page_title="一餐的碳足跡大冒險：從農場到你的胃",
    page_icon="🍽️",
    layout="centered",  # 手機 9:16 直式也比較好看
)

EXCEL_DEFAULT = "產品碳足跡3.xlsx"

# 兩位學號與姓名（寫死在程式裡）
STUDENT_MAP = {
    "BEE114105": "黃文瑜",
    "BEE114108": "陳依萱",
}

# =============================
# 工具：欄位辨識 + 數值清洗
# =============================
def _norm_text(x) -> str:
    return str(x).strip()

def _find_col(cols, keywords):
    """在欄位名稱中找包含 keyword 的欄位（不分大小寫）"""
    lower = {c: str(c).lower() for c in cols}
    for kw in keywords:
        kw = kw.lower()
        for c, lc in lower.items():
            if kw in lc:
                return c
    return None

def norm_group(v) -> str:
    """
    把 group/編號欄位正規化成：'1', '1-1', '1-2', '2' ...
    允許：1 / 1.0 / ' 1 ' / '1-1' / '編號 1-2' / '1－1'
    """
    if pd.isna(v):
        return ""
    s = str(v).strip()
    s = s.replace("－", "-").replace("–", "-").replace("—", "-")
    # 若是數字型（1.0）
    try:
        f = float(s)
        if f.is_integer():
            return str(int(f))
    except Exception:
        pass

    # 從字串中抓出 1 或 1-1 這種 pattern
    m = re.search(r"(\d+(?:-\d+)?)", s)
    return m.group(1) if m else s

def parse_cf_to_kg(value) -> float:
    """
    把 '900.00g' / '1.00kg' / '1.00k' / '0.398 kg' / '398gCO2e' 轉成 kgCO2e(float)
    """
    if pd.isna(value):
        return 0.0

    # 若已是數字
    if isinstance(value, (int, float)):
        return float(value)

    s = str(value).strip().lower()
    s = s.replace(",", "")
    # 去掉常見文字
    s = s.replace("kgco2e", "").replace("co2e", "").replace(" ", "")

    # 例如 '398.00g' / '398g'
    if s.endswith("g"):
        num = s[:-1]
        num = re.sub(r"[^\d.]+", "", num)
        return float(num) / 1000.0 if num else 0.0

    # 例如 '1.00kg' / '1kg'
    if s.endswith("kg"):
        num = s[:-2]
        num = re.sub(r"[^\d.]+", "", num)
        return float(num) if num else 0.0

    # 容錯：你遇到的 '1.00k'（把 k 當 kg）
    if s.endswith("k"):
        num = s[:-1]
        num = re.sub(r"[^\d.]+", "", num)
        return float(num) if num else 0.0

    # 其他：只抓數字
    num = re.sub(r"[^\d.]+", "", s)
    return float(num) if num else 0.0

@st.cache_data
def load_data(excel_path: str):
    df = pd.read_excel(excel_path)

    # 自動辨識欄位
    cols = list(df.columns)

    col_group = _find_col(cols, ["group", "編號", "群組", "類別"])
    col_name  = _find_col(cols, ["product_name", "品名", "產品", "食材", "名稱"])
    col_cf    = _find_col(cols, ["product_carbon_footprint_data", "碳足跡", "carbon", "cf"])
    col_unit  = _find_col(cols, ["declared_unit", "宣告單位", "單位", "功能單位"])

    missing = []
    if not col_group: missing.append("group/編號")
    if not col_name:  missing.append("品名")
    if not col_cf:    missing.append("碳足跡")
    if not col_unit:  missing.append("宣告單位")

    if missing:
        raise ValueError(
            f"Excel 欄位辨識失敗，缺少欄位：{', '.join(missing)}。"
            "請確認至少有：編號/群組、品名、碳足跡、宣告單位。"
        )

    out = pd.DataFrame({
        "group": df[col_group].apply(norm_group),
        "name": df[col_name].apply(_norm_text),
        "cf_kg": df[col_cf].apply(parse_cf_to_kg),
        "unit": df[col_unit].apply(_norm_text),
    })

    # 清掉空品名
    out = out[out["name"].str.len() > 0].reset_index(drop=True)

    return out

# =============================
# UI：母頁 / 主流程
# =============================
def init_state():
    st.session_state.setdefault("page", "home")  # home / order
    st.session_state.setdefault("student_id", "")
    st.session_state.setdefault("picked_main_idx", [])
    st.session_state.setdefault("cook_choice", {})   # {0:'boil'/'fry', 1:..., 2:...}
    st.session_state.setdefault("cook_item", {})     # {0: row dict(油/水), ...}
    st.session_state.setdefault("drink_mode", "random")  # random / none
    st.session_state.setdefault("drink_item", None)

def reset_order():
    st.session_state.picked_main_idx = []
    st.session_state.cook_choice = {}
    st.session_state.cook_item = {}
    st.session_state.drink_mode = "random"
    st.session_state.drink_item = None

init_state()

# =============================
# 讀 Excel：找不到就讓使用者上傳
# =============================
st.title("🍽️ 一餐的碳足跡大冒險：從農場到你的胃")

excel_path = None
if Path(EXCEL_DEFAULT).exists():
    excel_path = EXCEL_DEFAULT
else:
    st.info("找不到專案根目錄的 Excel，請在這裡上傳：")
    up = st.file_uploader("上傳 Excel（.xlsx）", type=["xlsx"])
    if up is not None:
        excel_path = up

if excel_path is None:
    st.stop()

try:
    df_all = load_data(excel_path if isinstance(excel_path, str) else excel_path)
except Exception as e:
    st.error("讀取 Excel 失敗：請確認檔案欄位與碳足跡格式。")
    st.exception(e)
    st.stop()

# 分群（你的規則：1=食材；1-1=油；1-2=水；2=飲料）
df_main = df_all[df_all["group"] == "1"].reset_index(drop=True)
df_oil  = df_all[df_all["group"] == "1-1"].reset_index(drop=True)
df_water= df_all[df_all["group"] == "1-2"].reset_index(drop=True)
df_drink= df_all[df_all["group"] == "2"].reset_index(drop=True)

# 防呆檢查
if len(df_main) == 0:
    st.error("你的 Excel 裡找不到 group=1 的主餐食材（主餐只能出現 group=1）。")
    st.stop()
if len(df_oil) == 0:
    st.warning("Excel 裡找不到 group=1-1 的油品（煎炸會用到）。")
if len(df_water) == 0:
    st.warning("Excel 裡找不到 group=1-2 的水品（水煮會用到）。")
if len(df_drink) == 0:
    st.warning("Excel 裡找不到 group=2 的飲料（隨機飲料會用到）。")

# =============================
# 母頁（預約號碼）
# =============================
if st.session_state.page == "home":
    st.subheader("🏭 碳足跡觀光工廠｜報到")

    sid = st.text_input("您的預約號碼（輸入學號）", value=st.session_state.student_id, placeholder="例如：BEE114108")
    sid = sid.strip().upper()
    st.session_state.student_id = sid

    if sid in STUDENT_MAP:
        name = STUDENT_MAP[sid]
        st.success(f"{name}您好，歡迎來到碳足跡觀光工廠！")

        st.markdown(
            f"""
**{name}**，你即將踏上一場「從農場到你的胃」的旅程。

在這座工廠裡，每一樣食材都有自己的「碳足跡護照」：  
- 它可能來自農田、牧場、工廠加工、包裝運輸  
- 也可能在「料理方式」上產生額外排放（例如煎炸用油、水煮用水）  
- 最後，你是否加點飲料，也會讓總排放不同

接下來你要做的任務是：  
1) 系統先隨機抽出 3 道主餐食材（只從 group=1）  
2) 你替每一道餐選擇「煎炸 / 水煮」，系統會自動搭配一種油或水（分別來自 group=1-1 / 1-2）  
3) 飲料可選：隨機一杯（只從 group=2）或不喝  
4) 表格與圖表會即時更新，最後看到你這餐的碳足跡組成！
"""
        )

        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ 開始點餐", use_container_width=True):
                st.session_state.page = "order"
                reset_order()
                st.rerun()
        with col2:
            if st.button("↩️ 重新輸入學號", use_container_width=True):
                st.session_state.student_id = ""
                st.rerun()
    else:
        st.info("可用學號：BEE114105（黃文瑜）、BEE114108（陳依萱）")
    st.stop()

# =============================
# 點餐頁
# =============================
st.subheader("🍱 開始點餐：主餐（3 道）")

top_btn1, top_btn2 = st.columns(2)
with top_btn1:
    if st.button("🎲 抽 3 項主餐食材（group=1）", use_container_width=True):
        n = min(3, len(df_main))
        st.session_state.picked_main_idx = random.sample(range(len(df_main)), n)
        # 每次抽新主餐，料理/飲料都重置
        st.session_state.cook_choice = {}
        st.session_state.cook_item = {}
        st.session_state.drink_item = None
        st.rerun()

with top_btn2:
    if st.button("♻️ 全部重置", use_container_width=True):
        reset_order()
        st.rerun()

if not st.session_state.picked_main_idx:
    st.info("請先按「抽 3 項主餐食材」。")
    st.stop()

main_pick = df_main.loc[st.session_state.picked_main_idx].reset_index(drop=True)

# 表格：食材底色（固定不因選項改變）
st.markdown("### ① 本次主餐食材（固定）")

def style_main(df):
    # 全列淡綠底色
    return pd.DataFrame([["background-color: #DFF5E7"] * df.shape[1]] * df.shape[0], columns=df.columns)

main_show = main_pick.rename(columns={"name": "食材名稱", "cf_kg": "食材碳足跡(kgCO₂e)", "unit": "宣告單位"})[
    ["食材名稱", "食材碳足跡(kgCO₂e)", "宣告單位"]
].copy()
main_show["食材碳足跡(kgCO₂e)"] = main_show["食材碳足跡(kgCO₂e)"].round(3)

st.dataframe(main_show.style.apply(style_main, axis=None), use_container_width=True, hide_index=True)

# 料理方式選擇
st.markdown("### ② 選擇調理方式（每道餐各選一次）")
st.caption("規則：煎炸 → 隨機搭配油品（group=1-1）；水煮 → 隨機搭配水品（group=1-2）。選項一改，總和與圖表即時更新。")

for i in range(len(main_pick)):
    food_name = main_pick.loc[i, "name"]
    food_cf = float(main_pick.loc[i, "cf_kg"])

    # 先準備「這道餐的油/水候選」（每道各自隨機一個，保持穩定直到重抽）
    if i not in st.session_state.cook_item:
        oil_item = None
        water_item = None
        if len(df_oil) > 0:
            r = df_oil.sample(1).iloc[0]
            oil_item = {"type": "油品", "name": r["name"], "cf": float(r["cf_kg"]), "unit": r["unit"], "group": "1-1"}
        if len(df_water) > 0:
            r = df_water.sample(1).iloc[0]
            water_item = {"type": "水品", "name": r["name"], "cf": float(r["cf_kg"]), "unit": r["unit"], "group": "1-2"}
        st.session_state.cook_item[i] = {"oil": oil_item, "water": water_item}

    oil_item = st.session_state.cook_item[i]["oil"]
    water_item = st.session_state.cook_item[i]["water"]

    # 顯示題目
    st.markdown(f"**第 {i+1} 道餐：{food_name}**（食材 {food_cf:.3f} kgCO₂e）")

    # 文字顯示（括號內顯示油/水與碳足跡）
    boil_label = "水煮"
    fry_label = "煎炸"

    if water_item:
        boil_label += f"（{water_item['name']} / {water_item['cf']:.3f}）"
    else:
        boil_label += "（無水品資料）"

    if oil_item:
        fry_label += f"（{oil_item['name']} / {oil_item['cf']:.3f}）"
    else:
        fry_label += "（無油品資料）"

    default = st.session_state.cook_choice.get(i, "boil")
    choice = st.radio(
        "請選擇料理方式：",
        options=["boil", "fry"],
        format_func=lambda x: boil_label if x == "boil" else fry_label,
        index=0 if default == "boil" else 1,
        key=f"cook_choice_{i}",
        horizontal=True,
    )
    st.session_state.cook_choice[i] = choice

    st.divider()

# 飲料（只允許 group=2）
st.markdown("### ③ 飲料（可選）")
drink_mode = st.radio(
    "飲料選項",
    options=["random", "none"],
    format_func=lambda x: "隨機生成飲料（group=2）" if x == "random" else "我不喝飲料",
    index=0 if st.session_state.drink_mode == "random" else 1,
    horizontal=True,
)
st.session_state.drink_mode = drink_mode

if drink_mode == "random":
    if len(df_drink) == 0:
        st.warning("你的 Excel 沒有 group=2 的飲料資料，因此無法抽飲料。")
        st.session_state.drink_item = None
    else:
        if st.session_state.drink_item is None:
            r = df_drink.sample(1).iloc[0]
            st.session_state.drink_item = {"name": r["name"], "cf": float(r["cf_kg"]), "unit": r["unit"], "group": "2"}

        d = st.session_state.drink_item
        colA, colB = st.columns([2, 1])
        with colA:
            st.info(f"本次飲料：**{d['name']}**（{d['cf']:.3f} kgCO₂e）")
        with colB:
            if st.button("🔁 換一杯飲料", use_container_width=True):
                r = df_drink.sample(1).iloc[0]
                st.session_state.drink_item = {"name": r["name"], "cf": float(r["cf_kg"]), "unit": r["unit"], "group": "2"}
                st.rerun()
else:
    st.session_state.drink_item = None

# =============================
# 組合表格 + 總和
# =============================
rows = []
# 食材列
for i in range(len(main_pick)):
    rows.append({
        "類別": "食材",
        "餐次": f"第{i+1}道",
        "名稱": main_pick.loc[i, "name"],
        "碳足跡(kgCO₂e)": float(main_pick.loc[i, "cf_kg"]),
        "宣告單位": main_pick.loc[i, "unit"],
    })

# 料理方式列（油/水）
for i in range(len(main_pick)):
    choice = st.session_state.cook_choice.get(i, "boil")
    item = st.session_state.cook_item[i]["water"] if choice == "boil" else st.session_state.cook_item[i]["oil"]
    if item:
        rows.append({
            "類別": "料理方式",
            "餐次": f"第{i+1}道",
            "名稱": f"{'水煮' if choice=='boil' else '煎炸'}：{item['name']}",
            "碳足跡(kgCO₂e)": float(item["cf"]),
            "宣告單位": item["unit"],
        })
    else:
        rows.append({
            "類別": "料理方式",
            "餐次": f"第{i+1}道",
            "名稱": "（缺資料）",
            "碳足跡(kgCO₂e)": 0.0,
            "宣告單位": "",
        })

# 飲料列
if st.session_state.drink_item:
    d = st.session_state.drink_item
    rows.append({
        "類別": "飲料",
        "餐次": "飲料",
        "名稱": d["name"],
        "碳足跡(kgCO₂e)": float(d["cf"]),
        "宣告單位": d["unit"],
    })

combo = pd.DataFrame(rows)
combo["碳足跡(kgCO₂e)"] = combo["碳足跡(kgCO₂e)"].astype(float)

food_sum = float(combo[combo["類別"] == "食材"]["碳足跡(kgCO₂e)"].sum())
cook_sum = float(combo[combo["類別"] == "料理方式"]["碳足跡(kgCO₂e)"].sum())
drink_sum = float(combo[combo["類別"] == "飲料"]["碳足跡(kgCO₂e)"].sum()) if "飲料" in combo["類別"].values else 0.0
total_sum = food_sum + cook_sum + drink_sum

st.markdown("### ④ 本餐組合（即時更新）")

def style_combo(df):
    styles = pd.DataFrame("", index=df.index, columns=df.columns)
    # 食材底色
    food_mask = df["類別"] == "食材"
    styles.loc[food_mask, :] = "background-color: #DFF5E7"
    # 料理方式底色
    cook_mask = df["類別"] == "料理方式"
    styles.loc[cook_mask, :] = "background-color: #FFF2CC"
    # 飲料底色
    drink_mask = df["類別"] == "飲料"
    styles.loc[drink_mask, :] = "background-color: #DDEBFF"
    return styles

show_combo = combo.copy()
show_combo["碳足跡(kgCO₂e)"] = show_combo["碳足跡(kgCO₂e)"].round(3)

st.dataframe(
    show_combo.style.apply(style_combo, axis=None),
    use_container_width=True,
    hide_index=True,
)

st.markdown("### ⑤ 碳足跡加總（sum）")
c1, c2, c3, c4 = st.columns(4)
c1.metric("食材合計", f"{food_sum:.3f}")
c2.metric("料理方式合計", f"{cook_sum:.3f}")
c3.metric("飲料", f"{drink_sum:.3f}")
c4.metric("總計", f"{total_sum:.3f}")

# =============================
# 圖表（縮小、手機也好看）
# =============================
st.markdown("### ⑥ 圖表（選項一改就更新）")
st.caption("若中文圖例字型無法顯示，會自動用英文標籤。")

# 長條圖：三大類
bar_df = pd.DataFrame({
    "category": ["Food", "Cooking", "Drink"],
    "kgCO2e": [food_sum, cook_sum, drink_sum],
})

fig1, ax1 = plt.subplots(figsize=(6, 3.2), dpi=120)
ax1.bar(bar_df["category"], bar_df["kgCO2e"])
ax1.set_ylabel("kgCO₂e")
ax1.set_title("Carbon Footprint by Category")
st.pyplot(fig1, use_container_width=True)

# 圓餅圖：比例（修正你遇到「圖例出不來」：改成 legend + bbox_to_anchor）
labels = []
sizes = []
if food_sum > 0:  labels.append("Food");   sizes.append(food_sum)
if cook_sum > 0:  labels.append("Cooking");sizes.append(cook_sum)
if drink_sum > 0: labels.append("Drink");  sizes.append(drink_sum)

fig2, ax2 = plt.subplots(figsize=(6, 3.2), dpi=120)
wedges, texts, autotexts = ax2.pie(
    sizes,
    autopct=lambda p: f"{p:.1f}%" if p >= 3 else "",
    startangle=90,
)
ax2.set_title("Share of Total Emissions")

# 圖例固定顯示（即使文字顏色/背景不同也可）
ax2.legend(
    wedges,
    labels,
    loc="center left",
    bbox_to_anchor=(1.0, 0.5),
    frameon=False,
)

st.pyplot(fig2, use_container_width=True)

st.markdown("---")
st.caption("🔎 小提醒：主餐只會從 group=1 抽；煎炸只會從 group=1-1 抽油；水煮只會從 group=1-2 抽水；飲料只會從 group=2 抽。")
