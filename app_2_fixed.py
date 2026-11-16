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
# FALLBACK DATA (used when live scraping fails, e.g. on Streamlit Cloud)
# ============================================================

# Source: Damodaran Online, Jan 2026 betas.xls
FALLBACK_BETAS = {
    "Advertising": 1.11, "Aerospace/Defense": 1.07, "Air Transport": 1.14,
    "Apparel": 0.88, "Auto & Truck": 0.76, "Auto Parts": 1.05,
    "Bank (Money Center)": 0.56, "Banks (Regional)": 0.49,
    "Beverage (Alcoholic)": 0.70, "Beverage (Soft)": 0.62,
    "Broadcasting": 0.85, "Brokerage & Investment Banking": 0.78,
    "Building Materials": 0.85, "Business & Consumer Services": 0.93,
    "Cable TV": 0.95, "Chemical (Basic)": 0.84, "Chemical (Diversified)": 1.08,
    "Chemical (Specialty)": 0.98, "Coal & Related Energy": 0.78,
    "Computer Services": 1.11, "Computers/Peripherals": 1.17,
    "Construction Supplies": 0.89, "Diversified": 0.72,
    "Drugs (Biotechnology)": 1.28, "Drugs (Pharmaceutical)": 1.01,
    "Education": 0.98, "Electrical Equipment": 1.17,
    "Electronics (Consumer & Office)": 1.12, "Electronics (General)": 1.05,
    "Engineering/Construction": 1.04, "Entertainment": 1.05,
    "Environmental & Waste Services": 0.82, "Farming/Agriculture": 0.68,
    "Financial Svcs. (Non-bank & Insurance)": 0.47,
    "Food Processing": 0.63, "Food Wholesalers": 0.56,
    "Furn/Home Furnishings": 0.88, "Green & Renewable Energy": 0.72,
    "Healthcare Products": 1.01, "Healthcare Support Services": 0.98,
    "Healthcare Information and Technology": 1.17,
    "Heathcare Information and Technology": 1.17,
    "Homebuilding": 0.86, "Hospitals/Healthcare Facilities": 0.74,
    "Hotel/Gaming": 0.89, "Household Products": 0.73,
    "Information Services": 1.07, "Insurance (General)": 0.71,
    "Insurance (Life)": 0.78, "Insurance (Prop/Cas.)": 0.68,
    "Investments & Asset Management": 0.84,
    "Machinery": 1.02, "Metals & Mining": 0.88,
    "Office Equipment & Services": 0.99, "Oil/Gas (Integrated)": 0.86,
    "Oil/Gas (Production and Exploration)": 0.95,
    "Oil/Gas Distribution": 0.73, "Oilfield Svcs/Equip.": 1.14,
    "Packaging & Container": 0.72, "Paper/Forest Products": 0.73,
    "Power": 0.49, "Precious Metals": 0.98,
    "Publishing & Newspapers": 0.90, "R.E.I.T.": 0.63,
    "Real Estate (Development)": 0.48, "Real Estate (General/Diversified)": 0.60,
    "Real Estate (Operations & Services)": 0.74,
    "Recreation": 0.86, "Reinsurance": 0.63,
    "Restaurant/Dining": 0.72, "Retail (Automotive)": 0.82,
    "Retail (Building Supply)": 0.91, "Retail (Distributors)": 0.89,
    "Retail (General)": 0.83, "Retail (Grocery and Food)": 0.47,
    "Retail (Online)": 1.24, "Retail (Special Lines)": 0.85,
    "Rubber& Tires": 0.80, "Semiconductor": 1.37,
    "Semiconductor Equip": 1.37, "Shipbuilding & Marine": 0.78,
    "Shoe": 0.86, "Software (Entertainment)": 1.19,
    "Software (Internet)": 1.26, "Software (System & Application)": 1.23,
    "Steel": 0.95, "Telecom (Wireless)": 0.72,
    "Telecom. Equipment": 1.11, "Telecom. Services": 0.73,
    "Tobacco": 0.60, "Transportation": 0.80,
    "Transportation (Railroads)": 0.83, "Trucking": 0.80,
    "Utility (General)": 0.44, "Utility (Water)": 0.48,
}

