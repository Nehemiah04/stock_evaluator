import pandas as pd
import yfinance as yf


def safe_float(value):
    """
    Converts a value to float safely.
    Returns None if the value is missing or invalid.
    """
    try:
        if pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


def get_statement_value(
    statement: pd.DataFrame, possible_row_names: list, column_position: int = 0
):
    """
    Searches a yfinance financial statement for a matching row name.
    Example rows: Total Revenue, Gross Profit, Operating Income, etc.
    """

    if statement is None or statement.empty:
        return None

    for target_name in possible_row_names:
        for row_name in statement.index:
            if target_name.lower() in str(row_name).lower():
                try:
                    return safe_float(statement.loc[row_name].iloc[column_position])
                except Exception:
                    return None

    return None


def percent_change(current, previous):
    """
    Calculates percentage change safely.
    """
    if current is None or previous is None:
        return None

    if previous == 0:
        return None

    return ((current - previous) / abs(previous)) * 100


def safe_ratio(numerator, denominator):
    """
    Calculates a ratio safely.
    """
    if numerator is None or denominator is None:
        return None

    if denominator == 0:
        return None

    return numerator / denominator


def normalize_growth_to_percent(value):
    """
    Converts growth values from estimate tables into percentage points.
    yfinance estimate growth fields are usually ratios, while statement growth
    calculations in this app are already percentage points.
    """

    numeric_value = safe_float(value)

    if numeric_value is None:
        return None

    if abs(numeric_value) <= 5:
        return numeric_value * 100

    return numeric_value


def calculate_fcf(operating_cash_flow, capital_expenditure):
    """
    Calculates free cash flow.

    In yfinance, capital expenditure is usually negative.
    So:
    FCF = Operating Cash Flow + Capital Expenditure

    If capex comes in as positive, we subtract it.
    """

    if operating_cash_flow is None or capital_expenditure is None:
        return None

    if capital_expenditure < 0:
        return operating_cash_flow + capital_expenditure

    return operating_cash_flow - capital_expenditure


def get_statement_row(statement: pd.DataFrame, possible_row_names: list):
    """
    Finds a row in a yfinance statement, preferring exact row-name matches.
    """

    if statement is None or statement.empty:
        return None

    statement_index = list(statement.index)

    for target_name in possible_row_names:
        target_name_normalized = str(target_name).strip().lower()

        for row_name in statement_index:
            if str(row_name).strip().lower() == target_name_normalized:
                row = statement.loc[row_name]
                return row.iloc[0] if isinstance(row, pd.DataFrame) else row

    for target_name in possible_row_names:
        target_name_normalized = str(target_name).strip().lower()

        for row_name in statement_index:
            row_name_normalized = str(row_name).strip().lower()

            if target_name_normalized == "ebit" and "ebitda" in row_name_normalized:
                continue

            if target_name_normalized in row_name_normalized:
                row = statement.loc[row_name]
                return row.iloc[0] if isinstance(row, pd.DataFrame) else row

    return None


def get_statement_values(
    statement: pd.DataFrame, possible_row_names: list, transform=None
) -> list:
    """
    Returns numeric statement row values in yfinance's newest-to-oldest order.
    """

    row = get_statement_row(statement, possible_row_names)

    if row is None:
        return []

    values = []

    for value in row.tolist():
        numeric_value = safe_float(value)

        if numeric_value is not None and transform is not None:
            numeric_value = transform(numeric_value)

        values.append(numeric_value)

    return values


def calculate_growth_from_values(
    values: list, current_position: int = 0, previous_position: int = 1
):
    """
    Calculates growth between two positions in a newest-to-oldest value list.
    """

    if len(values) <= max(current_position, previous_position):
        return None

    return percent_change(values[current_position], values[previous_position])


def calculate_average_growth(values: list, max_periods: int = 5):
    """
    Calculates the average growth rate across available historical periods.
    """

    growth_rates = []

    for position in range(min(len(values) - 1, max_periods)):
        growth_rate = calculate_growth_from_values(
            values,
            current_position=position,
            previous_position=position + 1,
        )

        if growth_rate is not None:
            growth_rates.append(growth_rate)

    if not growth_rates:
        return None

    return sum(growth_rates) / len(growth_rates)


