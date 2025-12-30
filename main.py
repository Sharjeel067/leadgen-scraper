import argparse
import csv
import os
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Iterable, List, Optional

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

class FetchError(RuntimeError):
    pass


def fetch_html(
    url: str,
    *,
    headers: Optional[dict] = None,
    timeout: int = 30,
    retries: int = 3,
    backoff_seconds: float = 1.0,
) -> str:
    merged_headers = dict(DEFAULT_HEADERS)
    if headers:
        merged_headers.update(headers)

    last_exc: Optional[BaseException] = None
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, headers=merged_headers, timeout=timeout)
            response.raise_for_status()
            return response.text
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(backoff_seconds * attempt)

    raise FetchError(f"Failed to fetch {url} after {retries} attempts") from last_exc


@dataclass
class ServiceReview:
    service_name: str
    heading: str
    url: str
    summary: str
    how_it_works: str
    practice_areas: str
    pricing: str


_SERVICE_RE = re.compile(r"^(?P<name>.+?)\s+Review\s+for\s+Lawyers\s*$", re.IGNORECASE)


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _extract_section_text(container_nodes: List[Tag]) -> str:
    lines: List[str] = []
    for node in container_nodes:
        if node.name in {"p", "li"}:
            t = _clean_text(node.get_text(" ", strip=True))
            if t:
                lines.append(t)
    return "\n".join(lines).strip()


def _split_by_h3(nodes: List[Tag]) -> dict:
    sections: dict[str, List[Tag]] = {"summary": []}
    current_key = "summary"

    for node in nodes:
        if node.name == "h3":
            title = _clean_text(node.get_text(" ", strip=True)).lower()
            if "how" in title and "work" in title:
                current_key = "how_it_works"
            elif "practice" in title and "area" in title:
                current_key = "practice_areas"
            elif "pricing" in title or "price" in title:
                current_key = "pricing"
            else:
                current_key = f"section:{title}"
            sections.setdefault(current_key, [])
            continue

        if node.name == "h2":
            break

        sections.setdefault(current_key, []).append(node)

    return sections


def parse_services(url: str, html: str) -> List[ServiceReview]:
    soup = BeautifulSoup(html, "html.parser")

    services: List[ServiceReview] = []

    for h2 in soup.find_all("h2"):
        heading_text = _clean_text(h2.get_text(" ", strip=True))
        match = _SERVICE_RE.match(heading_text)
        if not match:
            continue

        service_name = match.group("name").strip()

        nodes: List[Tag] = []
        for sib in h2.find_next_siblings():
            if isinstance(sib, Tag) and sib.name == "h2":
                break
            if isinstance(sib, Tag):
                nodes.append(sib)

        sections = _split_by_h3(nodes)

        summary = _extract_section_text(sections.get("summary", []))
        how_it_works = _extract_section_text(sections.get("how_it_works", []))
        practice_areas = _extract_section_text(sections.get("practice_areas", []))
        pricing = _extract_section_text(sections.get("pricing", []))

        services.append(
            ServiceReview(
                service_name=service_name,
                heading=heading_text,
                url=url,
                summary=summary,
                how_it_works=how_it_works,
                practice_areas=practice_areas,
                pricing=pricing,
            )
        )

    return services


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def write_csv(rows: Iterable[ServiceReview], output_path: str) -> str:
    out_dir = os.path.dirname(output_path)
    if out_dir:
        _ensure_dir(out_dir)

    rows_list = list(rows)
    fieldnames = [
        "service_name",
        "heading",
        "url",
        "summary",
        "how_it_works",
        "practice_areas",
        "pricing",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows_list:
            d = asdict(row)
            writer.writerow({k: d.get(k, "") for k in fieldnames})

    return output_path


def _default_output_path(url: str) -> str:
    slug = url.rstrip("/").split("/")[-1] or "output"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    for folder in ("results", "output"):
        if os.path.isdir(folder) or folder == "results":
            os.makedirs(folder, exist_ok=True)
            return os.path.join(folder, f"{slug}_{ts}.csv")

    os.makedirs("results", exist_ok=True)
    return os.path.join("results", f"{slug}_{ts}.csv")


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape lawyer lead generation services reviews into CSV")
    parser.add_argument("url", help="Article URL")
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output CSV path (default: results/<slug>_<timestamp>.csv)",
    )

    args = parser.parse_args()

    html = fetch_html(args.url)
    services = parse_services(args.url, html)

    output_path = args.output or _default_output_path(args.url)
    write_csv(services, output_path)

    print(f"Extracted {len(services)} services")
    print(f"Saved CSV to: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
