import pandas as pd

from src.price_data import load_price_data
from src.scoring import calculate_heartbeat, calculate_chart_score, get_action_label
from src.fundamentals import load_fundamentals, calculate_fundamental_score
from src.valuation import build_valuation_summary
from src.final_score import calculate_final_score, get_final_label, get_final_action
from src.institutional_scoring import build_institutional_smart_money_summary

DEFAULT_VALUATION_ASSUMPTIONS = {
    "dcf_growth_rate": 0.10,
    "discount_rate": 0.10,
    "terminal_growth_rate": 0.03,
    "dcf_years": 5,
    "eps_growth_rate": 0.10,
    "future_pe": 25.0,
    "eps_years": 5,
}


def safe_get(dictionary: dict, key: str, default=None):
    """
    Safe dictionary getter.
    """

    if dictionary is None:
        return default

    return dictionary.get(key, default)


def get_ticker_institutional_holdings(
    holdings_df: pd.DataFrame, ticker: str
) -> pd.DataFrame:
    """
    Filters institutional holdings data for one ticker.
    """

    if holdings_df is None or holdings_df.empty:
        return pd.DataFrame()

    if "ticker" not in holdings_df.columns:
        return pd.DataFrame()

    filtered_df = holdings_df[
        holdings_df["ticker"].astype(str).str.upper().str.strip() == ticker.upper()
    ]

    return filtered_df


def combine_manual_and_institutional_smart_money(
    manual_smart_money_score: float,
    institutional_smart_money_score: float,
    institutional_holding_count: int,
) -> float:
    """
    Combines manual smart money score and institutional smart money score.

    If institutional data exists:
    - Manual Smart Money: 35%
    - Institutional Smart Money: 65%

    If no institutional data exists:
    - Manual Smart Money: 100%
    """

    if institutional_holding_count > 0:
        return round(
            (manual_smart_money_score * 0.35)
            + (institutional_smart_money_score * 0.65),
            2,
        )

    return round(manual_smart_money_score, 2)


