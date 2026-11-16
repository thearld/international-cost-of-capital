"""
International Cost of Capital Calculator
Compares a project's cost of equity and WACC in USD and a selected country's currency.
Data sourced from Damodaran, OECD, and Trading Economics.
"""

import streamlit as st
import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
from io import BytesIO
from datetime import datetime
import re
import time

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="International Cost of Capital",
    page_icon="🌍",
    layout="wide",
)

# ============================================================
# CONSTANTS & DEFAULTS
# ============================================================
DEFAULT_INDUSTRY = "Software (System & Application)"
DEFAULT_COUNTRY = "United States"
DEFAULT_ERP = 6.5       # percent
DEFAULT_DEBT_SHARE = 30.0  # percent

DAMODARAN_BETAS_URL = "https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls"
DAMODARAN_RATINGS_URL = "https://pages.stern.nyu.edu/adamodar/New_Home_Page/datafile/ratings.html"
TRADING_ECONOMICS_BASE = "https://tradingeconomics.com"
OECD_TAX_SOURCE = "OECD Corporate Tax Statistics 2024 / Tax Foundation"

# ============================================================
# COUNTRY DATA
# ============================================================
# Combined statutory corporate tax rates (central + sub-national)
# Source: Tax Foundation / OECD Corporate Tax Statistics 2024
CORPORATE_TAX_RATES = {
    "Argentina": 35.0, "Australia": 30.0, "Austria": 23.0, "Belgium": 25.0,
    "Brazil": 34.0, "Canada": 26.14, "Chile": 27.0, "China": 25.0,
    "Colombia": 35.0, "Costa Rica": 30.0, "Czech Republic": 21.0,
    "Denmark": 22.0, "Egypt": 22.5, "Estonia": 20.0, "Finland": 20.0,
    "France": 25.83, "Germany": 29.93, "Greece": 22.0, "Hong Kong": 16.5,
    "Hungary": 9.0, "Iceland": 21.0, "India": 30.0, "Indonesia": 22.0,
    "Ireland": 12.5, "Israel": 23.0, "Italy": 27.81, "Japan": 29.74,
    "Kenya": 30.0, "Latvia": 20.0, "Lithuania": 15.0, "Luxembourg": 24.94,
    "Malaysia": 24.0, "Mexico": 30.0, "Morocco": 33.0, "Netherlands": 25.8,
    "New Zealand": 28.0, "Nigeria": 30.0, "Norway": 22.0, "Pakistan": 29.0,
    "Peru": 29.5, "Philippines": 25.0, "Poland": 19.0, "Portugal": 31.5,
    "Qatar": 10.0, "Romania": 16.0, "Russia": 20.0, "Saudi Arabia": 20.0,
    "Serbia": 15.0, "Singapore": 17.0, "Slovakia": 21.0, "Slovenia": 22.0,
    "South Africa": 27.0, "South Korea": 26.4, "Spain": 25.0,
    "Sweden": 20.6, "Switzerland": 19.61, "Taiwan": 20.0, "Thailand": 20.0,
    "Turkey": 25.0, "Ukraine": 18.0, "United Arab Emirates": 9.0,
    "United Kingdom": 25.0, "United States": 25.77, "Vietnam": 20.0,
}

# Trading Economics URL slug for each country
COUNTRY_TE_SLUGS = {
    "Argentina": "argentina", "Australia": "australia", "Austria": "austria",
    "Belgium": "belgium", "Brazil": "brazil", "Canada": "canada",
    "Chile": "chile", "China": "china", "Colombia": "colombia",
    "Costa Rica": "costa-rica", "Czech Republic": "czech-republic",
    "Denmark": "denmark", "Egypt": "egypt", "Estonia": "estonia",
    "Finland": "finland", "France": "france", "Germany": "germany",
    "Greece": "greece", "Hong Kong": "hong-kong", "Hungary": "hungary",
    "Iceland": "iceland", "India": "india", "Indonesia": "indonesia",
    "Ireland": "ireland", "Israel": "israel", "Italy": "italy",
    "Japan": "japan", "Kenya": "kenya", "Latvia": "latvia",
    "Lithuania": "lithuania", "Luxembourg": "luxembourg",
    "Malaysia": "malaysia", "Mexico": "mexico", "Morocco": "morocco",
    "Netherlands": "netherlands", "New Zealand": "new-zealand",
    "Nigeria": "nigeria", "Norway": "norway", "Pakistan": "pakistan",
    "Peru": "peru", "Philippines": "philippines", "Poland": "poland",
    "Portugal": "portugal", "Qatar": "qatar", "Romania": "romania",
    "Russia": "russia", "Saudi Arabia": "saudi-arabia", "Serbia": "serbia",
    "Singapore": "singapore", "Slovakia": "slovakia", "Slovenia": "slovenia",
    "South Africa": "south-africa", "South Korea": "south-korea",
    "Spain": "spain", "Sweden": "sweden", "Switzerland": "switzerland",
    "Taiwan": "taiwan", "Thailand": "thailand", "Turkey": "turkey",
    "Ukraine": "ukraine", "United Arab Emirates": "united-arab-emirates",
    "United Kingdom": "united-kingdom", "United States": "united-states",
    "Vietnam": "vietnam",
}

