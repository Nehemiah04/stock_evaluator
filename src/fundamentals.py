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