# Source: Damodaran Country Risk Premiums, Nov 2026 (ctryprem.html)
COUNTRY_RISK_PREMIUMS = {
    "Argentina": 11.84, "Australia": 0.00, "Austria": 0.46,
    "Belgium": 0.78, "Brazil": 2.36, "Canada": 0.00,
    "Chile": 0.78, "China": 0.78, "Colombia": 2.36,
    "Costa Rica": 2.57, "Czech Republic": 0.46, "Denmark": 0.00,
    "Egypt": 7.57, "Estonia": 0.46, "Finland": 0.00,
    "France": 0.46, "Germany": 0.00, "Greece": 2.57,
    "Hong Kong": 0.46, "Hungary": 1.44, "Iceland": 0.78,
    "India": 1.44, "Indonesia": 1.73, "Ireland": 0.46,
    "Israel": 0.78, "Italy": 1.44, "Japan": 0.46,
    "Kenya": 5.29, "Latvia": 0.78, "Lithuania": 0.78,
    "Luxembourg": 0.00, "Malaysia": 0.78, "Mexico": 1.44,
    "Morocco": 2.57, "Netherlands": 0.00, "New Zealand": 0.00,
    "Nigeria": 5.29, "Norway": 0.00, "Pakistan": 7.57,
    "Peru": 1.44, "Philippines": 1.73, "Poland": 0.78,
    "Portugal": 1.44, "Qatar": 0.78, "Romania": 1.73,
    "Russia": 7.57, "Saudi Arabia": 0.78, "Serbia": 2.57,
    "Singapore": 0.00, "Slovakia": 0.78, "Slovenia": 0.46,
    "South Africa": 2.57, "South Korea": 0.46, "Spain": 0.78,
    "Sweden": 0.00, "Switzerland": 0.00, "Taiwan": 0.46,
    "Thailand": 1.44, "Turkey": 3.84, "Ukraine": 11.84,
    "United Arab Emirates": 0.78, "United Kingdom": 0.78,
    "United States": 0.23, "Vietnam": 2.57,
}

# Source: OECD / statisticsoftheworld.com, Oct 2026 (10-year government bond yields)
FALLBACK_BOND_YIELDS = {
    "Argentina": 12.00, "Australia": 5.28, "Austria": 3.60,
    "Belgium": 4.38, "Brazil": 9.29, "Canada": 3.90,
    "Chile": 5.80, "China": 1.68, "Colombia": 10.00,
    "Costa Rica": 7.50, "Czech Republic": 4.20, "Denmark": 3.30,
    "Egypt": 22.00, "Estonia": 3.60, "Finland": 3.60,
    "France": 4.90, "Germany": 3.42, "Greece": 4.00,
    "Hong Kong": 4.70, "Hungary": 7.17, "Iceland": 6.50,
    "India": 7.38, "Indonesia": 6.90, "Ireland": 3.60,
    "Israel": 5.30, "Italy": 4.36, "Japan": 3.05,
    "Kenya": 12.50, "Latvia": 3.60, "Lithuania": 3.60,
    "Luxembourg": 3.50, "Malaysia": 4.10, "Mexico": 9.25,
    "Morocco": 4.50, "Netherlands": 3.50, "New Zealand": 5.10,
    "Nigeria": 15.00, "Norway": 4.33, "Pakistan": 13.50,
    "Peru": 6.90, "Philippines": 6.20, "Poland": 5.74,
    "Portugal": 3.90, "Qatar": 5.00, "Romania": 7.50,
    "Russia": 15.00, "Saudi Arabia": 5.20, "Serbia": 6.50,
    "Singapore": 3.60, "Slovakia": 4.00, "Slovenia": 3.70,
    "South Africa": 9.90, "South Korea": 4.21, "Spain": 4.00,
    "Sweden": 3.42, "Switzerland": 0.51, "Taiwan": 2.30,
    "Thailand": 2.70, "Turkey": 29.00, "Ukraine": 20.00,
    "United Arab Emirates": 5.00, "United Kingdom": 5.34,
    "United States": 5.13, "Vietnam": 3.00,
}