def evaluate_full_stock(
    ticker: str,
    institutional_holdings_df: pd.DataFrame | None = None,
    manual_smart_money_score: float = 0,
    valuation_assumptions: dict | None = None,
) -> dict:
    """
    Full stock evaluator engine.

    Combines:
    - Price data
    - 150DMA heartbeat
    - Chart score
    - Fundamentals
    - Valuation
    - Institutional smart money
    - Final score
    """

    ticker = str(ticker).upper().strip()

    if not ticker:
        return {"ticker": ticker, "status": "Error", "error": "Ticker is blank"}

    if valuation_assumptions is None:
        valuation_assumptions = DEFAULT_VALUATION_ASSUMPTIONS.copy()

    try:
        data = load_price_data(ticker)

        if data.empty or len(data) < 160:
            return {
                "ticker": ticker,
                "status": "Error",
                "error": "Not enough price data",
            }

        metrics = calculate_heartbeat(data)
        chart_score = calculate_chart_score(metrics)
        action_label = get_action_label(metrics, chart_score)

        fundamentals = load_fundamentals(ticker)
        fundamental_score = calculate_fundamental_score(fundamentals)

        valuation = build_valuation_summary(
            fundamentals=fundamentals,
            current_price=metrics["current_price"],
            dcf_growth_rate=valuation_assumptions.get("dcf_growth_rate", 0.10),
            discount_rate=valuation_assumptions.get("discount_rate", 0.10),
            terminal_growth_rate=valuation_assumptions.get(
                "terminal_growth_rate", 0.03
            ),
            dcf_years=int(valuation_assumptions.get("dcf_years", 5)),
            eps_growth_rate=valuation_assumptions.get("eps_growth_rate", 0.10),
            future_pe=valuation_assumptions.get("future_pe", 25.0),
            eps_years=int(valuation_assumptions.get("eps_years", 5)),
        )

        ticker_institutional_holdings = get_ticker_institutional_holdings(
            holdings_df=institutional_holdings_df, ticker=ticker
        )

        institutional_smart_money = build_institutional_smart_money_summary(
            ticker_institutional_holdings, ticker=ticker
        )

        institutional_smart_money_score = institutional_smart_money.get(
            "institutional_smart_money_score", 0
        )

        institutional_holding_count = institutional_smart_money.get("holding_count", 0)

        final_smart_money_score = combine_manual_and_institutional_smart_money(
            manual_smart_money_score=manual_smart_money_score,
            institutional_smart_money_score=institutional_smart_money_score,
            institutional_holding_count=institutional_holding_count,
        )

        final_score_data = calculate_final_score(
            chart_score=chart_score,
            fundamental_score=fundamental_score,
            valuation_score=valuation.get("valuation_score", 0),
            smart_money_score=final_smart_money_score,
        )

        final_score = final_score_data["final_score"]
        final_label = get_final_label(final_score)

        final_action = get_final_action(
            final_score=final_score,
            chart_action_label=action_label,
            valuation_label=valuation.get("valuation_label", "N/A"),
            profit_locker_status=metrics["profit_locker_status"],
        )

        return {
            "ticker": ticker,
            "status": "OK",
            "error": "",
            "current_price": metrics.get("current_price"),
            "dma_50": metrics.get("dma_50"),
            "dma_150": metrics.get("dma_150"),
            "distance_from_150dma": metrics.get("distance_from_150dma"),
            "heartbeat_status": metrics.get("heartbeat_status"),
            "profit_locker_status": metrics.get("profit_locker_status"),
            "chart_score": chart_score,
            "chart_action_label": action_label,
            "fundamental_score": fundamental_score,
            "sector": fundamentals.get("sector"),
            "industry": fundamentals.get("industry"),
            "quote_type": fundamentals.get("quote_type"),
            "fundamental_profile": fundamentals.get("fundamental_profile"),
            "fundamental_data_quality": fundamentals.get("fundamental_data_quality"),
            "missing_fundamental_fields": fundamentals.get(
                "missing_fundamental_fields"
            ),
            "revenue": fundamentals.get("revenue"),
            "revenue_yoy_growth": fundamentals.get("revenue_yoy_growth"),
            "gross_margin": fundamentals.get("gross_margin"),
            "operating_margin": fundamentals.get("operating_margin"),
            "net_income": fundamentals.get("net_income"),
            "net_income_yoy_growth": fundamentals.get("net_income_yoy_growth"),
            "return_on_equity": fundamentals.get("return_on_equity"),
            "equity_to_assets": fundamentals.get("equity_to_assets"),
            "cash_to_debt": fundamentals.get("cash_to_debt"),
            "fcf_margin": fundamentals.get("fcf_margin"),
            "cash": fundamentals.get("cash"),
            "total_debt": fundamentals.get("total_debt"),
            "debt_to_equity": fundamentals.get("debt_to_equity"),
            "current_ratio": fundamentals.get("current_ratio"),
            "growth_metrics": fundamentals.get("growth_metrics", []),
            "valuation_score": valuation.get("valuation_score"),
            "valuation_label": valuation.get("valuation_label"),
            "valuation_method": valuation.get("valuation_method"),
            "primary_intrinsic_value": valuation.get("primary_intrinsic_value"),
            "margin_of_safety": valuation.get("margin_of_safety"),
            "dcf_value": valuation.get("dcf_value"),
            "eps_pe_value": valuation.get("eps_pe_value"),
            "manual_smart_money_score": manual_smart_money_score,
            "institutional_smart_money_score": institutional_smart_money_score,
            "institutional_smart_money_label": institutional_smart_money.get(
                "institutional_smart_money_label", "N/A"
            ),
            "institutional_holding_count": institutional_holding_count,
            "institutional_net_qoq_flow_pct": institutional_smart_money.get(
                "net_qoq_flow_pct", 0
            ),
            "final_smart_money_score": final_smart_money_score,
            "final_score": final_score,
            "final_label": final_label,
            "final_action": final_action,
        }

    except Exception as error:
        return {"ticker": ticker, "status": "Error", "error": str(error)}


def evaluate_full_watchlist(
    tickers: list,
    institutional_holdings_df: pd.DataFrame | None = None,
    manual_smart_money_score: float = 0,
    valuation_assumptions: dict | None = None,
) -> pd.DataFrame:
    """
    Evaluates multiple tickers and returns a ranked DataFrame.
    """

    results = []

    for ticker in tickers:
        result = evaluate_full_stock(
            ticker=ticker,
            institutional_holdings_df=institutional_holdings_df,
            manual_smart_money_score=manual_smart_money_score,
            valuation_assumptions=valuation_assumptions,
        )

        results.append(result)

    results_df = pd.DataFrame(results)

    if results_df.empty:
        return results_df

    if "final_score" in results_df.columns:
        results_df["final_score_sort"] = pd.to_numeric(
            results_df["final_score"], errors="coerce"
        ).fillna(-1)

        results_df = results_df.sort_values(
            by="final_score_sort", ascending=False
        ).drop(columns=["final_score_sort"])

    return results_df