def calculate_yoy_growth(statement: pd.DataFrame, row_names: list, transform=None):
    """
    Calculates latest quarter YoY growth using the same-quarter prior-year value.
    """

    values = get_statement_values(statement, row_names, transform=transform)

    return calculate_growth_from_values(
        values,
        current_position=0,
        previous_position=4,
    )


def calculate_historical_average_growth(
    statement: pd.DataFrame, row_names: list, transform=None
):
    """
    Calculates average annual growth from available annual statement periods.
    """

    values = get_statement_values(statement, row_names, transform=transform)

    return calculate_average_growth(values, max_periods=5)


def load_optional_table(stock, attribute_name: str) -> pd.DataFrame:
    """
    Loads optional yfinance tables without failing the rest of the dashboard.
    """

    try:
        table = getattr(stock, attribute_name)
    except Exception:
        return pd.DataFrame()

    if isinstance(table, pd.DataFrame):
        return table

    return pd.DataFrame()


def get_estimate_growth(
    estimate_table: pd.DataFrame, period: str = "+1y", column: str = "growth"
):
    """
    Reads a yfinance estimate growth value as percentage points.
    """

    if estimate_table is None or estimate_table.empty:
        return None

    if column not in estimate_table.columns or period not in estimate_table.index:
        return None

    value = estimate_table.loc[period, column]

    if isinstance(value, pd.Series):
        value = value.iloc[0]

    return normalize_growth_to_percent(value)


def get_trend_growth(
    growth_estimates: pd.DataFrame,
    period: str,
    columns: list,
):
    """
    Reads a stock/sector/industry trend value from yfinance growth estimates.
    """

    if growth_estimates is None or growth_estimates.empty:
        return None

    if period not in growth_estimates.index:
        return None

    for column in columns:
        if column not in growth_estimates.columns:
            continue

        value = growth_estimates.loc[period, column]

        if isinstance(value, pd.Series):
            value = value.iloc[0]

        trend_growth = normalize_growth_to_percent(value)

        if trend_growth is not None:
            return trend_growth

    return None


def calculate_fcf_values(cashflow_statement: pd.DataFrame) -> list:
    """
    Calculates free cash flow for every available cash-flow statement period.
    """

    operating_cash_flow_values = get_statement_values(
        cashflow_statement,
        ["Operating Cash Flow", "Total Cash From Operating Activities"],
    )
    capex_values = get_statement_values(
        cashflow_statement,
        ["Capital Expenditure", "Capital Expenditures"],
    )

    fcf_values = []

    for operating_cash_flow, capital_expenditure in zip(
        operating_cash_flow_values,
        capex_values,
    ):
        fcf_values.append(calculate_fcf(operating_cash_flow, capital_expenditure))

    return fcf_values


def calculate_fcf_per_share_values(
    income_statement: pd.DataFrame, cashflow_statement: pd.DataFrame
) -> list:
    """
    Calculates free cash flow per share for available statement periods.
    """

    fcf_values = calculate_fcf_values(cashflow_statement)
    diluted_share_values = get_statement_values(
        income_statement,
        [
            "Diluted Average Shares",
            "Diluted Shares",
            "Basic Average Shares",
            "Basic Shares",
        ],
    )

    fcf_per_share_values = []

    for free_cash_flow, diluted_shares in zip(fcf_values, diluted_share_values):
        fcf_per_share_values.append(safe_ratio(free_cash_flow, diluted_shares))

    return fcf_per_share_values


def calculate_roe_values(
    income_statement: pd.DataFrame, balance_sheet: pd.DataFrame
) -> list:
    """
    Calculates ROE for available statement periods.
    """

    net_income_values = get_statement_values(
        income_statement,
        [
            "Net Income Common Stockholders",
            "Net Income Applicable To Common Shares",
            "Net Income",
        ],
    )
    equity_values = get_statement_values(
        balance_sheet,
        ["Stockholders Equity", "Total Stockholder Equity"],
    )

    roe_values = []

    for net_income, equity in zip(net_income_values, equity_values):
        roe_values.append(safe_ratio(net_income, equity))

    return roe_values


def calculate_working_capital_values(balance_sheet: pd.DataFrame) -> list:
    """
    Calculates working capital for available balance-sheet periods.
    """

    current_asset_values = get_statement_values(
        balance_sheet,
        ["Current Assets", "Total Current Assets"],
    )
    current_liability_values = get_statement_values(
        balance_sheet,
        ["Current Liabilities", "Total Current Liabilities"],
    )

    working_capital_values = []

    for current_assets, current_liabilities in zip(
        current_asset_values,
        current_liability_values,
    ):
        if current_assets is None or current_liabilities is None:
            working_capital_values.append(None)
        else:
            working_capital_values.append(current_assets - current_liabilities)

    return working_capital_values