# Fallback BBB spread (Damodaran ratings table, Nov 2026)
FALLBACK_BBB_SPREAD = 1.11

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
# DATA FETCHING FUNCTIONS (with fallback)
# ============================================================

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_damodaran_betas():
    """Download unlevered betas by industry from Damodaran's betas.xls.
    Falls back to hardcoded data if the fetch fails (common on cloud servers)."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Streamlit App)"}
        resp = requests.get(DAMODARAN_BETAS_URL, headers=headers, timeout=30)
        resp.raise_for_status()
        raw = BytesIO(resp.content)

        xls = pd.ExcelFile(raw, engine="xlrd")
        sheet = xls.sheet_names[0]
        df_raw = pd.read_excel(xls, sheet_name=sheet, header=None)

        header_row = None
        for i in range(min(20, len(df_raw))):
            row_vals = [str(v).strip().lower() for v in df_raw.iloc[i].values]
            if any("industry name" in v for v in row_vals):
                header_row = i
                break

        if header_row is not None:
            df = df_raw.iloc[header_row + 1:].copy()
            df.columns = [str(v).strip() for v in df_raw.iloc[header_row].values]
            df = df.reset_index(drop=True)
        else:
            raw.seek(0)
            df = pd.read_excel(raw, sheet_name=sheet, engine="xlrd")

        df.columns = [str(c).strip() for c in df.columns]

        industry_col = None
        beta_col = None
        for c in df.columns:
            cl = c.lower()
            if "industry" in cl and "name" in cl:
                industry_col = c
            if "unlevered beta" in cl and "cash" not in cl and "correct" not in cl:
                if beta_col is None:
                    beta_col = c

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

        if industry_col is None and len(df.columns) > 0:
            industry_col = df.columns[0]
        if beta_col is None and len(df.columns) > 5:
            beta_col = df.columns[5]
        elif beta_col is None:
            for c in df.columns[1:]:
                vals = pd.to_numeric(df[c], errors="coerce").dropna()
                if len(vals) > 10 and 0 < vals.median() < 3:
                    beta_col = c
                    break

        if industry_col is None or beta_col is None:
            col_list = ", ".join(df.columns[:10].tolist())
            raise ValueError(f"Could not identify columns. Found: {col_list}")

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
            raise ValueError(f"Only {len(result)} industries parsed; check XLS structure")
        return result, datetime.now().strftime("%Y-%m-%d %H:%M"), None, "live"
    except Exception as e:
        # Fall back to hardcoded betas
        fb = pd.DataFrame([
            {"Industry": k, "Unlevered Beta": v}
            for k, v in sorted(FALLBACK_BETAS.items())
        ])
        return fb, "Fallback (Jan 2026)", f"Live fetch failed: {e}", "fallback"


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_bbb_spread():
    """Scrape the Baa2/BBB spread from Damodaran. Falls back to hardcoded value."""
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
                        if i + 1 < len(cell_texts):
                            spread_text = cell_texts[i + 1]
                            spread_val = float(spread_text.replace("%", "").strip())
                            return spread_val, datetime.now().strftime("%Y-%m-%d %H:%M"), None, "live"
        raise ValueError("Could not find Baa2/BBB row in ratings table")
    except Exception as e:
        return FALLBACK_BBB_SPREAD, "Fallback (Nov 2026)", f"Live fetch failed: {e}", "fallback"


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_bond_yield(country_slug, country_name=None):
    """Scrape the 10-year government bond yield from Trading Economics.
    Falls back to hardcoded yields if scraping fails."""
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

        val_el = soup.find("div", {"id": "pnlLast"})
        if val_el:
            text = val_el.get_text(strip=True)
            match = re.search(r"[\d.]+", text)
            if match:
                return float(match.group()), datetime.now().strftime("%Y-%m-%d %H:%M"), None, "live"

        for tag in soup.find_all(string=re.compile(r"Actual|Last")):
            parent = tag.find_parent()
            if parent:
                sibling_text = parent.get_text(strip=True)
                match = re.search(r"(\d+\.?\d*)", sibling_text)
                if match:
                    val = float(match.group(1))
                    if 0 < val < 50:
                        return val, datetime.now().strftime("%Y-%m-%d %H:%M"), None, "live"

        meta = soup.find("meta", {"name": "description"})
        if meta:
            content = meta.get("content", "")
            match = re.search(r"(\d+\.?\d+)\s*percent", content, re.IGNORECASE)
            if not match:
                match = re.search(r"was\s+(\d+\.?\d+)", content)
            if match:
                return float(match.group(1)), datetime.now().strftime("%Y-%m-%d %H:%M"), None, "live"

        title = soup.find("title")
        if title:
            title_text = title.get_text()
            match = re.search(r"(\d+\.\d+)", title_text)
            if match:
                val = float(match.group(1))
                if 0 < val < 50:
                    return val, datetime.now().strftime("%Y-%m-%d %H:%M"), None, "live"

        raise ValueError("Could not parse yield from page")
    except Exception as e:
        # Fall back to hardcoded yield
        if country_name and country_name in FALLBACK_BOND_YIELDS:
            return FALLBACK_BOND_YIELDS[country_name], "Fallback (Oct 2026)", f"Live fetch failed: {e}", "fallback"
        return None, None, str(e), "failed"


def fetch_yields_for_countries(us_slug, foreign_slug, foreign_country_name):
    """Fetch both US and foreign country bond yields."""
    us_yield, us_date, us_err, us_src = fetch_bond_yield(us_slug, "United States")
    if us_slug == foreign_slug:
        return us_yield, us_date, us_err, us_src, us_yield, us_date, us_err, us_src
    foreign_yield, foreign_date, foreign_err, foreign_src = fetch_bond_yield(
        foreign_slug, foreign_country_name
    )
    return us_yield, us_date, us_err, us_src, foreign_yield, foreign_date, foreign_err, foreign_src


# ============================================================
# CALCULATION FUNCTIONS
# ============================================================

def compute_cost_of_capital(
    beta_u, rf_us, rf_foreign, erp_us, crp_foreign,
    debt_share, tax_rate, bbb_spread_usd, bbb_spread_foreign
):
    """
    Compute cost of equity, cost of debt, and WACC in both USD and foreign currency.

    All inputs in percentage points (e.g., 6.5 for 6.5%).
    erp_us: US equity risk premium (e.g. 6.5%)
    crp_foreign: Country risk premium for the foreign country (e.g. 0.78% for Belgium)

    Foreign ERP = US ERP + (Foreign CRP - US CRP)
    This adjusts the equity risk premium for additional country-specific risk.

    Returns dict with all results also in percentage points.
    """
    wd = debt_share / 100.0   # debt weight as decimal
    we = 1.0 - wd             # equity weight as decimal
    t = tax_rate / 100.0      # tax rate as decimal

    # D/E ratio
    de_ratio = wd / we if we > 0 else 0.0

    # Re-lever beta: beta_L = beta_U * (1 + (1 - t) * D/E)
    beta_l = beta_u * (1.0 + (1.0 - t) * de_ratio)

    # Country risk premium adjustment
    us_crp = COUNTRY_RISK_PREMIUMS.get("United States", 0.23)
    erp_foreign = erp_us + (crp_foreign - us_crp)

    # --- USD ---
    ke_usd = rf_us + beta_l * erp_us                  # cost of equity
    kd_usd = rf_us + bbb_spread_usd                   # cost of debt (pre-tax)
    wacc_usd = we * ke_usd + wd * kd_usd * (1 - t)   # WACC

    # --- Foreign Currency ---
    ke_foreign = rf_foreign + beta_l * erp_foreign
    kd_foreign = rf_foreign + bbb_spread_foreign
    wacc_foreign = we * ke_foreign + wd * kd_foreign * (1 - t)

    return {
        "beta_l": beta_l,
        "de_ratio": de_ratio,
        "erp_us": erp_us,
        "erp_foreign": erp_foreign,
        "crp_foreign": crp_foreign,
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
    betas_df, rf_us, rf_foreign, erp_us, crp_foreign,
    debt_share, tax_rate, bbb_spread_usd, bbb_spread_foreign
):
    """Compute WACC for every industry. Returns a DataFrame."""
    rows = []
    for _, row in betas_df.iterrows():
        bu = row["Unlevered Beta"]
        r = compute_cost_of_capital(
            bu, rf_us, rf_foreign, erp_us, crp_foreign,
            debt_share, tax_rate, bbb_spread_usd, bbb_spread_foreign
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
    st.title("International Cost of Capital Calculator")
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
    if "data_sources" not in st.session_state:
        st.session_state.data_sources = {}

    # ----------------------------------------------------------
    # Data fetching
    # ----------------------------------------------------------
    def do_fetch(selected_country):
        """Fetch all data sources (with automatic fallback to hardcoded data)."""
        errors = []
        timestamps = {}
        sources = {}

        # 1. Damodaran betas
        betas_df, betas_date, betas_err, betas_src = fetch_damodaran_betas()
        if betas_err:
            errors.append(f"Betas: {betas_err}")
        timestamps["betas"] = betas_date
        sources["betas"] = betas_src
        st.session_state.betas_df = betas_df

        # 2. BBB spread
        spread, spread_date, spread_err, spread_src = fetch_bbb_spread()
        if spread_err:
            errors.append(f"BBB Spread: {spread_err}")
        timestamps["spread"] = spread_date
        sources["spread"] = spread_src
        st.session_state.bbb_spread = spread

        # 3. Bond yields
        us_slug = COUNTRY_TE_SLUGS.get("United States", "united-states")
        foreign_slug = COUNTRY_TE_SLUGS.get(selected_country, "united-states")
        (us_y, us_d, us_e, us_src,
         fy, fd, fe, f_src) = fetch_yields_for_countries(us_slug, foreign_slug, selected_country)
        if us_e:
            errors.append(f"US Yield: {us_e}")
        timestamps["us_yield"] = us_d
        sources["us_yield"] = us_src
        if fe:
            errors.append(f"Foreign Yield: {fe}")
        timestamps["foreign_yield"] = fd
        sources["foreign_yield"] = f_src
        st.session_state.us_yield = us_y
        st.session_state.foreign_yield = fy

        st.session_state.fetch_errors = errors
        st.session_state.fetch_timestamps = timestamps
        st.session_state.data_sources = sources
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

        # Show data source status
        sources = st.session_state.get("data_sources", {})
        any_fallback = any(v == "fallback" for v in sources.values())
        if any_fallback:
            fb_items = [k for k, v in sources.items() if v == "fallback"]
            st.info(
                f"Using fallback data for: {', '.join(fb_items)}. "
                "Live scraping is unavailable from this server. "
                "Values are from Damodaran/OECD (recent, but not real-time). "
                "Use manual overrides for exact current figures."
            )

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
            help="US market equity risk premium. The foreign ERP is adjusted automatically "
                 "by adding the country risk premium differential."
        )
        debt_share = st.slider(
            "Debt Financing Share (%)", 0.0, 100.0, DEFAULT_DEBT_SHARE, 1.0,
            help="Target debt / (debt + equity) for the project"
        )

        # Country Risk Premium display
        crp_foreign = COUNTRY_RISK_PREMIUMS.get(selected_country, 0.0)
        crp_us = COUNTRY_RISK_PREMIUMS.get("United States", 0.23)
        erp_foreign_calc = erp + (crp_foreign - crp_us)
        is_same_country = (selected_country == "United States")

        if not is_same_country:
            st.caption(
                f"**Country Risk Premium:** {selected_country} = {crp_foreign:.2f}% "
                f"(US = {crp_us:.2f}%)"
            )
            st.caption(
                f"**Foreign ERP:** {erp:.1f}% + ({crp_foreign:.2f}% - {crp_us:.2f}%) "
                f"= **{erp_foreign_calc:.2f}%**"
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
        st.caption("Toggle on to override fetched/fallback data with manual inputs.")

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

        # Country Risk Premium override
        override_crp = st.toggle("Override Country Risk Premium", value=False)
        if override_crp:
            manual_crp = st.number_input(
                f"{selected_country} CRP (%)",
                value=crp_foreign,
                min_value=0.0, max_value=30.0, step=0.01, format="%.2f"
            )
            crp_foreign = manual_crp

        st.divider()

        # Refresh button
        if st.button("Refresh Data", use_container_width=True, type="primary"):
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
        erp_us=erp,
        crp_foreign=crp_foreign,
        debt_share=debt_share,
        tax_rate=project_tax,
        bbb_spread_usd=manual_spread,
        bbb_spread_foreign=manual_foreign_spread,
    )

    # ----------------------------------------------------------
    # DATA SOURCES TABLE
    # ----------------------------------------------------------
    with st.expander("Data Sources & Fetched Values", expanded=False):
        source_labels = st.session_state.get("data_sources", {})

        def source_tag(key, default_source):
            src = source_labels.get(key, "unknown")
            if src == "fallback":
                return f"{default_source} (fallback)"
            elif src == "live":
                return f"{default_source} (live)"
            return default_source

        src_data = {
            "Parameter": [
                "Unlevered Beta",
                "USD BBB Spread",
                f"U.S. 10-Year Yield",
                f"{selected_country} 10-Year Yield",
                f"U.S. Tax Rate",
                f"{selected_country} Tax Rate",
                f"{selected_country} Country Risk Premium",
            ],
            "Fetched Value": [
                f"{fetched_beta:.4f}" if fetched_beta else "N/A",
                f"{fetched_spread:.2f}%" if fetched_spread else "N/A",
                f"{fetched_us_yield:.2f}%" if fetched_us_yield else "N/A",
                f"{fetched_foreign_yield:.2f}%" if fetched_foreign_yield else "N/A",
                f"{CORPORATE_TAX_RATES.get('United States', 'N/A')}%",
                f"{CORPORATE_TAX_RATES.get(selected_country, 'N/A')}%",
                f"{COUNTRY_RISK_PREMIUMS.get(selected_country, 0.0):.2f}%",
            ],
            "Used Value": [
                f"{manual_beta:.4f}",
                f"{manual_spread:.2f}%",
                f"{manual_us_yield:.2f}%",
                f"{manual_foreign_yield:.2f}%",
                f"{us_tax:.2f}%",
                f"{foreign_tax:.2f}%",
                f"{crp_foreign:.2f}%",
            ],
            "Source": [
                source_tag("betas", "Damodaran"),
                source_tag("spread", "Damodaran Ratings"),
                source_tag("us_yield", "Trading Economics / OECD"),
                source_tag("foreign_yield", "Trading Economics / OECD"),
                OECD_TAX_SOURCE,
                OECD_TAX_SOURCE,
                "Damodaran CRP",
            ],
            "Override": [
                "Yes" if override_beta else "No",
                "Yes" if override_spread else "No",
                "Yes" if override_yields else "No",
                "Yes" if override_yields else "No",
                "Yes" if override_tax else "No",
                "Yes" if override_tax else "No",
                "Yes" if override_crp else "No",
            ],
        }
        st.dataframe(
            pd.DataFrame(src_data),
            hide_index=True,
            use_container_width=True,
        )
        st.caption(
            "**Sources:** "
            "[Damodaran Betas](https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls) . "
            "[Damodaran Ratings/Spreads](https://pages.stern.nyu.edu/adamodar/New_Home_Page/datafile/ratings.html) . "
            "[Damodaran CRP](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/ctryprem.html) . "
            "[OECD Tax Rates](https://www.oecd.org/en/publications/corporate-tax-statistics-2024_9c27d6e8-en/full-report/statutory-corporate-income-tax-rates_440f9286.html) . "
            "[Trading Economics Bonds](https://tradingeconomics.com/bonds)"
        )
        if st.session_state.fetch_errors:
            st.warning("Some live fetches had errors (fallback data used where available):")
            for err in st.session_state.fetch_errors:
                st.caption(f"Warning: {err}")

    # ----------------------------------------------------------
    # RESULTS: SIDE-BY-SIDE
    # ----------------------------------------------------------
    st.subheader("Cost of Capital Comparison")

    is_same_country = (selected_country == "United States")
    foreign_label = f"{selected_country} ({currency})" if not is_same_country else "USD (same country)"

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### US (USD)")
        st.metric("Cost of Equity", f"{results['ke_usd']:.2f}%")
        st.caption(
            f"Rf {manual_us_yield:.2f}% + B({results['beta_l']:.4f}) x ERP({erp:.1f}%)"
        )
        st.metric("Cost of Debt (pre-tax)", f"{results['kd_usd']:.2f}%")
        st.caption(
            f"Rf {manual_us_yield:.2f}% + BBB spread {manual_spread:.2f}%"
        )
        st.metric("Cost of Debt (after-tax)", f"{results['kd_usd_aftertax']:.2f}%")
        st.caption(
            f"{results['kd_usd']:.2f}% x (1 - {project_tax:.2f}%)"
        )
        st.metric("**WACC**", f"{results['wacc_usd']:.2f}%")
        st.caption(
            f"Equity {results['we']:.0f}% x {results['ke_usd']:.2f}% + "
            f"Debt {results['wd']:.0f}% x {results['kd_usd']:.2f}% x (1 - {project_tax:.2f}%)"
        )

    with col2:
        st.markdown(f"### {foreign_label}")
        st.metric("Cost of Equity", f"{results['ke_foreign']:.2f}%")
        if not is_same_country:
            st.caption(
                f"Rf {manual_foreign_yield:.2f}% + B({results['beta_l']:.4f}) x "
                f"ERP({results['erp_foreign']:.2f}%)"
            )
            st.caption(
                f"Foreign ERP = {erp:.1f}% + ({crp_foreign:.2f}% - {crp_us:.2f}%) = "
                f"{results['erp_foreign']:.2f}%"
            )
        else:
            st.caption(
                f"Rf {manual_foreign_yield:.2f}% + B({results['beta_l']:.4f}) x ERP({erp:.1f}%)"
            )
        st.metric("Cost of Debt (pre-tax)", f"{results['kd_foreign']:.2f}%")
        spread_label = "override" if override_foreign_spread else "auto = USD spread"
        st.caption(
            f"Rf {manual_foreign_yield:.2f}% + BBB spread {manual_foreign_spread:.2f}% ({spread_label})"
        )
        st.metric("Cost of Debt (after-tax)", f"{results['kd_foreign_aftertax']:.2f}%")
        st.caption(
            f"{results['kd_foreign']:.2f}% x (1 - {project_tax:.2f}%)"
        )
        st.metric("**WACC**", f"{results['wacc_foreign']:.2f}%")
        st.caption(
            f"Equity {results['we']:.0f}% x {results['ke_foreign']:.2f}% + "
            f"Debt {results['wd']:.0f}% x {results['kd_foreign']:.2f}% x (1 - {project_tax:.2f}%)"
        )

    # Difference summary
    if not is_same_country:
        diff = results["wacc_foreign"] - results["wacc_usd"]
        direction = "higher" if diff > 0 else "lower"
        rf_diff = manual_foreign_yield - manual_us_yield
        erp_diff = results["erp_foreign"] - erp
        st.info(
            f"The {currency} WACC is **{abs(diff):.2f}pp** {direction} than the USD WACC. "
            f"Drivers: risk-free rate differential ({manual_foreign_yield:.2f}% vs. {manual_us_yield:.2f}% = "
            f"{'+' if rf_diff >= 0 else ''}{rf_diff:.2f}pp) and "
            f"country risk premium adjustment (CRP adds {'+' if erp_diff >= 0 else ''}{erp_diff:.2f}pp to ERP)."
        )

    # ----------------------------------------------------------
    # KEY ASSUMPTIONS
    # ----------------------------------------------------------
    with st.expander("Key Assumptions & Methodology", expanded=False):
        crp_note = ""
        if not is_same_country:
            crp_note = f"""