# Currency codes
COUNTRY_CURRENCIES = {
    "Argentina": "ARS", "Australia": "AUD", "Austria": "EUR",
    "Belgium": "EUR", "Brazil": "BRL", "Canada": "CAD",
    "Chile": "CLP", "China": "CNY", "Colombia": "COP",
    "Costa Rica": "CRC", "Czech Republic": "CZK", "Denmark": "DKK",
    "Egypt": "EGP", "Estonia": "EUR", "Finland": "EUR",
    "France": "EUR", "Germany": "EUR", "Greece": "EUR",
    "Hong Kong": "HKD", "Hungary": "HUF", "Iceland": "ISK",
    "India": "INR", "Indonesia": "IDR", "Ireland": "EUR",
    "Israel": "ILS", "Italy": "EUR", "Japan": "JPY",
    "Kenya": "KES", "Latvia": "EUR", "Lithuania": "EUR",
    "Luxembourg": "EUR", "Malaysia": "MYR", "Mexico": "MXN",
    "Morocco": "MAD", "Netherlands": "EUR", "New Zealand": "NZD",
    "Nigeria": "NGN", "Norway": "NOK", "Pakistan": "PKR",
    "Peru": "PEN", "Philippines": "PHP", "Poland": "PLN",
    "Portugal": "EUR", "Qatar": "QAR", "Romania": "RON",
    "Russia": "RUB", "Saudi Arabia": "SAR", "Serbia": "RSD",
    "Singapore": "SGD", "Slovakia": "EUR", "Slovenia": "EUR",
    "South Africa": "ZAR", "South Korea": "KRW", "Spain": "EUR",
    "Sweden": "SEK", "Switzerland": "CHF", "Taiwan": "TWD",
    "Thailand": "THB", "Turkey": "TRY", "Ukraine": "UAH",
    "United Arab Emirates": "AED", "United Kingdom": "GBP",
    "United States": "USD", "Vietnam": "VND",
}