def calculate_dividend_ttm_growth(dividends: pd.Series):
    """
    Calculates current trailing-12-month dividend growth versus the prior year.
    """

    if dividends is None or dividends.empty:
        return None

    dividends = dividends.dropna().sort_index()

    if dividends.empty:
        return None

    latest_date = dividends.index.max()
    current_ttm_start = latest_date - pd.DateOffset(years=1)
    previous_ttm_start = latest_date - pd.DateOffset(years=2)

    current_ttm = dividends[dividends.index > current_ttm_start].sum()
    previous_ttm = dividends[
        (dividends.index > previous_ttm_start)
        & (dividends.index <= current_ttm_start)
    ].sum()

    return percent_change(safe_float(current_ttm), safe_float(previous_ttm))


def build_growth_metric(
    metric: str,
    value=None,
    five_year_average=None,
    sector_median=None,
    sector_relative_grade=None,
) -> dict:
    """
    Builds a normalized growth metric row for display.
    """

    return {
        "metric": metric,
        "sector_relative_grade": sector_relative_grade,
        "value": value,
        "sector_median": sector_median,
        "diff_to_sector": percent_change(value, sector_median),
        "five_year_average": five_year_average,
        "diff_to_five_year_average": percent_change(value, five_year_average),
    }


def build_growth_metrics(
    info: dict,
    quarterly_income: pd.DataFrame,
    annual_income: pd.DataFrame,
    quarterly_cashflow: pd.DataFrame,
    annual_cashflow: pd.DataFrame,
    quarterly_balance: pd.DataFrame,
    annual_balance: pd.DataFrame,
    revenue_estimate: pd.DataFrame,
    earnings_estimate: pd.DataFrame,
    growth_estimates: pd.DataFrame,
    dividends: pd.Series,
    revenue_yoy_growth,
) -> list:
    """
    Builds the growth metric set shown in the single-ticker dashboard.
    """

    revenue_rows = ["Total Revenue", "Operating Revenue", "Revenue"]
    ebitda_rows = ["EBITDA", "Normalized EBITDA"]
    ebit_rows = [
        "EBIT",
        "Normalized EBIT",
        "Operating Income",
        "Operating Income or Loss",
    ]
    diluted_eps_rows = ["Diluted EPS"]
    gaap_eps_rows = ["Basic EPS", "Diluted EPS"]
    operating_cash_flow_rows = [
        "Operating Cash Flow",
        "Total Cash From Operating Activities",
    ]
    capex_rows = ["Capital Expenditure", "Capital Expenditures"]

    fcf_yoy_growth = calculate_growth_from_values(
        calculate_fcf_values(quarterly_cashflow),
        current_position=0,
        previous_position=4,
    )
    fcf_average_growth = calculate_average_growth(
        calculate_fcf_values(annual_cashflow),
        max_periods=5,
    )
    fcf_per_share_average_growth = calculate_average_growth(
        calculate_fcf_per_share_values(annual_income, annual_cashflow),
        max_periods=5,
    )
    roe_yoy_growth = calculate_growth_from_values(
        calculate_roe_values(quarterly_income, quarterly_balance),
        current_position=0,
        previous_position=4,
    )
    roe_average_growth = calculate_average_growth(
        calculate_roe_values(annual_income, annual_balance),
        max_periods=5,
    )
    working_capital_yoy_growth = calculate_growth_from_values(
        calculate_working_capital_values(quarterly_balance),
        current_position=0,
        previous_position=4,
    )
    working_capital_average_growth = calculate_average_growth(
        calculate_working_capital_values(annual_balance),
        max_periods=5,
    )

    revenue_fwd_growth = get_estimate_growth(revenue_estimate, period="+1y")
    eps_fwd_growth = get_estimate_growth(earnings_estimate, period="+1y")
    eps_long_term_growth = get_trend_growth(
        growth_estimates,
        period="+5y",
        columns=["stockTrend", "stock", "stock_trend"],
    )
    sector_one_year_growth = get_trend_growth(
        growth_estimates,
        period="+1y",
        columns=["sectorTrend", "sector", "sector_trend"],
    )
    sector_long_term_growth = get_trend_growth(
        growth_estimates,
        period="+5y",
        columns=["sectorTrend", "sector", "sector_trend"],
    )

    dividend_forward_growth = percent_change(
        safe_float(info.get("dividendRate")),
        safe_float(info.get("trailingAnnualDividendRate")),
    )
    dividend_ttm_growth = calculate_dividend_ttm_growth(dividends)

    return [
        build_growth_metric(
            "Revenue Growth (YoY)",
            revenue_yoy_growth,
            calculate_historical_average_growth(annual_income, revenue_rows),
        ),
        build_growth_metric(
            "Revenue Growth (FWD)",
            revenue_fwd_growth,
            calculate_historical_average_growth(annual_income, revenue_rows),
        ),
        build_growth_metric(
            "EBITDA Growth (YoY)",
            calculate_yoy_growth(quarterly_income, ebitda_rows),
            calculate_historical_average_growth(annual_income, ebitda_rows),
        ),
        build_growth_metric(
            "EBITDA Growth (FWD)",
            None,
            calculate_historical_average_growth(annual_income, ebitda_rows),
        ),
        build_growth_metric(
            "EBIT Growth (YoY)",
            calculate_yoy_growth(quarterly_income, ebit_rows),
            calculate_historical_average_growth(annual_income, ebit_rows),
        ),
        build_growth_metric(
            "EBIT Growth (FWD)",
            None,
            calculate_historical_average_growth(annual_income, ebit_rows),
        ),
        build_growth_metric(
            "EPS Diluted Growth (YoY)",
            calculate_yoy_growth(quarterly_income, diluted_eps_rows),
            calculate_historical_average_growth(annual_income, diluted_eps_rows),
        ),
        build_growth_metric(
            "EPS Diluted Growth (FWD)",
            eps_fwd_growth,
            calculate_historical_average_growth(annual_income, diluted_eps_rows),
            sector_median=sector_one_year_growth,
        ),
        build_growth_metric(
            "EPS GAAP Growth (YoY)",
            calculate_yoy_growth(quarterly_income, gaap_eps_rows),
            calculate_historical_average_growth(annual_income, gaap_eps_rows),
        ),
        build_growth_metric(
            "EPS GAAP Growth (FWD)",
            eps_fwd_growth,
            calculate_historical_average_growth(annual_income, gaap_eps_rows),
            sector_median=sector_one_year_growth,
        ),
        build_growth_metric(
            "EPS FWD Long Term Growth (3-5Y CAGR)",
            eps_long_term_growth,
            get_trend_growth(
                growth_estimates,
                period="-5y",
                columns=["stockTrend", "stock", "stock_trend"],
            ),
            sector_median=sector_long_term_growth,
        ),
        build_growth_metric(
            "Levered FCF Growth (YoY)",
            fcf_yoy_growth,
            fcf_average_growth,
        ),
        build_growth_metric(
            "Free Cash Flow Per Share Growth Rate (FWD)",
            None,
            fcf_per_share_average_growth,
        ),
        build_growth_metric(
            "Operating Cash Flow Growth (YoY)",
            calculate_yoy_growth(quarterly_cashflow, operating_cash_flow_rows),
            calculate_historical_average_growth(
                annual_cashflow,
                operating_cash_flow_rows,
            ),
        ),
        build_growth_metric(
            "Operating Cash Flow Growth (FWD)",
            None,
            calculate_historical_average_growth(
                annual_cashflow,
                operating_cash_flow_rows,
            ),
        ),
        build_growth_metric(
            "ROE Growth (YoY)",
            roe_yoy_growth,
            roe_average_growth,
        ),
        build_growth_metric(
            "ROE Growth (FWD)",
            None,
            roe_average_growth,
        ),
        build_growth_metric(
            "Working Capital Growth (YoY)",
            working_capital_yoy_growth,
            working_capital_average_growth,
        ),
        build_growth_metric(
            "CAPEX Growth (YoY)",
            calculate_yoy_growth(quarterly_cashflow, capex_rows, transform=abs),
            calculate_historical_average_growth(
                annual_cashflow,
                capex_rows,
                transform=abs,
            ),
        ),
        build_growth_metric(
            "Dividend Per Share Growth (FWD)",
            dividend_forward_growth,
            dividend_ttm_growth,
        ),
        build_growth_metric(
            "1 Year Dividend Growth Rate (TTM)",
            dividend_ttm_growth,
            dividend_ttm_growth,
        ),
    ]


