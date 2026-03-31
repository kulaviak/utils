import asyncio
from pathlib import Path

import requests
from playwright.async_api import async_playwright


SEC_HEADERS = {
    # SEC asks for an identifying User-Agent with contact info.
    "User-Agent": "DemoScript/1.0 jkulaviak@gmail.com",
    "Accept-Encoding": "gzip, deflate",
    "Accept": "application/json, text/html;q=0.9,*/*;q=0.8",
}


def get_latest_10k_for_apple() -> tuple[str, str]:
    cik = "0000320193"  # Apple Inc.
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    response = requests.get(url, headers=SEC_HEADERS, timeout=30)
    response.raise_for_status()
    data = response.json()

    recent = data["filings"]["recent"]
    forms = recent["form"]
    accession_numbers = recent["accessionNumber"]
    primary_docs = recent["primaryDocument"]

    for form, accession, primary_doc in zip(forms, accession_numbers, primary_docs):
        if form == "10-K":
            accession_nodash = accession.replace("-", "")
            filing_url = (
                f"https://www.sec.gov/Archives/edgar/data/320193/"
                f"{accession_nodash}/{primary_doc}"
            )
            return accession, filing_url

    raise RuntimeError("Could not find a 10-K filing for Apple.")


async def save_filing_page_as_pdf(filing_url: str, output_pdf: Path) -> None:
    filing_response = requests.get(filing_url, headers=SEC_HEADERS, timeout=60)
    filing_response.raise_for_status()
    filing_html = filing_response.text
    # Keep relative links (images/css) resolvable when rendering HTML content directly.
    html_with_base = f'<base href="{filing_url}">\n{filing_html}'

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=SEC_HEADERS["User-Agent"],
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        page = await context.new_page()
        await page.set_content(html_with_base, wait_until="networkidle")
        await page.pdf(path=str(output_pdf), format="A4", print_background=True)
        await context.close()
        await browser.close()


def main() -> None:
    accession_no, filing_url = get_latest_10k_for_apple()
    output_name = Path(f"aapl_10k_{accession_no}.pdf")
    asyncio.run(save_filing_page_as_pdf(filing_url, output_name))
    print(f"Saved latest Apple 10-K as PDF: {output_name}")
    print(f"Source filing URL: {filing_url}")


if __name__ == "__main__":
    main()