# ============================================================
# DATA FETCHING FUNCTIONS
# ============================================================

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_damodaran_betas():
    """Download unlevered betas by industry from Damodaran's betas.xls."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Streamlit App)"}
        resp = requests.get(DAMODARAN_BETAS_URL, headers=headers, timeout=30)
        resp.raise_for_status()
        raw = BytesIO(resp.content)

        # Try reading with header=None first to inspect raw structure
        xls = pd.ExcelFile(raw, engine="xlrd")
        sheet = xls.sheet_names[0]
        df_raw = pd.read_excel(xls, sheet_name=sheet, header=None)

        # Search all rows for one that contains 'Industry Name'
        header_row = None
        for i in range(min(20, len(df_raw))):
            row_vals = [str(v).strip().lower() for v in df_raw.iloc[i].values]
            if any("industry name" in v for v in row_vals):
                header_row = i
                break

        if header_row is not None:
            # Use the found row as header
            df = df_raw.iloc[header_row + 1:].copy()
            df.columns = [str(v).strip() for v in df_raw.iloc[header_row].values]
            df = df.reset_index(drop=True)
        else:
            # Maybe pandas already picked up the header; re-read with default header
            raw.seek(0)
            df = pd.read_excel(raw, sheet_name=sheet, engine="xlrd")

        # Clean column names
        df.columns = [str(c).strip() for c in df.columns]

        # Strategy 1: exact column name match
        industry_col = None
        beta_col = None
        for c in df.columns:
            cl = c.lower()
            if "industry" in cl and "name" in cl:
                industry_col = c
            if "unlevered beta" in cl and "cash" not in cl and "correct" not in cl:
                if beta_col is None:
                    beta_col = c

        # Strategy 2: partial match
        if industry_col is None:
            for c in df.columns:
                if "industry" in c.lower():
                    industry_col = c
                    break
        if beta_col is None:
            for c in df.columns:
                if "unlevered" in c.lower() and "beta" in c.lower():
                    beta_col = c
                    break

        # Strategy 3: positional fallback (only if enough columns)
        if industry_col is None and len(df.columns) > 0:
            industry_col = df.columns[0]
        if beta_col is None and len(df.columns) > 5:
            beta_col = df.columns[5]
        elif beta_col is None:
            # Look for any column with mostly small positive floats (beta-like)
            for c in df.columns[1:]:
                vals = pd.to_numeric(df[c], errors="coerce").dropna()
                if len(vals) > 10 and 0 < vals.median() < 3:
                    beta_col = c
                    break

        if industry_col is None or beta_col is None:
            col_list = ", ".join(df.columns[:10].tolist())
            return None, None, f"Could not identify columns. Found: {col_list}"

        result = df[[industry_col, beta_col]].copy()
        result.columns = ["Industry", "Unlevered Beta"]
        result["Industry"] = result["Industry"].astype(str).str.strip()
        result["Unlevered Beta"] = pd.to_numeric(result["Unlevered Beta"], errors="coerce")
        result = result.dropna(subset=["Unlevered Beta"])
        result = result[result["Industry"] != "nan"]
        result = result[~result["Industry"].str.contains("Total Market", case=False, na=False)]
        result = result[result["Unlevered Beta"] > 0]
        result = result.reset_index(drop=True)
        if len(result) < 5:
            return None, None, f"Only {len(result)} industries parsed; check XLS structure"
        return result, datetime.now().strftime("%Y-%m-%d %H:%M"), None
    except Exception as e:
        return None, None, str(e)


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_bbb_spread():
    """Scrape the Baa2/BBB spread for large non-financial service firms from Damodaran."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Streamlit App)"}
        resp = requests.get(DAMODARAN_RATINGS_URL, headers=headers, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all("td")
                cell_texts = [c.get_text(strip=True) for c in cells]
                for i, text in enumerate(cell_texts):
                    if "Baa2/BBB" in text:
                        # The spread is in the next cell
                        if i + 1 < len(cell_texts):
                            spread_text = cell_texts[i + 1]
                            spread_val = float(spread_text.replace("%", "").strip())
                            return spread_val, datetime.now().strftime("%Y-%m-%d %H:%M"), None
        return None, None, "Could not find Baa2/BBB row in ratings table"
    except Exception as e:
        return None, None, str(e)


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_bond_yield(country_slug):
    """Scrape the 10-year government bond yield from Trading Economics for one country."""
    try:
        url = f"{TRADING_ECONOMICS_BASE}/{country_slug}/government-bond-yield"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        # Try multiple strategies to find the yield value
        # Strategy 1: Look for the main value in a known element
        val_el = soup.find("div", {"id": "pnlLast"})
        if val_el:
            text = val_el.get_text(strip=True)
            match = re.search(r"[\d.]+", text)
            if match:
                return float(match.group()), datetime.now().strftime("%Y-%m-%d %H:%M"), None
        # Strategy 2: Look for 'Actual' label pattern
        for tag in soup.find_all(string=re.compile(r"Actual|Last")):
            parent = tag.find_parent()
            if parent:
                sibling_text = parent.get_text(strip=True)
                match = re.search(r"(\d+\.?\d*)", sibling_text)
                if match:
                    val = float(match.group(1))
                    if 0 < val < 50:  # sanity check for yield
                        return val, datetime.now().strftime("%Y-%m-%d %H:%M"), None
        # Strategy 3: Look in meta description or title
        meta = soup.find("meta", {"name": "description"})
        if meta:
            content = meta.get("content", "")
            match = re.search(r"(\d+\.?\d+)\s*percent", content, re.IGNORECASE)
            if not match:
                match = re.search(r"was\s+(\d+\.?\d+)", content)
            if match:
                return float(match.group(1)), datetime.now().strftime("%Y-%m-%d %H:%M"), None
        # Strategy 4: Search for standalone numeric value in title
        title = soup.find("title")
        if title:
            title_text = title.get_text()
            match = re.search(r"(\d+\.\d+)", title_text)
            if match:
                val = float(match.group(1))
                if 0 < val < 50:
                    return val, datetime.now().strftime("%Y-%m-%d %H:%M"), None
        return None, None, "Could not parse yield from page"
    except Exception as e:
        return None, None, str(e)


def fetch_yields_for_countries(us_slug, foreign_slug):
    """Fetch both US and foreign country bond yields."""
    us_yield, us_date, us_err = fetch_bond_yield(us_slug)
    if us_slug == foreign_slug:
        return us_yield, us_date, us_err, us_yield, us_date, us_err
    foreign_yield, foreign_date, foreign_err = fetch_bond_yield(foreign_slug)
    return us_yield, us_date, us_err, foreign_yield, foreign_date, foreign_err


# ============================================================
# CALCULATION FUNCTIONS
# ============================================================

def compute_cost_of_capital(
    beta_u, rf_us, rf_foreign, erp, debt_share,
    tax_rate, bbb_spread_usd, bbb_spread_foreign
):
    """
    Compute cost of equity, cost of debt, and WACC in both USD and foreign currency.

    All inputs in percentage points (e.g., 6.5 for 6.5%).
    Returns dict with all results also in percentage points.
    """
    wd = debt_share / 100.0   # debt weight as decimal
    we = 1.0 - wd             # equity weight as decimal
    t = tax_rate / 100.0      # tax rate as decimal

    # D/E ratio
    de_ratio = wd / we if we > 0 else 0.0

    # Re-lever beta: beta_L = beta_U * (1 + (1 - t) * D/E)
    beta_l = beta_u * (1.0 + (1.0 - t) * de_ratio)

    # --- USD ---
    ke_usd = rf_us + beta_l * erp                  # cost of equity
    kd_usd = rf_us + bbb_spread_usd                # cost of debt (pre-tax)
    wacc_usd = we * ke_usd + wd * kd_usd * (1 - t) # WACC

    # --- Foreign Currency ---
    ke_foreign = rf_foreign + beta_l * erp
    kd_foreign = rf_foreign + bbb_spread_foreign
    wacc_foreign = we * ke_foreign + wd * kd_foreign * (1 - t)

    return {
        "beta_l": beta_l,
        "de_ratio": de_ratio,
        "ke_usd": ke_usd,
        "kd_usd": kd_usd,
        "kd_usd_pretax": kd_usd,
        "kd_usd_aftertax": kd_usd * (1 - t),
        "wacc_usd": wacc_usd,
        "ke_foreign": ke_foreign,
        "kd_foreign": kd_foreign,
        "kd_foreign_pretax": kd_foreign,
        "kd_foreign_aftertax": kd_foreign * (1 - t),
        "wacc_foreign": wacc_foreign,
        "we": we * 100,
        "wd": wd * 100,
    }


def compute_all_industry(
    betas_df, rf_us, rf_foreign, erp, debt_share,
    tax_rate, bbb_spread_usd, bbb_spread_foreign
):
    """Compute WACC for every industry. Returns a DataFrame."""
    rows = []
    for _, row in betas_df.iterrows():
        bu = row["Unlevered Beta"]
        r = compute_cost_of_capital(
            bu, rf_us, rf_foreign, erp, debt_share,
            tax_rate, bbb_spread_usd, bbb_spread_foreign
        )
        rows.append({
            "Industry": row["Industry"],
            "Unlevered Beta": bu,
            "Levered Beta": r["beta_l"],
            "Cost of Equity (USD)": r["ke_usd"],
            "Cost of Debt (USD)": r["kd_usd"],
            "WACC (USD)": r["wacc_usd"],
            "Cost of Equity (Foreign)": r["ke_foreign"],
            "Cost of Debt (Foreign)": r["kd_foreign"],
            "WACC (Foreign)": r["wacc_foreign"],
        })
    return pd.DataFrame(rows)


# ============================================================
# STREAMLIT APP
# ============================================================

def main():
    st.title("🌍 International Cost of Capital Calculator")
    st.caption(
        "Compare a project's cost of equity and WACC in USD and a selected country's currency "
        "using CAPM, Damodaran industry betas, and sovereign yield differentials."
    )

    # ----------------------------------------------------------
    # Initialize session state
    # ----------------------------------------------------------
    if "data_fetched" not in st.session_state:
        st.session_state.data_fetched = False
    if "betas_df" not in st.session_state:
        st.session_state.betas_df = None
    if "bbb_spread" not in st.session_state:
        st.session_state.bbb_spread = None
    if "us_yield" not in st.session_state:
        st.session_state.us_yield = None
    if "foreign_yield" not in st.session_state:
        st.session_state.foreign_yield = None
    if "fetch_errors" not in st.session_state:
        st.session_state.fetch_errors = []

    # ----------------------------------------------------------
    # Data fetching
    # ----------------------------------------------------------
    def do_fetch(selected_country):
        """Fetch all data sources."""
        errors = []
        timestamps = {}

        # 1. Damodaran betas
        betas_df, betas_date, betas_err = fetch_damodaran_betas()
        if betas_err:
            errors.append(f"Betas: {betas_err}")
        else:
            timestamps["betas"] = betas_date
        st.session_state.betas_df = betas_df

        # 2. BBB spread
        spread, spread_date, spread_err = fetch_bbb_spread()
        if spread_err:
            errors.append(f"BBB Spread: {spread_err}")
        else:
            timestamps["spread"] = spread_date
        st.session_state.bbb_spread = spread

        # 3. Bond yields
        us_slug = COUNTRY_TE_SLUGS.get("United States", "united-states")
        foreign_slug = COUNTRY_TE_SLUGS.get(selected_country, "united-states")
        (us_y, us_d, us_e,
         fy, fd, fe) = fetch_yields_for_countries(us_slug, foreign_slug)
        if us_e:
            errors.append(f"US Yield: {us_e}")
        else:
            timestamps["us_yield"] = us_d
        if fe:
            errors.append(f"Foreign Yield: {fe}")
        else:
            timestamps["foreign_yield"] = fd
        st.session_state.us_yield = us_y
        st.session_state.foreign_yield = fy

        st.session_state.fetch_errors = errors
        st.session_state.fetch_timestamps = timestamps
        st.session_state.data_fetched = True

    # ----------------------------------------------------------
    # SIDEBAR
    # ----------------------------------------------------------
    with st.sidebar:
        st.header("Parameters")

        # Country and Industry selection
        country_list = sorted(CORPORATE_TAX_RATES.keys())
        default_country_idx = country_list.index(DEFAULT_COUNTRY) if DEFAULT_COUNTRY in country_list else 0
        selected_country = st.selectbox(
            "Target Country", country_list, index=default_country_idx
        )
        currency = COUNTRY_CURRENCIES.get(selected_country, "LCL")

        # Fetch data on first load or country change
        if (not st.session_state.data_fetched
            or st.session_state.get("prev_country") != selected_country):
            with st.spinner("Fetching data..."):
                do_fetch(selected_country)
            st.session_state.prev_country = selected_country

        # Industry selection
        industry_list = []
        if st.session_state.betas_df is not None:
            industry_list = st.session_state.betas_df["Industry"].tolist()
        if not industry_list:
            industry_list = [DEFAULT_INDUSTRY]
        default_ind_idx = (
            industry_list.index(DEFAULT_INDUSTRY)
            if DEFAULT_INDUSTRY in industry_list else 0
        )
        selected_industry = st.selectbox(
            "Industry", industry_list, index=default_ind_idx
        )

        # Get fetched beta for selected industry
        fetched_beta = None
        if st.session_state.betas_df is not None:
            match = st.session_state.betas_df[
                st.session_state.betas_df["Industry"] == selected_industry
            ]
            if not match.empty:
                fetched_beta = float(match.iloc[0]["Unlevered Beta"])

        st.divider()

        # ERP and Debt Share
        erp = st.slider(
            "Equity Risk Premium (%)", 0.0, 15.0, DEFAULT_ERP, 0.1,
            help="Market equity risk premium applied to levered beta"
        )
        debt_share = st.slider(
            "Debt Financing Share (%)", 0.0, 100.0, DEFAULT_DEBT_SHARE, 1.0,
            help="Target debt / (debt + equity) for the project"
        )

        # Tax rate toggle
        us_tax = CORPORATE_TAX_RATES.get("United States", 25.77)
        foreign_tax = CORPORATE_TAX_RATES.get(selected_country, 25.0)
        use_us_tax = st.toggle(
            "Use U.S. Tax Rate", value=True,
            help="Switch between U.S. and selected country's corporate tax rate"
        )
        project_tax_label = "U.S." if use_us_tax else selected_country
        project_tax = us_tax if use_us_tax else foreign_tax

        st.divider()

        # Manual overrides
        st.subheader("Manual Overrides")
        st.caption("Toggle on to override fetched data with manual inputs.")

        # Unlevered Beta
        override_beta = st.toggle("Override Unlevered Beta", value=False)
        if override_beta:
            manual_beta = st.number_input(
                "Unlevered Beta",
                value=fetched_beta if fetched_beta else 1.0,
                min_value=0.0, max_value=5.0, step=0.01, format="%.4f"
            )
        else:
            manual_beta = fetched_beta

        # Tax Rates
        override_tax = st.toggle("Override Tax Rates", value=False)
        if override_tax:
            manual_us_tax = st.number_input(
                "U.S. Tax Rate (%)", value=us_tax,
                min_value=0.0, max_value=60.0, step=0.1, format="%.2f"
            )
            manual_foreign_tax = st.number_input(
                f"{selected_country} Tax Rate (%)", value=foreign_tax,
                min_value=0.0, max_value=60.0, step=0.1, format="%.2f"
            )
            us_tax = manual_us_tax
            foreign_tax = manual_foreign_tax
            project_tax = us_tax if use_us_tax else foreign_tax

        # BBB Spread
        fetched_spread = st.session_state.bbb_spread
        override_spread = st.toggle("Override USD BBB Spread", value=False)
        if override_spread:
            manual_spread = st.number_input(
                "USD BBB Spread (%)", value=fetched_spread if fetched_spread else 1.11,
                min_value=0.0, max_value=10.0, step=0.01, format="%.2f"
            )
        else:
            manual_spread = fetched_spread

        # Bond Yields
        fetched_us_yield = st.session_state.us_yield
        fetched_foreign_yield = st.session_state.foreign_yield
        override_yields = st.toggle("Override Bond Yields", value=False)
        if override_yields:
            manual_us_yield = st.number_input(
                "U.S. 10-Year Yield (%)",
                value=fetched_us_yield if fetched_us_yield else 4.5,
                min_value=0.0, max_value=30.0, step=0.01, format="%.2f"
            )
            manual_foreign_yield = st.number_input(
                f"{selected_country} 10-Year Yield (%)",
                value=fetched_foreign_yield if fetched_foreign_yield else 4.5,
                min_value=0.0, max_value=50.0, step=0.01, format="%.2f"
            )
        else:
            manual_us_yield = fetched_us_yield
            manual_foreign_yield = fetched_foreign_yield

        # Foreign BBB Spread
        auto_foreign_spread = manual_spread  # auto = same as USD spread
        override_foreign_spread = st.toggle(
            "Override Foreign BBB Spread", value=False,
            help="When off, the foreign BBB spread equals the USD BBB spread (same credit quality assumption)."
        )
        if override_foreign_spread:
            manual_foreign_spread = st.number_input(
                f"{currency} BBB Spread (%)",
                value=auto_foreign_spread if auto_foreign_spread else 1.11,
                min_value=0.0, max_value=20.0, step=0.01, format="%.2f"
            )
        else:
            manual_foreign_spread = auto_foreign_spread

        st.divider()

        # Refresh button
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.session_state.data_fetched = False
            st.rerun()

    # ----------------------------------------------------------
    # VALIDATE INPUTS
    # ----------------------------------------------------------
    missing = []
    if manual_beta is None:
        missing.append("Unlevered Beta (enable override or check data fetch)")
    if manual_us_yield is None:
        missing.append("U.S. 10-Year Yield (enable override or check data fetch)")
    if manual_foreign_yield is None:
        missing.append(f"{selected_country} 10-Year Yield (enable override or check data fetch)")
    if manual_spread is None:
        missing.append("USD BBB Spread (enable override or check data fetch)")

    if missing:
        st.warning(
            "Some data could not be fetched automatically. "
            "Please enable manual overrides in the sidebar for: "
            + ", ".join(missing)
        )
        if st.session_state.fetch_errors:
            with st.expander("Fetch error details"):
                for err in st.session_state.fetch_errors:
                    st.error(err)
        st.stop()

    # ----------------------------------------------------------
    # COMPUTE RESULTS
    # ----------------------------------------------------------
    results = compute_cost_of_capital(
        beta_u=manual_beta,
        rf_us=manual_us_yield,
        rf_foreign=manual_foreign_yield,
        erp=erp,
        debt_share=debt_share,
        tax_rate=project_tax,
        bbb_spread_usd=manual_spread,
        bbb_spread_foreign=manual_foreign_spread,
    )

    # ----------------------------------------------------------
    # DATA SOURCES TABLE
    # ----------------------------------------------------------
    with st.expander("📡 Data Sources & Fetched Values", expanded=False):
        src_data = {
            "Parameter": [
                "Unlevered Beta",
                "USD BBB Spread",
                f"U.S. 10-Year Yield",
                f"{selected_country} 10-Year Yield",
                f"U.S. Tax Rate",
                f"{selected_country} Tax Rate",
            ],
            "Fetched Value": [
                f"{fetched_beta:.4f}" if fetched_beta else "N/A",
                f"{fetched_spread:.2f}%" if fetched_spread else "N/A",
                f"{fetched_us_yield:.2f}%" if fetched_us_yield else "N/A",
                f"{fetched_foreign_yield:.2f}%" if fetched_foreign_yield else "N/A",
                f"{CORPORATE_TAX_RATES.get('United States', 'N/A')}%",
                f"{CORPORATE_TAX_RATES.get(selected_country, 'N/A')}%",
            ],
            "Used Value": [
                f"{manual_beta:.4f}",
                f"{manual_spread:.2f}%",
                f"{manual_us_yield:.2f}%",
                f"{manual_foreign_yield:.2f}%",
                f"{us_tax:.2f}%",
                f"{foreign_tax:.2f}%",
            ],
            "Source": [
                "Damodaran (Jan 2026)",
                "Damodaran Ratings",
                "Trading Economics",
                "Trading Economics",
                OECD_TAX_SOURCE,
                OECD_TAX_SOURCE,
            ],
            "Override": [
                "Yes" if override_beta else "No",
                "Yes" if override_spread else "No",
                "Yes" if override_yields else "No",
                "Yes" if override_yields else "No",
                "Yes" if override_tax else "No",
                "Yes" if override_tax else "No",
            ],
        }
        st.dataframe(
            pd.DataFrame(src_data),
            hide_index=True,
            use_container_width=True,
        )
        st.caption(
            "**Sources:** "
            "[Damodaran Betas](https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls) · "
            "[Damodaran Ratings/Spreads](https://pages.stern.nyu.edu/adamodar/New_Home_Page/datafile/ratings.html) · "
            "[OECD Tax Rates](https://www.oecd.org/en/publications/corporate-tax-statistics-2024_9c27d6e8-en/full-report/statutory-corporate-income-tax-rates_440f9286.html) · "
            "[Trading Economics Bonds](https://tradingeconomics.com/bonds)"
        )
        if st.session_state.fetch_errors:
            st.warning("Some fetches had errors (manual overrides may be needed):")
            for err in st.session_state.fetch_errors:
                st.caption(f"⚠️ {err}")

    # ----------------------------------------------------------
    # RESULTS: SIDE-BY-SIDE
    # ----------------------------------------------------------
    st.subheader("Cost of Capital Comparison")

    is_same_country = (selected_country == "United States")
    foreign_label = f"{selected_country} ({currency})" if not is_same_country else "USD (same country)"

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 🇺🇸 USD")
        st.metric("Cost of Equity", f"{results['ke_usd']:.2f}%")
        st.caption(
            f"Rf {manual_us_yield:.2f}% + β({results['beta_l']:.4f}) × ERP({erp:.1f}%)"
        )
        st.metric("Cost of Debt (pre-tax)", f"{results['kd_usd']:.2f}%")
        st.caption(
            f"Rf {manual_us_yield:.2f}% + BBB spread {manual_spread:.2f}%"
        )
        st.metric("Cost of Debt (after-tax)", f"{results['kd_usd_aftertax']:.2f}%")
        st.caption(
            f"{results['kd_usd']:.2f}% × (1 - {project_tax:.2f}%)"
        )
        st.metric("**WACC**", f"{results['wacc_usd']:.2f}%")
        st.caption(
            f"Equity {results['we']:.0f}% × {results['ke_usd']:.2f}% + "
            f"Debt {results['wd']:.0f}% × {results['kd_usd']:.2f}% × (1 - {project_tax:.2f}%)"
        )

    with col2:
        flag = "" if is_same_country else "🌐"
        st.markdown(f"### {flag} {foreign_label}")
        st.metric("Cost of Equity", f"{results['ke_foreign']:.2f}%")
        st.caption(
            f"Rf {manual_foreign_yield:.2f}% + β({results['beta_l']:.4f}) × ERP({erp:.1f}%)"
        )
        st.metric("Cost of Debt (pre-tax)", f"{results['kd_foreign']:.2f}%")
        spread_label = "override" if override_foreign_spread else "auto = USD spread"
        st.caption(
            f"Rf {manual_foreign_yield:.2f}% + BBB spread {manual_foreign_spread:.2f}% ({spread_label})"
        )
        st.metric("Cost of Debt (after-tax)", f"{results['kd_foreign_aftertax']:.2f}%")
        st.caption(
            f"{results['kd_foreign']:.2f}% × (1 - {project_tax:.2f}%)"
        )
        st.metric("**WACC**", f"{results['wacc_foreign']:.2f}%")
        st.caption(
            f"Equity {results['we']:.0f}% × {results['ke_foreign']:.2f}% + "
            f"Debt {results['wd']:.0f}% × {results['kd_foreign']:.2f}% × (1 - {project_tax:.2f}%)"
        )

    # Difference summary
    if not is_same_country:
        diff = results["wacc_foreign"] - results["wacc_usd"]
        direction = "higher" if diff > 0 else "lower"
        st.info(
            f"The {currency} WACC is **{abs(diff):.2f}pp** {direction} than the USD WACC, "
            f"driven by the {currency} risk-free rate being "
            f"{'higher' if manual_foreign_yield > manual_us_yield else 'lower'} "
            f"than the U.S. rate ({manual_foreign_yield:.2f}% vs. {manual_us_yield:.2f}%)."
        )

    # ----------------------------------------------------------
    # KEY ASSUMPTIONS
    # ----------------------------------------------------------
    with st.expander("📋 Key Assumptions & Methodology", expanded=False):
        st.markdown(f"""
**Model:** Capital Asset Pricing Model (CAPM) with yield-differential currency conversion.

**Shared parameters across both currencies:**
- **Industry:** {selected_industry} (unlevered beta = {manual_beta:.4f})
- **Levered beta:** {results['beta_l']:.4f} = {manual_beta:.4f} × [1 + (1 - {project_tax:.2f}%) × {results['de_ratio']:.4f}]
- **Equity risk premium:** {erp:.1f}%
- **Debt share:** {debt_share:.0f}% debt / {100 - debt_share:.0f}% equity
- **Project tax rate:** {project_tax:.2f}% ({project_tax_label})

**Currency conversion approach:**
The cost of capital in each currency uses that country's 10-year government bond yield as the
risk-free rate. The equity risk premium and credit spread are held constant across currencies
(same real project risk), so the only driver of the difference is the risk-free rate gap.

- Cost of equity = Rf + Levered Beta × ERP
- Cost of debt = Rf + BBB spread
- WACC = (E/V) × Ke + (D/V) × Kd × (1 - t)

When the foreign BBB spread override is off, the foreign spread equals the USD spread,
reflecting the assumption that credit quality is the same regardless of the currency of
borrowing. This means:
- **Equal yields produce equal results** when the foreign spread override is off.
- **Zero debt makes WACC equal to cost of equity.**
- **Overriding the foreign spread leaves USD results unchanged.**
""")

    # ----------------------------------------------------------
    # ALL-INDUSTRY COMPARISON
    # ----------------------------------------------------------
    st.subheader("🏭 All-Industry Comparison")

    if st.session_state.betas_df is not None:
        all_df = compute_all_industry(
            st.session_state.betas_df,
            manual_us_yield, manual_foreign_yield, erp, debt_share,
            project_tax, manual_spread, manual_foreign_spread,
        )

        # Chart
        chart_col = "WACC (USD)" if is_same_country else None
        if not is_same_country:
            chart_df = all_df[["Industry", "WACC (USD)", "WACC (Foreign)"]].copy()
            chart_df = chart_df.rename(columns={
                "WACC (USD)": "WACC USD (%)",
                "WACC (Foreign)": f"WACC {currency} (%)",
            })
            chart_df = chart_df.sort_values("WACC USD (%)", ascending=True)
            chart_melted = chart_df.melt(
                id_vars="Industry", var_name="Currency", value_name="WACC (%)"
            )
            import plotly.express as px
            fig = px.bar(
                chart_melted, x="WACC (%)", y="Industry", color="Currency",
                barmode="group", orientation="h",
                height=max(400, len(all_df) * 18),
                color_discrete_sequence=["#1f77b4", "#2ca02c"],
            )
            fig.update_layout(yaxis={"categoryorder": "total ascending"}, margin=dict(l=10))
            st.plotly_chart(fig, use_container_width=True)
        else:
            chart_df = all_df[["Industry", "WACC (USD)"]].copy()
            chart_df = chart_df.sort_values("WACC (USD)", ascending=True)
            import plotly.express as px
            fig = px.bar(
                chart_df, x="WACC (USD)", y="Industry",
                orientation="h",
                height=max(400, len(all_df) * 16),
                color_discrete_sequence=["#1f77b4"],
            )
            fig.update_layout(margin=dict(l=10))
            st.plotly_chart(fig, use_container_width=True)

        # Highlight selected industry
        highlight = all_df[all_df["Industry"] == selected_industry]
        if not highlight.empty:
            st.info(
                f"**{selected_industry}:** "
                f"WACC (USD) = {highlight.iloc[0]['WACC (USD)']:.2f}% | "
                f"WACC ({currency}) = {highlight.iloc[0]['WACC (Foreign)']:.2f}%"
            )

        # Full table
        with st.expander("Full Industry Table"):
            display_df = all_df.copy()
            display_df = display_df.rename(columns={
                "WACC (Foreign)": f"WACC ({currency})",
                "Cost of Equity (Foreign)": f"Cost of Equity ({currency})",
                "Cost of Debt (Foreign)": f"Cost of Debt ({currency})",
            })
            # Format numeric columns
            for col in display_df.columns:
                if col != "Industry":
                    display_df[col] = display_df[col].apply(
                        lambda x: f"{x:.2f}" if isinstance(x, (int, float)) else x
                    )
            st.dataframe(display_df, hide_index=True, use_container_width=True)

        # ----------------------------------------------------------
        # DOWNLOAD
        # ----------------------------------------------------------
        st.subheader("💾 Download Results")

        # Summary results
        summary_data = {
            "Metric": [
                "Industry", "Country", "Currency",
                "Unlevered Beta", "Levered Beta", "Equity Risk Premium (%)",
                "Debt Share (%)", "Project Tax Rate (%)", "Tax Jurisdiction",
                "U.S. Rf (%)", f"{selected_country} Rf (%)",
                "USD BBB Spread (%)", f"{currency} BBB Spread (%)",
                "Cost of Equity USD (%)", f"Cost of Equity {currency} (%)",
                "Cost of Debt USD pre-tax (%)", f"Cost of Debt {currency} pre-tax (%)",
                "Cost of Debt USD after-tax (%)", f"Cost of Debt {currency} after-tax (%)",
                "WACC USD (%)", f"WACC {currency} (%)",
            ],
            "Value": [
                selected_industry, selected_country, currency,
                f"{manual_beta:.4f}", f"{results['beta_l']:.4f}", f"{erp:.1f}",
                f"{debt_share:.0f}", f"{project_tax:.2f}", project_tax_label,
                f"{manual_us_yield:.2f}", f"{manual_foreign_yield:.2f}",
                f"{manual_spread:.2f}", f"{manual_foreign_spread:.2f}",
                f"{results['ke_usd']:.2f}", f"{results['ke_foreign']:.2f}",
                f"{results['kd_usd']:.2f}", f"{results['kd_foreign']:.2f}",
                f"{results['kd_usd_aftertax']:.2f}", f"{results['kd_foreign_aftertax']:.2f}",
                f"{results['wacc_usd']:.2f}", f"{results['wacc_foreign']:.2f}",
            ],
        }
        summary_df = pd.DataFrame(summary_data)

        col_d1, col_d2 = st.columns(2)
        with col_d1:
            csv_summary = summary_df.to_csv(index=False)
            st.download_button(
                "📥 Download Summary (CSV)",
                csv_summary,
                f"cost_of_capital_summary_{selected_country.replace(' ', '_')}.csv",
                "text/csv",
                use_container_width=True,
            )
        with col_d2:
            # All-industry CSV
            csv_all = all_df.to_csv(index=False)
            st.download_button(
                "📥 Download All Industries (CSV)",
                csv_all,
                f"all_industry_wacc_{selected_country.replace(' ', '_')}.csv",
                "text/csv",
                use_container_width=True,
            )
    else:
        st.error(
            "Industry beta data could not be loaded. "
            "Please check the data source or try refreshing."
        )


if __name__ == "__main__":
    main()
