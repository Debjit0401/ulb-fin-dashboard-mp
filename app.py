import pandas as pd
import streamlit as st

# ── CONFIG ──
SHEET_ID = "1LZtwJUmblDYe-YM40epBqyRTUwnr4b2Y_MsETU1XQWA"
MAIN_SHEET_NAME = "OverAll_FinStatusRp"

# Column mapping (0-indexed), same as the HTML dashboard:
# 0 Sr, 1 Division, 2 District, 3 ULB Name, 4 ULB Code, 5 LGD Code, 6 IA's Cd, 7 Sharing Pattern
# "Overall" block starts at column 8:
#   8 Project Cost, 9 ULB Share, 10 GOI/GoMP Share, 11 CC Rlsd, 12 Utilization, 13 Unspent, 14 Balance
OVERALL_START = 8

st.set_page_config(page_title="SBM(U) 2.0 — ULB Fin Status", layout="wide")


@st.cache_data(ttl=300)
def load_data() -> pd.DataFrame:
    url = (
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq"
        f"?tqx=out:csv&sheet={MAIN_SHEET_NAME}"
    )
    # header=None: row 0 = group header, row 1 = column header (both junk to us),
    # real data starts at row 2 — same layout the HTML dashboard assumes.
    raw = pd.read_csv(url, header=None, skiprows=2)

    df = pd.DataFrame({
        "Division": raw[1].astype(str).str.strip(),
        "District": raw[2].astype(str).str.strip(),
        "ULB Name": raw[3].astype(str).str.strip(),
        "Fund Released": pd.to_numeric(raw[OVERALL_START + 3], errors="coerce").fillna(0),
        "Expenditure": pd.to_numeric(raw[OVERALL_START + 4], errors="coerce").fillna(0),
        "Unspent": pd.to_numeric(raw[OVERALL_START + 5], errors="coerce").fillna(0),
    })

    # Drop non-ULB rows (blank name, or any kind of "Total"/"State" rollup row)
    df = df[df["ULB Name"].str.len() > 0]
    df = df[~df["ULB Name"].str.lower().str.contains("total|^state$", regex=True)]

    # Forward-fill Division in case of merged cells in the source sheet
    df["Division"] = df["Division"].replace("", pd.NA).ffill()

    df["% Util"] = (df["Expenditure"] / df["Fund Released"].replace(0, pd.NA) * 100).fillna(0)
    return df.reset_index(drop=True)


# ── SIDEBAR ──
st.sidebar.title("SBM(U) 2.0")
st.sidebar.caption("MP — ULB Fin Status")

if st.sidebar.button("🔄 Refresh data"):
    st.cache_data.clear()

try:
    df = load_data()
except Exception as e:
    st.error(f"Error loading data: {e}")
    st.stop()

divisions = ["All Divisions"] + sorted(df["Division"].unique().tolist())
selected_division = st.sidebar.radio("Division", divisions, index=0)

search = st.sidebar.text_input("Search ULB name")

# ── FILTER ──
filtered = df.copy()
if selected_division != "All Divisions":
    filtered = filtered[filtered["Division"] == selected_division]
if search:
    filtered = filtered[filtered["ULB Name"].str.contains(search, case=False, na=False)]

# ── HEADER ──
st.markdown("### Financial Progress — Overall")
st.caption(f"{len(filtered)} ULBs shown")

# ── KPI CARDS ──
fund_released = filtered["Fund Released"].sum()
expenditure = filtered["Expenditure"].sum()
unspent = filtered["Unspent"].sum()
util_pct = (expenditure / fund_released * 100) if fund_released > 0 else 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("Fund Released", f"₹{fund_released:,.2f} L")
c2.metric("Expenditure", f"₹{expenditure:,.2f} L", f"{util_pct:.1f}% of released")
c3.metric("Unspent", f"₹{unspent:,.2f} L")
c4.metric("% Utilized", f"{util_pct:.1f}%")

# ── TABLE ──
st.markdown("#### ULB-wise Detail")
table = filtered.sort_values("% Util").reset_index(drop=True)


def pct_color(val):
    if val >= 75:
        return "color: #16a34a; font-weight: 600"
    if val >= 40:
        return "color: #d97706; font-weight: 600"
    return "color: #dc2626; font-weight: 600"


st.dataframe(
    table.style
        .format({"Fund Released": "{:,.2f}", "Expenditure": "{:,.2f}", "Unspent": "{:,.2f}", "% Util": "{:.1f}%"})
        .map(pct_color, subset=["% Util"]),
    use_container_width=True,
    height=600,
)
