# International Cost of Capital Calculator

A Streamlit application that compares a project's cost of equity and WACC in USD and the currency of any selected country, using CAPM with sovereign yield differentials.

## Live App

[Open on Streamlit Community Cloud](https://share.streamlit.io/) *(update with your deployed URL)*

## Data Sources

| Data | Source | Method |
|------|--------|--------|
| Industry unlevered betas | [Damodaran (NYU Stern)](https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls) | XLS download, parsed with pandas |
| BBB/Baa2 borrowing spread | [Damodaran Ratings](https://pages.stern.nyu.edu/adamodar/New_Home_Page/datafile/ratings.html) | HTML table scrape (large non-financial service firms) |
| Corporate tax rates | [OECD Corporate Tax Statistics 2024](https://www.oecd.org/en/publications/corporate-tax-statistics-2024_9c27d6e8-en/full-report/statutory-corporate-income-tax-rates_440f9286.html) / [Tax Foundation](https://taxfoundation.org/data/all/global/corporate-tax-rates-by-country-2024/) | Combined statutory rates (central + sub-national) |
| 10-year government bond yields | [Trading Economics](https://tradingeconomics.com/bonds) | Individual country page scrape |

All fetched values can be overridden with manual inputs.

## Methodology

### Cost of Equity (CAPM)

```
Levered Beta = Unlevered Beta x [1 + (1 - Tax Rate) x (D/E)]
Cost of Equity = Risk-Free Rate + Levered Beta x Equity Risk Premium
```

### Cost of Debt

```
Cost of Debt (pre-tax) = Risk-Free Rate + BBB Spread
Cost of Debt (after-tax) = Cost of Debt (pre-tax) x (1 - Tax Rate)
```

### WACC

```
WACC = (E/V) x Cost of Equity + (D/V) x Cost of Debt x (1 - Tax Rate)
```

### Currency Conversion

The cost of capital in each currency uses that country's 10-year government bond yield as the risk-free rate. The equity risk premium and credit spread are held constant across currencies, so the difference is driven entirely by the risk-free rate gap.

When the foreign BBB spread override is off, the foreign spread equals the USD spread (same credit quality assumption).

## Verification Checks

1. **Equal yields produce equal results:** When the U.S. and foreign yields are set to the same value and the foreign BBB spread override is off, both currency columns show identical results.
2. **Zero debt equals equity cost:** Setting debt share to 0% makes WACC equal to the cost of equity.
3. **Foreign spread override is independent of USD:** Changing the foreign BBB spread override leaves all USD results unchanged.

## Default Settings

- Industry: Software (System & Application)
- Country: United States
- Tax rate: U.S. (25.77%)
- Equity risk premium: 6.5%
- Debt financing: 30%

## Deployment

1. Create a GitHub repository and upload `app.py`, `requirements.txt`, and this `README.md`.
2. Go to [share.streamlit.io](https://share.streamlit.io/).
3. Click "New app," select your repository, branch (`main`), and main file (`app.py`).
4. Click "Deploy."

## Built With

- [Streamlit](https://streamlit.io/) for the web interface
- [Plotly](https://plotly.com/) for interactive charts
- [pandas](https://pandas.pydata.org/) for data handling
- [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/) for web scraping