def load_fundamentals(ticker: str) -> dict:
    """
    Loads core fundamentals using yfinance.
    This is the prototype version before connecting a stronger API like FMP.
    """

    stock = yf.Ticker(ticker)
    try:
        info = stock.info
    except Exception:
        info = {}

    shares_outstanding = safe_float(info.get("sharesOutstanding"))
    trailing_eps = safe_float(info.get("trailingEps"))
    forward_eps = safe_float(info.get("forwardEps"))
    market_cap = safe_float(info.get("marketCap"))

    try:
        quarterly_income = stock.quarterly_financials
    except Exception:
        quarterly_income = pd.DataFrame()

    try:
        quarterly_cashflow = stock.quarterly_cashflow
    except Exception:
        quarterly_cashflow = pd.DataFrame()

    try:
        quarterly_balance = stock.quarterly_balance_sheet
    except Exception:
        quarterly_balance = pd.DataFrame()

    annual_income = load_optional_table(stock, "financials")
    annual_cashflow = load_optional_table(stock, "cashflow")
    annual_balance = load_optional_table(stock, "balance_sheet")
    revenue_estimate = load_optional_table(stock, "revenue_estimate")
    earnings_estimate = load_optional_table(stock, "earnings_estimate")
    growth_estimates = load_optional_table(stock, "growth_estimates")

    try:
        dividends = stock.dividends
    except Exception:
        dividends = pd.Series(dtype=float)

    # -----------------------------
    # Income statement
    # -----------------------------
    revenue = get_statement_value(quarterly_income, ["Total Revenue", "Revenue"])

    revenue_year_ago = None
    if (
        quarterly_income is not None
        and not quarterly_income.empty
        and quarterly_income.shape[1] >= 5
    ):
        revenue_year_ago = get_statement_value(
            quarterly_income, ["Total Revenue", "Revenue"], column_position=4
        )

    revenue_yoy_growth = percent_change(revenue, revenue_year_ago)

    gross_profit = get_statement_value(quarterly_income, ["Gross Profit"])

    operating_income = get_statement_value(
        quarterly_income, ["Operating Income", "Operating Income or Loss"]
    )

    gross_margin = safe_ratio(gross_profit, revenue)
    operating_margin = safe_ratio(operating_income, revenue)

    # -----------------------------
    # Cash flow statement
    # -----------------------------
    operating_cash_flow = get_statement_value(
        quarterly_cashflow,
        ["Operating Cash Flow", "Total Cash From Operating Activities"],
    )

    capital_expenditure = get_statement_value(
        quarterly_cashflow, ["Capital Expenditure", "Capital Expenditures"]
    )

    free_cash_flow = calculate_fcf(operating_cash_flow, capital_expenditure)
    fcf_margin = safe_ratio(free_cash_flow, revenue)

    # -----------------------------
    # Balance sheet
    # -----------------------------
    cash = get_statement_value(
        quarterly_balance,
        [
            "Cash And Cash Equivalents",
            "Cash Cash Equivalents And Short Term Investments",
            "Cash And Short Term Investments",
        ],
    )

    total_debt = get_statement_value(quarterly_balance, ["Total Debt"])

    stockholders_equity = get_statement_value(
        quarterly_balance, ["Stockholders Equity", "Total Stockholder Equity"]
    )

    current_assets = get_statement_value(
        quarterly_balance, ["Current Assets", "Total Current Assets"]
    )

    current_liabilities = get_statement_value(
        quarterly_balance, ["Current Liabilities", "Total Current Liabilities"]
    )

    debt_to_equity = safe_ratio(total_debt, stockholders_equity)
    current_ratio = safe_ratio(current_assets, current_liabilities)

    # -----------------------------
    # Cash runway
    # -----------------------------
    annualized_fcf = None
    cash_runway_years = None
    cash_runway_label = "N/A"

    if free_cash_flow is not None:
        annualized_fcf = free_cash_flow * 4

        if annualized_fcf >= 0:
            cash_runway_label = "FCF positive"
        elif cash is not None:
            annual_cash_burn = abs(annualized_fcf)
            cash_runway_years = safe_ratio(cash, annual_cash_burn)

            if cash_runway_years is not None:
                cash_runway_label = f"{cash_runway_years:.2f} years"

    growth_metrics = build_growth_metrics(
        info=info,
        quarterly_income=quarterly_income,
        annual_income=annual_income,
        quarterly_cashflow=quarterly_cashflow,
        annual_cashflow=annual_cashflow,
        quarterly_balance=quarterly_balance,
        annual_balance=annual_balance,
        revenue_estimate=revenue_estimate,
        earnings_estimate=earnings_estimate,
        growth_estimates=growth_estimates,
        dividends=dividends,
        revenue_yoy_growth=revenue_yoy_growth,
    )

    return {
        "ticker": ticker.upper(),
        "revenue": revenue,
        "revenue_yoy_growth": revenue_yoy_growth,
        "gross_profit": gross_profit,
        "gross_margin": gross_margin,
        "operating_income": operating_income,
        "operating_margin": operating_margin,
        "operating_cash_flow": operating_cash_flow,
        "capital_expenditure": capital_expenditure,
        "free_cash_flow": free_cash_flow,
        "fcf_margin": fcf_margin,
        "cash": cash,
        "total_debt": total_debt,
        "stockholders_equity": stockholders_equity,
        "debt_to_equity": debt_to_equity,
        "current_assets": current_assets,
        "current_liabilities": current_liabilities,
        "current_ratio": current_ratio,
        "annualized_fcf": annualized_fcf,
        "cash_runway_years": cash_runway_years,
        "cash_runway_label": cash_runway_label,
        "shares_outstanding": shares_outstanding,
        "trailing_eps": trailing_eps,
        "forward_eps": forward_eps,
        "market_cap": market_cap,
        "growth_metrics": growth_metrics,
    }


