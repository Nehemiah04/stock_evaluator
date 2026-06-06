from pathlib import Path

import pandas as pd
import plotly.express as px


HOLDINGS_PATH = Path("data/institution_holdings_sample.csv")


def load_institution_holdings_sample(file_path: str = str(HOLDINGS_PATH)) -> pd.DataFrame:
    try:
        df = pd.read_csv(file_path)
    except FileNotFoundError:
        return pd.DataFrame()

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

    missing_columns = [column for column in required_columns if column not in df.columns]

    if missing_columns:
        raise ValueError(
            f"Missing required columns in institution_holdings_sample.csv: {missing_columns}"
        )

    numeric_columns = [
        "market_value_billions",
        "position_change_qoq_pct",
        "shares_change_qoq_pct",
    ]

    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    df = df.dropna(
        subset=[
            "institution",
            "sector",
            "ticker",
            "company",
            "market_value_billions",
            "position_change_qoq_pct",
        ]
    )

    text_columns = [
        "institution",
        "sector",
        "ticker",
        "company",
        "flow_status",
        "report_date",
    ]

    for column in text_columns:
        df[column] = df[column].astype(str).str.strip()

    df["ticker"] = df["ticker"].str.upper()

    return df


def merge_holdings_with_universe(holdings_df: pd.DataFrame, universe_df: pd.DataFrame) -> pd.DataFrame:
    if holdings_df.empty:
        return pd.DataFrame()

    if universe_df.empty:
        merged_df = holdings_df.copy()
        merged_df["type"] = "Unknown"
        merged_df["city"] = "Unknown"
        merged_df["country"] = "Unknown"
        merged_df["assets_or_aum_trillions"] = 0
        merged_df["trackability"] = "Unknown"
        return merged_df

    universe_columns = [
        "institution",
        "type",
        "city",
        "country",
        "assets_or_aum_trillions",
        "trackability",
    ]

    clean_universe = universe_df[universe_columns].copy()

    merged_df = holdings_df.merge(
        clean_universe,
        on="institution",
        how="left",
    )

    merged_df["type"] = merged_df["type"].fillna("Unknown")
    merged_df["city"] = merged_df["city"].fillna("Unknown")
    merged_df["country"] = merged_df["country"].fillna("Unknown")
    merged_df["assets_or_aum_trillions"] = merged_df["assets_or_aum_trillions"].fillna(0)
    merged_df["trackability"] = merged_df["trackability"].fillna("Unknown")

    return merged_df


def get_flow_label(net_qoq_change_pct: float) -> str:
    if net_qoq_change_pct >= 5:
        return "Accumulating"
    elif net_qoq_change_pct >= 1:
        return "Slight Accumulating"
    elif net_qoq_change_pct > -1:
        return "Neutral"
    elif net_qoq_change_pct > -5:
        return "Slight Reducing"
    else:
        return "Reducing"


def weighted_average_qoq(group: pd.DataFrame) -> float:
    total_value = group["market_value_billions"].sum()

    if total_value == 0:
        return group["position_change_qoq_pct"].mean()

    return (
        group["position_change_qoq_pct"] * group["market_value_billions"]
    ).sum() / total_value


def top_holdings_text(group: pd.DataFrame, top_n: int = 3) -> str:
    top_holdings = group.sort_values(
        by="market_value_billions",
        ascending=False,
    ).head(top_n)

    labels = []

    for _, row in top_holdings.iterrows():
        labels.append(
            f"{row['ticker']} ({row['company']}) ${row['market_value_billions']:.1f}B"
        )

    return " | ".join(labels)


