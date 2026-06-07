from pathlib import Path

import pandas as pd
import plotly.express as px

UNIVERSE_PATH = Path("data/smart_money_universe.csv")


def load_institution_universe(file_path: str = str(UNIVERSE_PATH)) -> pd.DataFrame:
    """
    Loads the static institution universe used for the Institutional Smart Money Heat Map.
    """

    try:
        df = pd.read_csv(file_path)
    except FileNotFoundError:
        return pd.DataFrame()

    required_columns = [
        "institution",
        "type",
        "city",
        "country",
        "assets_or_aum_trillions",
        "latitude",
        "longitude",
        "trackability",
    ]

    missing_columns = [
        column for column in required_columns if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing required columns in smart_money_universe.csv: {missing_columns}"
        )

    df["assets_or_aum_trillions"] = pd.to_numeric(
        df["assets_or_aum_trillions"], errors="coerce"
    )

    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")

    df = df.dropna(subset=["assets_or_aum_trillions", "latitude", "longitude"])

    df["institution"] = df["institution"].astype(str).str.strip()
    df["type"] = df["type"].astype(str).str.strip()
    df["city"] = df["city"].astype(str).str.strip()
    df["country"] = df["country"].astype(str).str.strip()
    df["trackability"] = df["trackability"].astype(str).str.strip()

    df["trackability_score"] = (
        df["trackability"].map({"Low": -1, "Medium": 0, "High": 1}).fillna(0)
    )

    df["display_assets"] = df["assets_or_aum_trillions"].apply(
        lambda value: f"${value:.2f}T"
    )

    return df


def build_institution_summary(df: pd.DataFrame) -> dict:
    """
    Builds summary metrics for the Institutional Smart Money Heat Map.
    """

    if df.empty:
        return {
            "institution_count": 0,
            "total_assets_or_aum": 0,
            "high_trackability_count": 0,
            "bank_count": 0,
            "alt_manager_count": 0,
            "hedge_fund_count": 0,
        }

    institution_count = len(df)
    total_assets_or_aum = df["assets_or_aum_trillions"].sum()

    high_trackability_count = len(df[df["trackability"].str.lower() == "high"])

    bank_count = len(df[df["type"].str.lower() == "bank"])

    alt_manager_count = len(
        df[df["type"].str.lower().str.contains("private equity|alt")]
    )

    hedge_fund_count = len(df[df["type"].str.lower().str.contains("hedge")])

    return {
        "institution_count": institution_count,
        "total_assets_or_aum": total_assets_or_aum,
        "high_trackability_count": high_trackability_count,
        "bank_count": bank_count,
        "alt_manager_count": alt_manager_count,
        "hedge_fund_count": hedge_fund_count,
    }


def build_institution_heatmap_figure(df: pd.DataFrame):
    """
    Builds a Finviz-style institutional heat map.

    Box size = assets/AUM.
    Box color = trackability for now.

    Later in Phase 6B:
    Box color should become institutional buying/selling flow.
    """

    if df.empty:
        return px.treemap(
            pd.DataFrame(
                {
                    "type": ["No Data"],
                    "country": ["No Data"],
                    "institution": ["No Data"],
                    "assets_or_aum_trillions": [1],
                    "trackability_score": [0],
                }
            ),
            path=["type", "country", "institution"],
            values="assets_or_aum_trillions",
            color="trackability_score",
            title="Institutional Smart Money Heat Map",
        )

    fig = px.treemap(
        df,
        path=["type", "country", "institution"],
        values="assets_or_aum_trillions",
        color="trackability_score",
        color_continuous_scale="RdYlGn",
        color_continuous_midpoint=0,
        hover_data={
            "assets_or_aum_trillions": ":.2f",
            "trackability": True,
            "city": True,
            "country": True,
            "trackability_score": False,
        },
        title="Institutional Smart Money Heat Map",
    )

    fig.update_traces(
        texttemplate="<b>%{label}</b><br>%{value:.2f}T",
        textposition="middle center",
        marker=dict(line=dict(width=1)),
    )

    fig.update_layout(
        height=750,
        margin=dict(l=10, r=10, t=60, b=10),
        coloraxis_colorbar=dict(
            title="Trackability",
            tickvals=[-1, 0, 1],
            ticktext=["Low", "Medium", "High"],
        ),
    )

    return fig


def prepare_institution_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepares a clean table for Streamlit display.
    """

    if df.empty:
        return pd.DataFrame()

    table = df.copy()

    table = table[
        [
            "institution",
            "type",
            "city",
            "country",
            "assets_or_aum_trillions",
            "trackability",
        ]
    ]

    table = table.rename(
        columns={
            "institution": "Institution",
            "type": "Type",
            "city": "City",
            "country": "Country",
            "assets_or_aum_trillions": "Assets / AUM ($T)",
            "trackability": "Trackability",
        }
    )

    table = table.sort_values(by="Assets / AUM ($T)", ascending=False)

    return table