**Country risk premium adjustment:**
- U.S. CRP: {crp_us:.2f}%
- {selected_country} CRP: {crp_foreign:.2f}%
- Foreign ERP = US ERP + (Foreign CRP - US CRP) = {erp:.1f}% + ({crp_foreign:.2f}% - {crp_us:.2f}%) = {results['erp_foreign']:.2f}%
"""
        st.markdown(f"""
**Model:** Capital Asset Pricing Model (CAPM) with yield-differential currency conversion
and Damodaran country risk premium adjustment.

**Shared parameters across both currencies:**
- **Industry:** {selected_industry} (unlevered beta = {manual_beta:.4f})
- **Levered beta:** {results['beta_l']:.4f} = {manual_beta:.4f} x [1 + (1 - {project_tax:.2f}%) x {results['de_ratio']:.4f}]
- **US equity risk premium:** {erp:.1f}%
- **Debt share:** {debt_share:.0f}% debt / {100 - debt_share:.0f}% equity
- **Project tax rate:** {project_tax:.2f}% ({project_tax_label})
{crp_note}
**Currency conversion approach:**
The cost of capital in each currency uses that country's 10-year government bond yield as the
risk-free rate. The equity risk premium for the foreign country is adjusted by the country risk
premium differential (Foreign CRP - US CRP), reflecting the additional risk of investing in
that country's equity market.

