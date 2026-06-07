import pandas as pd

NUMERIC_COLUMNS = [
    "final_score",
    "current_price",
    "dma_150",
    "distance_from_150dma",
    "chart_score",
    "fundamental_score",
    "valuation_score",
    "final_smart_money_score",
    "institutional_smart_money_score",
    "institutional_holding_count",
    "institutional_net_qoq_flow_pct",
    "margin_of_safety",
]


def prepare_watchlist_filter_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepares watchlist scan results for filtering and sorting.
    """

    if df is None or df.empty:
        return pd.DataFrame()

    prepared_df = df.copy()

    for column in NUMERIC_COLUMNS:
        if column in prepared_df.columns:
            prepared_df[column] = pd.to_numeric(
                prepared_df[column],
                errors="coerce",
            )

    if "ticker" in prepared_df.columns:
        prepared_df["ticker"] = (
            prepared_df["ticker"].astype(str).str.upper().str.strip()
        )

    if "status" in prepared_df.columns:
        prepared_df["status"] = prepared_df["status"].astype(str)

    if "profit_locker_status" in prepared_df.columns:
        prepared_df["profit_locker_status"] = prepared_df[
            "profit_locker_status"
        ].astype(str)

    if "valuation_label" in prepared_df.columns:
        prepared_df["valuation_label"] = prepared_df["valuation_label"].astype(str)

    if "heartbeat_status" in prepared_df.columns:
        prepared_df["heartbeat_status"] = prepared_df["heartbeat_status"].astype(str)

    return prepared_df


def apply_watchlist_filters(
    df: pd.DataFrame,
    min_final_score: float = 0,
    min_chart_score: float = 0,
    min_fundamental_score: float = 0,
    min_valuation_score: float = 0,
    min_institutional_score: float = -5,
    require_ok_status: bool = True,
    require_above_150dma: bool = False,
    hide_profit_locker_warning: bool = False,
    require_positive_margin_of_safety: bool = False,
    require_institutional_accumulation: bool = False,
) -> pd.DataFrame:
    """
    Applies Watchlist Scanner 2.0 filters.
    """

    filtered_df = prepare_watchlist_filter_df(df)

    if filtered_df.empty:
        return filtered_df

    if require_ok_status and "status" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["status"].str.upper() == "OK"]

    if "final_score" in filtered_df.columns:
        filtered_df = filtered_df[
            filtered_df["final_score"].fillna(-999) >= min_final_score
        ]

    if "chart_score" in filtered_df.columns:
        filtered_df = filtered_df[
            filtered_df["chart_score"].fillna(-999) >= min_chart_score
        ]

    if "fundamental_score" in filtered_df.columns:
        filtered_df = filtered_df[
            filtered_df["fundamental_score"].fillna(-999) >= min_fundamental_score
        ]

    if "valuation_score" in filtered_df.columns:
        filtered_df = filtered_df[
            filtered_df["valuation_score"].fillna(-999) >= min_valuation_score
        ]

    if "institutional_smart_money_score" in filtered_df.columns:
        filtered_df = filtered_df[
            filtered_df["institutional_smart_money_score"].fillna(-999)
            >= min_institutional_score
        ]

    if require_above_150dma and "distance_from_150dma" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["distance_from_150dma"].fillna(-999) >= 0]

    if hide_profit_locker_warning and "profit_locker_status" in filtered_df.columns:
        filtered_df = filtered_df[
            ~filtered_df["profit_locker_status"]
            .str.lower()
            .str.contains(
                "locker|caution|warning|extended|danger",
                na=False,
            )
        ]

    if require_positive_margin_of_safety and "margin_of_safety" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["margin_of_safety"].fillna(-999) > 0]

    if (
        require_institutional_accumulation
        and "institutional_net_qoq_flow_pct" in filtered_df.columns
    ):
        filtered_df = filtered_df[
            filtered_df["institutional_net_qoq_flow_pct"].fillna(-999) > 0
        ]

    return filtered_df


def sort_watchlist_results(
    df: pd.DataFrame,
    sort_option: str = "Final Score",
    ascending: bool = False,
) -> pd.DataFrame:
    """
    Sorts filtered watchlist results.
    """

    if df is None or df.empty:
        return pd.DataFrame()

    sorted_df = df.copy()

    sort_map = {
        "Final Score": "final_score",
        "Chart Score": "chart_score",
        "Fundamental Score": "fundamental_score",
        "Valuation Score": "valuation_score",
        "Smart Money Score": "final_smart_money_score",
        "Institutional Score": "institutional_smart_money_score",
        "Institutional Flow": "institutional_net_qoq_flow_pct",
        "Margin of Safety": "margin_of_safety",
        "Distance From 150DMA": "distance_from_150dma",
    }

    sort_column = sort_map.get(sort_option, "final_score")

    if sort_column in sorted_df.columns:
        sorted_df[sort_column] = pd.to_numeric(
            sorted_df[sort_column],
            errors="coerce",
        )

        sorted_df = sorted_df.sort_values(
            by=sort_column,
            ascending=ascending,
            na_position="last",
        )

    return sorted_df


def get_watchlist_display_columns() -> list:
    """
    Preferred display columns for the Watchlist Scanner 2.0 table.
    """

    return [
        "ticker",
        "status",
        "final_score",
        "final_label",
        "final_action",
        "current_price",
        "dma_150",
        "distance_from_150dma",
        "profit_locker_status",
        "chart_score",
        "fundamental_score",
        "valuation_score",
        "final_smart_money_score",
        "institutional_smart_money_score",
        "institutional_holding_count",
        "institutional_net_qoq_flow_pct",
        "valuation_label",
        "margin_of_safety",
        "heartbeat_status",
        "error",
    ]
