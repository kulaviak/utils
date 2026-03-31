import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

from my_sec_api import SEC_HEADERS, save_filing_page_as_pdf


def get_cik_for_ticker(ticker: str) -> str:
    url = "https://www.sec.gov/files/company_tickers.json"
    response = requests.get(url, headers=SEC_HEADERS, timeout=30)
    response.raise_for_status()
    data = response.json()

    ticker_upper = ticker.upper()
    for item in data.values():
        if item["ticker"].upper() == ticker_upper:
            return str(item["cik_str"]).zfill(10)

    raise RuntimeError(f"Ticker not found in SEC list: {ticker}")


def get_recent_10k_filings(cik_10: str, years_back: int = 5) -> list[tuple[str, str, str]]:
    submissions_url = f"https://data.sec.gov/submissions/CIK{cik_10}.json"
    response = requests.get(submissions_url, headers=SEC_HEADERS, timeout=30)
    response.raise_for_status()
    data = response.json()

    recent = data["filings"]["recent"]
    forms = recent["form"]
    accession_numbers = recent["accessionNumber"]
    filing_dates = recent["filingDate"]
    primary_docs = recent["primaryDocument"]

    current_year = datetime.now(timezone.utc).year
    min_year = current_year - years_back + 1
    cik_no_leading_zeros = str(int(cik_10))

    filings: list[tuple[str, str, str]] = []
    for form, accession, filing_date, primary_doc in zip(
        forms, accession_numbers, filing_dates, primary_docs
    ):
        if form != "10-K":
            continue

        filing_year = int(filing_date[:4])
        if filing_year < min_year:
            continue

        accession_nodash = accession.replace("-", "")
        filing_url = (
            f"https://www.sec.gov/Archives/edgar/data/{cik_no_leading_zeros}/"
            f"{accession_nodash}/{primary_doc}"
        )
        filings.append((accession, filing_date, filing_url))

    return filings


def main() -> None:
    if len(sys.argv) < 3:
        raise RuntimeError("Usage: python download_10k.py <TICKER> <YEARS_BACK>")

    ticker = sys.argv[1].upper()
    try:
        years_back = int(sys.argv[2])
    except ValueError as exc:
        raise RuntimeError("YEARS_BACK must be an integer.") from exc
    if years_back < 1:
        raise RuntimeError("YEARS_BACK must be >= 1.")

    cik_10 = get_cik_for_ticker(ticker)
    filings = get_recent_10k_filings(cik_10, years_back=years_back)

    if not filings:
        print(f"No 10-K filings found in last {years_back} year(s) for {ticker}.")
        return

    out_dir = Path(f"{ticker.lower()}_10k_last_{years_back}_years")
    out_dir.mkdir(parents=True, exist_ok=True)

    for accession, filing_date, filing_url in filings:
        output_pdf = out_dir / f"{ticker.lower()}_10k_{filing_date}_{accession}.pdf"
        print(f"Downloading {ticker} 10-K ({filing_date}) -> {output_pdf.name}")
        asyncio.run(save_filing_page_as_pdf(filing_url, output_pdf))

    print(
        f"Done. Downloaded {len(filings)} filing(s) from last {years_back} year(s) into: {out_dir}"
    )


if __name__ == "__main__":
    main()