def aggregate_institution_sector_exposure(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    rows = []

    for keys, group in df.groupby(["type", "institution", "sector"]):
        institution_type, institution, sector = keys

        market_value = group["market_value_billions"].sum()
        net_qoq_change = weighted_average_qoq(group)
        top_holdings = top_holdings_text(group)

        rows.append(
            {
                "type": institution_type,
                "institution": institution,
                "sector": sector,
                "market_value_billions": market_value,
                "net_qoq_change_pct": net_qoq_change,
                "flow_label": get_flow_label(net_qoq_change),
                "top_holdings": top_holdings,
                "holding_count": len(group),
            }
        )

    return pd.DataFrame(rows)


def aggregate_sector_institution_exposure(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    rows = []

    for keys, group in df.groupby(["sector", "institution"]):
        sector, institution = keys

        market_value = group["market_value_billions"].sum()
        net_qoq_change = weighted_average_qoq(group)
        top_holdings = top_holdings_text(group)

        rows.append(
            {
                "sector": sector,
                "institution": institution,
                "market_value_billions": market_value,
                "net_qoq_change_pct": net_qoq_change,
                "flow_label": get_flow_label(net_qoq_change),
                "top_holdings": top_holdings,
                "holding_count": len(group),
            }
        )

    return pd.DataFrame(rows)


def build_holdings_summary(df: pd.DataFrame) -> dict:
    if df.empty:
        return {
            "institution_count": 0,
            "sector_count": 0,
            "holding_count": 0,
            "total_market_value": 0,
            "net_qoq_change": 0,
            "top_sector": "N/A",
        }

    total_market_value = df["market_value_billions"].sum()
    net_qoq_change = weighted_average_qoq(df)
    sector_totals = df.groupby("sector")["market_value_billions"].sum()

    top_sector = "N/A" if sector_totals.empty else sector_totals.sort_values(ascending=False).index[0]

    return {
        "institution_count": df["institution"].nunique(),
        "sector_count": df["sector"].nunique(),
        "holding_count": len(df),
        "total_market_value": total_market_value,
        "net_qoq_change": net_qoq_change,
        "top_sector": top_sector,
    }


def build_institution_sector_treemap(df: pd.DataFrame):
    exposure_df = aggregate_institution_sector_exposure(df)

    if exposure_df.empty:
        return px.treemap(
            pd.DataFrame(
                {
                    "type": ["No Data"],
                    "institution": ["No Data"],
                    "sector": ["No Data"],
                    "market_value_billions": [1],
                    "net_qoq_change_pct": [0],
                }
            ),
            path=["type", "institution", "sector"],
            values="market_value_billions",
            color="net_qoq_change_pct",
            title="Institution → Sector Exposure",
        )

    fig = px.treemap(
        exposure_df,
        path=["type", "institution", "sector"],
        values="market_value_billions",
        color="net_qoq_change_pct",
        color_continuous_scale="RdYlGn",
        color_continuous_midpoint=0,
        hover_data={
            "market_value_billions": ":.2f",
            "net_qoq_change_pct": ":.2f",
            "flow_label": True,
            "top_holdings": True,
            "holding_count": True,
        },
        title="Institution → Sector Exposure",
    )

    fig.update_traces(
        texttemplate="<b>%{label}</b><br>$%{value:.1f}B",
        textposition="middle center",
        marker=dict(line=dict(width=1)),
    )

    fig.update_layout(
        height=800,
        margin=dict(l=10, r=10, t=60, b=10),
        coloraxis_colorbar=dict(title="QoQ Flow %"),
    )

    return fig


def build_sector_institution_treemap(df: pd.DataFrame):
    exposure_df = aggregate_sector_institution_exposure(df)

    if exposure_df.empty:
        return px.treemap(
            pd.DataFrame(
                {
                    "sector": ["No Data"],
                    "institution": ["No Data"],
                    "market_value_billions": [1],
                    "net_qoq_change_pct": [0],
                }
            ),
            path=["sector", "institution"],
            values="market_value_billions",
            color="net_qoq_change_pct",
            title="Sector → Institution Exposure",
        )

    fig = px.treemap(
        exposure_df,
        path=["sector", "institution"],
        values="market_value_billions",
        color="net_qoq_change_pct",
        color_continuous_scale="RdYlGn",
        color_continuous_midpoint=0,
        hover_data={
            "market_value_billions": ":.2f",
            "net_qoq_change_pct": ":.2f",
            "flow_label": True,
            "top_holdings": True,
            "holding_count": True,
        },
        title="Sector → Institution Exposure",
    )

    fig.update_traces(
        texttemplate="<b>%{label}</b><br>$%{value:.1f}B",
        textposition="middle center",
        marker=dict(line=dict(width=1)),
    )

    fig.update_layout(
        height=800,
        margin=dict(l=10, r=10, t=60, b=10),
        coloraxis_colorbar=dict(title="QoQ Flow %"),
    )

    return fig


def prepare_holdings_table(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    table = df.copy()

    columns = [
        "institution",
        "type",
        "sector",
        "ticker",
        "company",
        "market_value_billions",
        "position_change_qoq_pct",
        "shares_change_qoq_pct",
        "flow_status",
        "report_date",
    ]

    table = table[columns]

    table = table.rename(
        columns={
            "institution": "Institution",
            "type": "Type",
            "sector": "Sector",
            "ticker": "Ticker",
            "company": "Company",
            "market_value_billions": "Market Value ($B)",
            "position_change_qoq_pct": "Position Change QoQ %",
            "shares_change_qoq_pct": "Shares Change QoQ %",
            "flow_status": "Flow Status",
            "report_date": "Report Date",
        }
    )

    table = table.sort_values(
        by="Market Value ($B)",
        ascending=False,
    )

    return table
