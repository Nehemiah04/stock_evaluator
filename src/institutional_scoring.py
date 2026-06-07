import pandas as pd


def clip_score(value: float, low: float = -5.0, high: float = 5.0) -> float:
    try:
        value = float(value)
    except Exception:
        return 0.0

    return max(low, min(value, high))


def safe_numeric_series(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def weighted_average_change(df: pd.DataFrame) -> float:
    if df.empty:
        return 0.0

    value_col = safe_numeric_series(df["market_value_billions"])
    change_col = safe_numeric_series(df["position_change_qoq_pct"])

    total_value = value_col.sum()

    if total_value == 0:
        return float(change_col.mean())

    return float((change_col * value_col).sum() / total_value)


def get_flow_label(score: float) -> str:
    if score >= 4:
        return "Strong institutional accumulation"
    elif score >= 2:
        return "Institutional accumulation"
    elif score > 0:
        return "Slight institutional support"
    elif score == 0:
        return "Neutral / no clear institutional edge"
    elif score > -2:
        return "Slight institutional distribution"
    elif score > -4:
        return "Institutional distribution"
    else:
        return "Strong institutional distribution"


def get_flow_action(score: float) -> str:
    if score >= 3:
        return "Smart money strongly supports the setup"
    elif score > 0:
        return "Smart money slightly supports the setup"
    elif score == 0:
        return "No clear institutional signal"
    elif score > -3:
        return "Institutional caution flag"
    else:
        return "Institutional selling pressure is a major warning"


def prepare_scoring_df(df: pd.DataFrame, ticker: str | None = None) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    scoring_df = df.copy()

    required_columns = [
        "institution",
        "sector",
        "ticker",
        "company",
        "market_value_billions",
        "position_change_qoq_pct",
        "shares_change_qoq_pct",
        "flow_status",
        "report_date",
    ]

    for column in required_columns:
        if column not in scoring_df.columns:
            scoring_df[column] = None

    scoring_df["ticker"] = scoring_df["ticker"].astype(str).str.upper().str.strip()
    scoring_df["market_value_billions"] = safe_numeric_series(
        scoring_df["market_value_billions"]
    )
    scoring_df["position_change_qoq_pct"] = safe_numeric_series(
        scoring_df["position_change_qoq_pct"]
    )
    scoring_df["shares_change_qoq_pct"] = safe_numeric_series(
        scoring_df["shares_change_qoq_pct"]
    )

    if ticker:
        scoring_df = scoring_df[scoring_df["ticker"] == ticker.upper()]

    return scoring_df


def aggregate_top_flows(
    df: pd.DataFrame, group_col: str, top_n: int = 5
) -> pd.DataFrame:
    if df.empty or group_col not in df.columns:
        return pd.DataFrame()

    rows = []

    for group_name, group in df.groupby(group_col):
        market_value = group["market_value_billions"].sum()
        net_change = weighted_average_change(group)

        rows.append(
            {
                group_col: group_name,
                "market_value_billions": market_value,
                "net_qoq_change_pct": net_change,
                "holding_count": len(group),
            }
        )

    result = pd.DataFrame(rows)

    if result.empty:
        return result

    return result.sort_values(
        by="net_qoq_change_pct",
        ascending=False,
    ).head(top_n)


def build_institutional_smart_money_summary(
    df: pd.DataFrame, ticker: str | None = None
) -> dict:
    """
    Converts institutional holdings flow into a -5 to +5 Smart Money Score.

    Score components:
    - Net QoQ flow: Are positions increasing or decreasing?
    - Breadth: Are more institutions accumulating or reducing?
    - Institution count: How many tracked institutions are involved?
    """

    scoring_df = prepare_scoring_df(df, ticker=ticker)

    if scoring_df.empty:
        return {
            "institutional_smart_money_score": 0.0,
            "institutional_smart_money_label": "Neutral / no institutional data",
            "institutional_smart_money_action": "Use manual Smart Money inputs or Sample CSV until data is available",
            "net_qoq_flow_pct": 0.0,
            "accumulating_count": 0,
            "reducing_count": 0,
            "neutral_count": 0,
            "institution_count": 0,
            "sector_count": 0,
            "holding_count": 0,
            "total_market_value_billions": 0.0,
        }

    net_qoq_flow = weighted_average_change(scoring_df)

    accumulating_count = len(scoring_df[scoring_df["position_change_qoq_pct"] >= 1])
    reducing_count = len(scoring_df[scoring_df["position_change_qoq_pct"] <= -1])
    neutral_count = len(scoring_df) - accumulating_count - reducing_count

    holding_count = len(scoring_df)
    institution_count = scoring_df["institution"].nunique()
    sector_count = scoring_df["sector"].nunique()
    total_market_value = scoring_df["market_value_billions"].sum()

    if holding_count == 0:
        breadth_score = 0
    else:
        breadth_score = ((accumulating_count - reducing_count) / holding_count) * 1.5

    flow_score = clip_score(net_qoq_flow / 5, low=-3, high=3)

    institution_depth_score = min(institution_count / 10, 1) * 0.5

    raw_score = flow_score + breadth_score + institution_depth_score
    final_score = round(clip_score(raw_score), 2)

    return {
        "institutional_smart_money_score": final_score,
        "institutional_smart_money_label": get_flow_label(final_score),
        "institutional_smart_money_action": get_flow_action(final_score),
        "net_qoq_flow_pct": round(net_qoq_flow, 2),
        "accumulating_count": accumulating_count,
        "reducing_count": reducing_count,
        "neutral_count": neutral_count,
        "institution_count": institution_count,
        "sector_count": sector_count,
        "holding_count": holding_count,
        "total_market_value_billions": round(total_market_value, 2),
    }


def build_institutional_score_table(summary: dict) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Metric": [
                "Institutional Smart Money Score",
                "Institutional Label",
                "Institutional Action",
                "Net QoQ Flow",
                "Accumulating Holdings",
                "Reducing Holdings",
                "Neutral Holdings",
                "Institutions Tracked",
                "Sectors Tracked",
                "Holding Rows",
                "Total Market Value",
            ],
            "Value": [
                f"{summary.get('institutional_smart_money_score', 0)}/5",
                summary.get("institutional_smart_money_label", "N/A"),
                summary.get("institutional_smart_money_action", "N/A"),
                f"{summary.get('net_qoq_flow_pct', 0):.2f}%",
                summary.get("accumulating_count", 0),
                summary.get("reducing_count", 0),
                summary.get("neutral_count", 0),
                summary.get("institution_count", 0),
                summary.get("sector_count", 0),
                summary.get("holding_count", 0),
                f"${summary.get('total_market_value_billions', 0):.2f}B",
            ],
        }
    )


def build_top_flow_tables(df: pd.DataFrame) -> dict:
    scoring_df = prepare_scoring_df(df)

    if scoring_df.empty:
        return {
            "top_accumulating_sectors": pd.DataFrame(),
            "top_reducing_sectors": pd.DataFrame(),
            "top_accumulating_institutions": pd.DataFrame(),
            "top_reducing_institutions": pd.DataFrame(),
        }

    sector_flows = aggregate_top_flows(scoring_df, "sector", top_n=10)
    institution_flows = aggregate_top_flows(scoring_df, "institution", top_n=10)

    top_reducing_sectors = sector_flows.sort_values(
        by="net_qoq_change_pct",
        ascending=True,
    ).head(10)

    top_reducing_institutions = institution_flows.sort_values(
        by="net_qoq_change_pct",
        ascending=True,
    ).head(10)

    return {
        "top_accumulating_sectors": sector_flows,
        "top_reducing_sectors": top_reducing_sectors,
        "top_accumulating_institutions": institution_flows,
        "top_reducing_institutions": top_reducing_institutions,
    }
