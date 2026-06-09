import pandas as pd

PORTFOLIO_COLUMNS = [
    "ticker",
    "shares",
    "average_cost",
    "notes",
]


def load_portfolio_positions(file_path: str = "data/portfolio.csv") -> pd.DataFrame:
    """
    Loads portfolio holdings from data/portfolio.csv.
    """

    try:
        df = pd.read_csv(file_path)
    except FileNotFoundError:
        return pd.DataFrame(columns=PORTFOLIO_COLUMNS)

    if df.empty:
        return pd.DataFrame(columns=PORTFOLIO_COLUMNS)

    for column in PORTFOLIO_COLUMNS:
        if column not in df.columns:
            df[column] = None

    df = df[PORTFOLIO_COLUMNS].copy()

    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
    df["shares"] = pd.to_numeric(df["shares"], errors="coerce").fillna(0)
    df["average_cost"] = pd.to_numeric(df["average_cost"], errors="coerce").fillna(0)
    df["notes"] = df["notes"].fillna("").astype(str)

    df = df[df["ticker"] != ""]
    df = df[df["shares"] > 0]

    return df


def build_portfolio_dashboard(
    positions_df: pd.DataFrame,
    evaluator_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Combines portfolio positions with full evaluator results.
    """

    if positions_df is None or positions_df.empty:
        return pd.DataFrame()

    if evaluator_df is None or evaluator_df.empty:
        return positions_df.copy()

    positions = positions_df.copy()
    evaluator = evaluator_df.copy()

    positions["ticker"] = positions["ticker"].astype(str).str.upper().str.strip()
    evaluator["ticker"] = evaluator["ticker"].astype(str).str.upper().str.strip()

    merged = positions.merge(
        evaluator,
        on="ticker",
        how="left",
    )

    merged["current_price"] = pd.to_numeric(
        merged.get("current_price"),
        errors="coerce",
    ).fillna(0)

    # If average_cost is 0 or blank, use current market price as a placeholder.
    # This keeps real cost basis fixed when provided, but makes paper/test portfolios dynamic.
    merged["effective_average_cost"] = merged["average_cost"]

    missing_cost_mask = merged["effective_average_cost"] <= 0

    merged.loc[missing_cost_mask, "effective_average_cost"] = merged.loc[
        missing_cost_mask,
        "current_price",
    ]

    merged["market_value"] = merged["shares"] * merged["current_price"]
    merged["cost_basis"] = merged["shares"] * merged["effective_average_cost"]
    merged["unrealized_gain_loss"] = merged["market_value"] - merged["cost_basis"]

    merged["unrealized_gain_loss_pct"] = 0.0

    positive_cost = merged["cost_basis"] > 0

    merged.loc[positive_cost, "unrealized_gain_loss_pct"] = (
        merged.loc[positive_cost, "unrealized_gain_loss"]
        / merged.loc[positive_cost, "cost_basis"]
    ) * 100

    total_market_value = merged["market_value"].sum()

    if total_market_value > 0:
        merged["portfolio_weight_pct"] = (
            merged["market_value"] / total_market_value
        ) * 100
    else:
        merged["portfolio_weight_pct"] = 0.0

    return merged


def build_portfolio_summary(portfolio_df: pd.DataFrame) -> dict:
    """
    Builds top-level portfolio summary metrics.
    """

    if portfolio_df is None or portfolio_df.empty:
        return {
            "holding_count": 0,
            "total_market_value": 0,
            "total_cost_basis": 0,
            "total_unrealized_gain_loss": 0,
            "total_unrealized_gain_loss_pct": 0,
            "weighted_final_score": 0,
            "profit_locker_count": 0,
        }

    total_market_value = portfolio_df["market_value"].sum()
    total_cost_basis = portfolio_df["cost_basis"].sum()
    total_gain_loss = portfolio_df["unrealized_gain_loss"].sum()

    if total_cost_basis > 0:
        total_gain_loss_pct = (total_gain_loss / total_cost_basis) * 100
    else:
        total_gain_loss_pct = 0

    if total_market_value > 0 and "final_score" in portfolio_df.columns:
        scores = pd.to_numeric(
            portfolio_df["final_score"],
            errors="coerce",
        ).fillna(0)

        weighted_final_score = (
            scores * portfolio_df["market_value"]
        ).sum() / total_market_value
    else:
        weighted_final_score = 0

    if "profit_locker_status" in portfolio_df.columns:
        profit_locker_count = (
            portfolio_df["profit_locker_status"]
            .astype(str)
            .str.lower()
            .str.contains(
                "locker|caution|warning|extended",
                na=False,
            )
            .sum()
        )
    else:
        profit_locker_count = 0

    return {
        "holding_count": len(portfolio_df),
        "total_market_value": total_market_value,
        "total_cost_basis": total_cost_basis,
        "total_unrealized_gain_loss": total_gain_loss,
        "total_unrealized_gain_loss_pct": total_gain_loss_pct,
        "weighted_final_score": weighted_final_score,
        "profit_locker_count": int(profit_locker_count),
    }


def get_portfolio_display_columns() -> list:
    return [
        "ticker",
        "shares",
        "average_cost",
        "effective_average_cost",
        "current_price",
        "market_value",
        "cost_basis",
        "unrealized_gain_loss",
        "unrealized_gain_loss_pct",
        "portfolio_weight_pct",
        "final_score",
        "final_label",
        "final_action",
        "distance_from_150dma",
        "profit_locker_status",
        "chart_score",
        "fundamental_score",
        "valuation_score",
        "final_smart_money_score",
        "institutional_smart_money_score",
        "notes",
    ]
