import json
from pathlib import Path

from scholarly import scholarly  # pip install scholarly

# Replace with your Scholar user id (the 'user=XXXX' part of your profile URL)
SCHOLAR_USER_ID = "cHzwkWMAAAAJ"
MAX_PAPERS = 40  # adjust as you like

# Papers you always want to skip (case-insensitive, checked in title + venue)
SKIP_PATTERNS = [
    "wacvw 2025",
    "predictive maintenance using deep learning",
]


def should_skip_paper(title: str, venue: str) -> bool:
    """
    Returns True if this paper should be excluded based on its title/venue.
    """
    text = f"{title} {venue}".lower()
    return any(pattern in text for pattern in SKIP_PATTERNS)


def fetch_publications(user_id: str, max_papers: int = 40):
    author = scholarly.search_author_id(user_id)
    author = scholarly.fill(author, sections=["publications"])

    pubs_out = []

    for pub_ref in author.get("publications", [])[:max_papers]:
        pub = scholarly.fill(pub_ref)

        bib = pub.get("bib", {})
        title = bib.get("title", "").strip()
        authors = bib.get("author", "")  # often "Last, F.; Last, F."
        venue = (
            bib.get("venue", "")
            or bib.get("journal", "")
            or bib.get("conference", "")
            or ""
        )
        year = bib.get("pub_year") or bib.get("year")
        try:
            year = int(year) if year else None
        except Exception:
            year = None

        # ---- Skip unwanted papers ----
        if should_skip_paper(title, venue):
            print(f"Skipping blacklisted publication: {title} ({venue})")
            continue

        # Try to find an accessible URL
        pdf_url = pub.get("eprint_url") or ""
        scholar_url = pub.get("pub_url") or ""

        pubs_out.append(
            {
                "title": title,
                "authors": authors,
                "venue": venue,
                "year": year,
                "summary": (bib.get("abstract", "") or "")[:350],
                "links": {
                    "pdf": pdf_url,
                    "doi": "",  # you can enrich this manually later
                    "code": "",  # optional: match by title to GitHub repos
                    "scholar": scholar_url,
                },
            }
        )

    return pubs_out


def main():
    pubs = fetch_publications(SCHOLAR_USER_ID, MAX_PAPERS)

    out_path = Path("publications.json")
    out_path.write_text(
        json.dumps(pubs, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Written {len(pubs)} publications to {out_path}")


if __name__ == "__main__":
    main()