- Cost of equity = Rf + Levered Beta x ERP (where ERP is adjusted for CRP in foreign currency)
- Cost of debt = Rf + BBB spread
- WACC = (E/V) x Ke + (D/V) x Kd x (1 - t)

When the foreign BBB spread override is off, the foreign spread equals the USD spread,
reflecting the assumption that credit quality is the same regardless of the currency of
borrowing.
""")

    # ----------------------------------------------------------
    # DOWNLOAD RESULTS
    # ----------------------------------------------------------
    st.subheader("Download Results")

    summary_data = {
        "Metric": [
            "Industry", "Country", "Currency",
            "Unlevered Beta", "Levered Beta", "US Equity Risk Premium (%)",
            f"Foreign ERP ({currency}) (%)", "Country Risk Premium (%)",
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
            f"{results['erp_foreign']:.2f}", f"{crp_foreign:.2f}",
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
            "Download Summary (CSV)",
            csv_summary,
            f"cost_of_capital_summary_{selected_country.replace(' ', '_')}.csv",
            "text/csv",
            use_container_width=True,
        )
    with col_d2:
        if st.session_state.betas_df is not None:
            all_df = compute_all_industry(
                st.session_state.betas_df,
                manual_us_yield, manual_foreign_yield, erp, crp_foreign,
                project_tax, manual_spread, manual_foreign_spread,
            )
            csv_all = all_df.to_csv(index=False)
            st.download_button(
                "Download All Industries (CSV)",
                csv_all,
                f"all_industry_wacc_{selected_country.replace(' ', '_')}.csv",
                "text/csv",
                use_container_width=True,
            )
        else:
            st.download_button(
                "All Industries (unavailable)",
                "Beta data not loaded", "unavailable.txt", "text/plain",
                use_container_width=True, disabled=True,
            )

    # ----------------------------------------------------------
    # ALL-INDUSTRY COMPARISON
    # ----------------------------------------------------------
    st.subheader("All-Industry Comparison")

    if st.session_state.betas_df is not None:
        if "all_df" not in dir():
            all_df = compute_all_industry(
                st.session_state.betas_df,
                manual_us_yield, manual_foreign_yield, erp, crp_foreign,
                project_tax, manual_spread, manual_foreign_spread,
            )

        # Chart
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
            for col in display_df.columns:
                if col != "Industry":
                    display_df[col] = display_df[col].apply(
                        lambda x: f"{x:.2f}" if isinstance(x, (int, float)) else x
                    )
            st.dataframe(display_df, hide_index=True, use_container_width=True)
    else:
        st.warning(
            "Industry beta data could not be loaded. "
            "Try clicking **Refresh Data** in the sidebar."
        )


if __name__ == "__main__":
    main()
