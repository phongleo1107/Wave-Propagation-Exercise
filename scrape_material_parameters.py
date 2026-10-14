"""Scrape public material-property pages into the Task 1 CSV format.

This script uses requests for HTTP access, urllib.robotparser to honor
robots.txt, and BeautifulSoup to parse HTML text. Its main aim is to collect
best-effort Young's modulus, Poisson's ratio, and density values without
bypassing access controls; missing fields are written as None and failed
URLs are logged separately.
"""

import re
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import pandas as pd
import requests
from bs4 import BeautifulSoup


CONFIG = {
    "output_csv": Path("scraped_material_parameters.csv"),
    "failed_urls_file": Path("scrape_failed_urls.txt"),
    "user_agent": "WavePropagationExerciseResearch/1.0 (educational use)",
    "request_delay_seconds": 2.0,
    "timeout_seconds": 20,
    "terms_urls": {
        "www.matweb.com": "https://www.matweb.com",
        "matweb.com": "https://www.matweb.com",
        "www.engineeringtoolbox.com": "https://www.engineeringtoolbox.com",
        "engineeringtoolbox.com": "https://www.engineeringtoolbox.com",
    },
    # Add only public URLs whose robots.txt and terms permit automated access.
    "source_urls": [],
}

HEADERS = {"User-Agent": CONFIG["user_agent"]}


def access_is_allowed(
    url: str, session: requests.Session, last_request: list[float]
) -> bool:
    """Check robots.txt and fetch the site's terms page before scraping."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"Invalid URL: {url}")
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    robots = RobotFileParser()
    robots.set_url(robots_url)
    try:
        robots.read()
    except (OSError, requests.RequestException) as exc:
        raise RuntimeError(f"Could not verify robots.txt at {robots_url}: {exc}") from exc
    if not robots.can_fetch(CONFIG["user_agent"], url):
        return False
    terms_url = CONFIG["terms_urls"].get(parsed.netloc.lower())
    if not terms_url:
        raise RuntimeError(
            f"No configured terms URL for {parsed.netloc}; review the site's terms first."
        )
    response = polite_get(session, terms_url, last_request)
    response.raise_for_status()
    return True


def polite_get(
    session: requests.Session, url: str, last_request: list[float]
) -> requests.Response:
    """Issue a request only after the configured minimum inter-request delay."""
    elapsed = time.monotonic() - last_request[0]
    time.sleep(max(0.0, CONFIG["request_delay_seconds"] - elapsed))
    response = session.get(url, headers=HEADERS, timeout=CONFIG["timeout_seconds"])
    last_request[0] = time.monotonic()
    return response


def find_number(text: str, patterns: list[str]) -> float | None:
    """Return the first numeric value following one of the supplied labels."""
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return float(match.group(1).replace(",", ""))
    return None


def parse_material_page(url: str, html: str) -> dict:
    """Extract common property labels and normalize units where recognizable."""
    soup = BeautifulSoup(html, "html.parser")
    text = " ".join(soup.stripped_strings)
    title = soup.title.get_text(" ", strip=True) if soup.title else url
    name = title.split("|")[0].strip() or url
    youngs_gpa = find_number(
        text, [r"Young(?:'s)?\s+Modulus[^0-9]*([0-9]+(?:\.[0-9]+)?)\s*GPa"]
    )
    poisson = find_number(
        text, [r"Poisson(?:'s)?\s+Ratio[^0-9]*([0-9]+(?:\.[0-9]+)?)"]
    )
    density = find_number(
        text, [r"Density[^0-9]*([0-9]+(?:\.[0-9]+)?)\s*(?:kg/m[³3]|kg/m\^3)"]
    )
    return {
        "name": name,
        "E_GPa": youngs_gpa,
        "nu": poisson,
        "rho_kg_m3": density,
        "source_url": url,
    }


def main() -> None:
    """Scrape configured URLs, preserving failures and missing fields."""
    rows = []
    failures = []
    last_request = [0.0]
    with requests.Session() as session:
        for url in CONFIG["source_urls"]:
            try:
                if not access_is_allowed(url, session, last_request):
                    failures.append(f"{url}\tblocked by robots.txt")
                    continue
                response = polite_get(session, url, last_request)
                response.raise_for_status()
                rows.append(parse_material_page(url, response.text))
            except (OSError, requests.RequestException, RuntimeError, ValueError) as exc:
                failures.append(f"{url}\t{exc}")
    pd.DataFrame(
        rows, columns=["name", "E_GPa", "nu", "rho_kg_m3", "source_url"]
    ).to_csv(CONFIG["output_csv"], index=False)
    CONFIG["failed_urls_file"].write_text(
        "\n".join(failures) + ("\n" if failures else ""), encoding="utf-8"
    )
    print(f"Wrote {len(rows)} records to {CONFIG['output_csv']}")
    print(f"Wrote {len(failures)} failures to {CONFIG['failed_urls_file']}")


if __name__ == "__main__":
    main()