def calculate_fundamental_score(fundamentals: dict) -> int:
    """
    Scores the company's fundamentals from 0 to 100.
    """

    score = 0

    revenue_growth = fundamentals.get("revenue_yoy_growth")
    gross_margin = fundamentals.get("gross_margin")
    operating_margin = fundamentals.get("operating_margin")
    fcf_margin = fundamentals.get("fcf_margin")
    current_ratio = fundamentals.get("current_ratio")
    debt_to_equity = fundamentals.get("debt_to_equity")
    cash_runway_years = fundamentals.get("cash_runway_years")
    cash_runway_label = fundamentals.get("cash_runway_label")

    # Revenue growth score: 20 points
    if revenue_growth is not None:
        if revenue_growth >= 30:
            score += 20
        elif revenue_growth >= 15:
            score += 15
        elif revenue_growth >= 5:
            score += 10
        elif revenue_growth >= 0:
            score += 5

    # Gross margin score: 15 points
    if gross_margin is not None:
        if gross_margin >= 0.70:
            score += 15
        elif gross_margin >= 0.50:
            score += 12
        elif gross_margin >= 0.35:
            score += 8
        elif gross_margin >= 0.20:
            score += 4

    # Operating margin score: 15 points
    if operating_margin is not None:
        if operating_margin >= 0.30:
            score += 15
        elif operating_margin >= 0.15:
            score += 12
        elif operating_margin >= 0.05:
            score += 8
        elif operating_margin >= 0:
            score += 4

    # FCF margin score: 20 points
    if fcf_margin is not None:
        if fcf_margin >= 0.25:
            score += 20
        elif fcf_margin >= 0.15:
            score += 15
        elif fcf_margin >= 0.05:
            score += 10
        elif fcf_margin >= 0:
            score += 5

    # Current ratio score: 10 points
    if current_ratio is not None:
        if current_ratio >= 2:
            score += 10
        elif current_ratio >= 1.2:
            score += 7
        elif current_ratio >= 1:
            score += 4

    # Debt-to-equity score: 10 points
    if debt_to_equity is not None:
        if debt_to_equity <= 0.5:
            score += 10
        elif debt_to_equity <= 1:
            score += 7
        elif debt_to_equity <= 2:
            score += 4

    # Cash runway / FCF positive score: 10 points
    if cash_runway_label == "FCF positive":
        score += 10
    elif cash_runway_years is not None:
        if cash_runway_years >= 3:
            score += 10
        elif cash_runway_years >= 2:
            score += 7
        elif cash_runway_years >= 1:
            score += 4

    return max(0, min(score, 100))
