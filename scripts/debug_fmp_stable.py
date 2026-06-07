import os
import requests


def test_endpoint(name, url):
    api_key = os.getenv("FMP_API_KEY")

    if not api_key:
        print("ERROR: FMP_API_KEY is not set.")
        return

    full_url = f"{url}&apikey={api_key}" if "?" in url else f"{url}?apikey={api_key}"

    print("=" * 80)
    print(name)
    print("=" * 80)
    print(full_url.replace(api_key, "HIDDEN_KEY"))

    response = requests.get(full_url, timeout=30)

    print(f"HTTP status: {response.status_code}")
    print("Response preview:")
    print(response.text[:1200])
    print()


def main():
    test_endpoint(
        "Stable Profile Test",
        "https://financialmodelingprep.com/stable/profile?symbol=NVDA"
    )

    test_endpoint(
        "Stable Institutional Latest Filings Test",
        "https://financialmodelingprep.com/stable/institutional-ownership/latest?page=0&limit=5"
    )

    test_endpoint(
        "Stable Symbol Positions Summary Test",
        "https://financialmodelingprep.com/stable/institutional-ownership/symbol-positions-summary?symbol=NVDA&year=2025&quarter=4"
    )


if __name__ == "__main__":
    main()
