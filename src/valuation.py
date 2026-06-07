def safe_ratio(numerator, denominator):
    """
    Safely divides two values.
    """
    if numerator is None or denominator is None:
        return None

    if denominator == 0:
        return None

    return numerator / denominator


def calculate_dcf_value(
    annual_fcf,
    shares_outstanding,
    growth_rate=0.10,
    discount_rate=0.10,
    terminal_growth_rate=0.03,
    years=5,
):
    """
    Basic DCF model using annualized free cash flow.

    annual_fcf: annual free cash flow in dollars
    growth_rate: expected FCF growth rate as decimal, example 0.10 = 10%
    discount_rate: required return as decimal, example 0.10 = 10%
    terminal_growth_rate: terminal growth as decimal, example 0.03 = 3%
    years: projection years
    """

    if annual_fcf is None or shares_outstanding is None:
        return None

    if annual_fcf <= 0 or shares_outstanding <= 0:
        return None

    if discount_rate <= terminal_growth_rate:
        return None

    present_value_cash_flows = 0
    projected_fcf = annual_fcf

    for year in range(1, years + 1):
        projected_fcf = projected_fcf * (1 + growth_rate)
        discounted_fcf = projected_fcf / ((1 + discount_rate) ** year)
        present_value_cash_flows += discounted_fcf

    terminal_fcf = projected_fcf * (1 + terminal_growth_rate)

    terminal_value = terminal_fcf / (discount_rate - terminal_growth_rate)

    present_value_terminal = terminal_value / ((1 + discount_rate) ** years)

    equity_value = present_value_cash_flows + present_value_terminal

    value_per_share = equity_value / shares_outstanding

    return {
        "present_value_cash_flows": present_value_cash_flows,
        "present_value_terminal": present_value_terminal,
        "equity_value": equity_value,
        "value_per_share": value_per_share,
    }


def calculate_eps_pe_value(
    eps, eps_growth_rate=0.10, future_pe=25, discount_rate=0.10, years=5
):
    """
    EPS x Growth x P/E model.

    Future EPS = EPS x (1 + growth rate) ^ years
    Future Price = Future EPS x Future P/E
    Present Value = Future Price discounted back to today
    """

    if eps is None:
        return None

    if eps <= 0:
        return None

    if future_pe <= 0:
        return None

    future_eps = eps * ((1 + eps_growth_rate) ** years)

    future_price = future_eps * future_pe

    present_value = future_price / ((1 + discount_rate) ** years)

    return {
        "future_eps": future_eps,
        "future_price": future_price,
        "value_per_share": present_value,
    }


def calculate_asset_value(stockholders_equity, shares_outstanding):
    """
    Asset-based value using stockholders' equity per share.
    This is most useful for asset-heavy or distressed companies.
    """

    if stockholders_equity is None or shares_outstanding is None:
        return None

    if shares_outstanding <= 0:
        return None

    value_per_share = stockholders_equity / shares_outstanding

    return {"value_per_share": value_per_share}


def calculate_margin_of_safety(intrinsic_value, current_price):
    """
    Margin of Safety = (Intrinsic Value - Current Price) / Intrinsic Value
    Returns percentage, not decimal.
    """

    if intrinsic_value is None or current_price is None:
        return None

    if intrinsic_value <= 0:
        return None

    return ((intrinsic_value - current_price) / intrinsic_value) * 100


def get_valuation_label(margin_of_safety):
    """
    Converts margin of safety into a valuation label.
    """

    if margin_of_safety is None:
        return "Needs more data"

    if margin_of_safety >= 30:
        return "Strong undervaluation"
    elif margin_of_safety >= 20:
        return "Attractive"
    elif margin_of_safety >= 10:
        return "Decent"
    elif margin_of_safety >= 0:
        return "Fair value"
    elif margin_of_safety >= -20:
        return "Expensive"
    else:
        return "Very expensive"


def calculate_valuation_score(margin_of_safety):
    """
    Scores valuation from 0 to 100.
    """

    if margin_of_safety is None:
        return 0

    if margin_of_safety >= 30:
        return 100
    elif margin_of_safety >= 20:
        return 85
    elif margin_of_safety >= 10:
        return 70
    elif margin_of_safety >= 0:
        return 55
    elif margin_of_safety >= -10:
        return 40
    elif margin_of_safety >= -20:
        return 25
    else:
        return 10


def build_valuation_summary(
    fundamentals,
    current_price,
    dcf_growth_rate=0.10,
    discount_rate=0.10,
    terminal_growth_rate=0.03,
    dcf_years=5,
    eps_growth_rate=0.10,
    future_pe=25,
    eps_years=5,
):
    """
    Builds a complete valuation summary using DCF, EPS/P/E, and asset value.

    The primary intrinsic value chooses:
    1. DCF value if available
    2. EPS/P/E value if DCF is not available
    3. Asset value if both are unavailable
    """

    annual_fcf = fundamentals.get("annualized_fcf")
    shares_outstanding = fundamentals.get("shares_outstanding")
    stockholders_equity = fundamentals.get("stockholders_equity")

    trailing_eps = fundamentals.get("trailing_eps")
    forward_eps = fundamentals.get("forward_eps")

    eps_to_use = (
        forward_eps if forward_eps is not None and forward_eps > 0 else trailing_eps
    )

    dcf_result = calculate_dcf_value(
        annual_fcf=annual_fcf,
        shares_outstanding=shares_outstanding,
        growth_rate=dcf_growth_rate,
        discount_rate=discount_rate,
        terminal_growth_rate=terminal_growth_rate,
        years=dcf_years,
    )

    eps_pe_result = calculate_eps_pe_value(
        eps=eps_to_use,
        eps_growth_rate=eps_growth_rate,
        future_pe=future_pe,
        discount_rate=discount_rate,
        years=eps_years,
    )

    asset_result = calculate_asset_value(
        stockholders_equity=stockholders_equity, shares_outstanding=shares_outstanding
    )

    dcf_value = None
    eps_pe_value = None
    asset_value = None

    if dcf_result is not None:
        dcf_value = dcf_result.get("value_per_share")

    if eps_pe_result is not None:
        eps_pe_value = eps_pe_result.get("value_per_share")

    if asset_result is not None:
        asset_value = asset_result.get("value_per_share")

    primary_intrinsic_value = None
    valuation_method = "N/A"

    if dcf_value is not None:
        primary_intrinsic_value = dcf_value
        valuation_method = "DCF"
    elif eps_pe_value is not None:
        primary_intrinsic_value = eps_pe_value
        valuation_method = "EPS x Growth x P/E"
    elif asset_value is not None:
        primary_intrinsic_value = asset_value
        valuation_method = "Asset value"

    margin_of_safety = calculate_margin_of_safety(
        primary_intrinsic_value, current_price
    )

    valuation_label = get_valuation_label(margin_of_safety)
    valuation_score = calculate_valuation_score(margin_of_safety)

    return {
        "dcf_value": dcf_value,
        "eps_pe_value": eps_pe_value,
        "asset_value": asset_value,
        "primary_intrinsic_value": primary_intrinsic_value,
        "valuation_method": valuation_method,
        "margin_of_safety": margin_of_safety,
        "valuation_label": valuation_label,
        "valuation_score": valuation_score,
    }
