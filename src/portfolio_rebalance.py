import pandas as pd

TARGET_COLUMNS = [
    "ticker",
    "target_weight_pct",
    "max_weight_pct",
    "min_score_required",
    "notes",
]


def load_portfolio_targets(
    file_path: str = "data/portfolio_targets.csv",
) -> pd.DataFrame:
    try:
        df = pd.read_csv(file_path)
    except FileNotFoundError:
        return pd.DataFrame(columns=TARGET_COLUMNS)

    for column in TARGET_COLUMNS:
        if column not in df.columns:
            df[column] = None

    df = df[TARGET_COLUMNS].copy()

    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
    df["target_weight_pct"] = pd.to_numeric(
        df["target_weight_pct"], errors="coerce"
    ).fillna(0)
    df["max_weight_pct"] = pd.to_numeric(df["max_weight_pct"], errors="coerce").fillna(
        100
    )
    df["min_score_required"] = pd.to_numeric(
        df["min_score_required"], errors="coerce"
    ).fillna(0)
    df["notes"] = df["notes"].fillna("").astype(str)

    return df


def get_rebalance_action(row) -> str:
    current_weight = row.get("portfolio_weight_pct", 0)
    target_weight = row.get("target_weight_pct", 0)
    max_weight = row.get("max_weight_pct", 100)
    final_score = row.get("final_score", 0)
    min_score_required = row.get("min_score_required", 0)
    distance_from_150dma = row.get("distance_from_150dma", 0)

    if current_weight > max_weight:
        return "Trim: above max weight"

    if distance_from_150dma >= 35:
        return "Profit Locker: consider trimming"

    if final_score < min_score_required:
        return "Hold/Review: score below requirement"

    if current_weight < target_weight:
        return "Add candidate"

    if current_weight > target_weight:
        return "Slight trim candidate"

    return "On target"


def build_rebalance_plan(
    portfolio_df: pd.DataFrame,
    targets_df: pd.DataFrame,
) -> pd.DataFrame:
    if portfolio_df is None or portfolio_df.empty:
        return pd.DataFrame()

    if targets_df is None or targets_df.empty:
        return portfolio_df.copy()

    portfolio = portfolio_df.copy()
    targets = targets_df.copy()

    portfolio["ticker"] = portfolio["ticker"].astype(str).str.upper().str.strip()
    targets["ticker"] = targets["ticker"].astype(str).str.upper().str.strip()

    merged = portfolio.merge(
        targets,
        on="ticker",
        how="left",
        suffixes=("", "_target"),
    )

    merged["target_weight_pct"] = pd.to_numeric(
        merged["target_weight_pct"],
        errors="coerce",
    ).fillna(0)

    merged["max_weight_pct"] = pd.to_numeric(
        merged["max_weight_pct"],
        errors="coerce",
    ).fillna(100)

    merged["min_score_required"] = pd.to_numeric(
        merged["min_score_required"],
        errors="coerce",
    ).fillna(0)

    numeric_columns = [
        "portfolio_weight_pct",
        "market_value",
        "final_score",
        "distance_from_150dma",
    ]

    for column in numeric_columns:
        if column not in merged.columns:
            merged[column] = 0

        merged[column] = pd.to_numeric(
            merged[column],
            errors="coerce",
        ).fillna(0)

    total_market_value = merged["market_value"].sum()

    merged["weight_gap_pct"] = (
        merged["target_weight_pct"] - merged["portfolio_weight_pct"]
    )

    merged["rebalance_dollar_gap"] = (
        merged["weight_gap_pct"] / 100
    ) * total_market_value

    merged["rebalance_action"] = merged.apply(
        get_rebalance_action,
        axis=1,
    )

    merged["priority_score"] = (
        merged["final_score"]
        - merged["distance_from_150dma"].clip(lower=0) * 0.5
        - merged["portfolio_weight_pct"].clip(lower=0) * 0.25
    )

    merged = merged.sort_values(
        by="priority_score",
        ascending=False,
    )

    return merged


def build_rebalance_summary(rebalance_df: pd.DataFrame) -> dict:
    if rebalance_df is None or rebalance_df.empty:
        return {
            "add_candidates": 0,
            "trim_candidates": 0,
            "profit_locker_candidates": 0,
            "review_candidates": 0,
        }

    action_series = rebalance_df["rebalance_action"].astype(str)

    return {
        "add_candidates": action_series.str.contains("Add", case=False, na=False).sum(),
        "trim_candidates": action_series.str.contains(
            "Trim", case=False, na=False
        ).sum(),
        "profit_locker_candidates": action_series.str.contains(
            "Profit Locker", case=False, na=False
        ).sum(),
        "review_candidates": action_series.str.contains(
            "Review", case=False, na=False
        ).sum(),
    }


def get_rebalance_display_columns() -> list:
    return [
        "ticker",
        "portfolio_weight_pct",
        "target_weight_pct",
        "max_weight_pct",
        "weight_gap_pct",
        "rebalance_dollar_gap",
        "market_value",
        "final_score",
        "min_score_required",
        "distance_from_150dma",
        "profit_locker_status",
        "rebalance_action",
        "priority_score",
        "notes",
    ]
