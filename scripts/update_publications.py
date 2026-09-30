"""
Pull publications from Google Scholar and MERGE them into info/publications.json.

Existing entries are matched by normalized title and never lose data:
only empty fields are filled in, so hand-curated venues, years and links survive.
New papers are appended. If Scholar blocks the request, the file is left untouched.
"""

import json
import re
import sys
import unicodedata
from pathlib import Path

# Replace with your Scholar user id (the 'user=XXXX' part of your profile URL)
SCHOLAR_USER_ID = "cHzwkWMAAAAJ"
MAX_PAPERS = 40  # adjust as you like

OUT_PATH = Path(__file__).resolve().parent.parent / "info" / "publications.json"

# Papers you always want to skip (case-insensitive, checked in title + venue)
SKIP_PATTERNS = [
    "wacvw 2025",
    "predictive maintenance using deep learning",
]


def title_key(title):
    t = unicodedata.normalize("NFKD", title or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


def should_skip_paper(title: str, venue: str) -> bool:
    """
    Returns True if this paper should be excluded based on its title/venue.
    """
    text = f"{title} {venue}".lower()
    return any(pattern in text for pattern in SKIP_PATTERNS)


def fetch_publications(user_id: str, max_papers: int = 40):
    from scholarly import scholarly  # pip install scholarly

    author = scholarly.search_author_id(user_id)
    author = scholarly.fill(author, sections=["publications"])

    pubs_out = []

    for pub_ref in author.get("publications", [])[:max_papers]:
        pub = scholarly.fill(pub_ref)

        bib = pub.get("bib", {})
        title = bib.get("title", "").strip()
        authors = bib.get("author", "")
        venue = (
            bib.get("venue", "")
            or bib.get("journal", "")
            or bib.get("conference", "")
            or bib.get("citation", "")
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

        pubs_out.append(
            {
                "title": title,
                "authors": authors,
                "venue": venue,
                "year": year,
                "summary": (bib.get("abstract", "") or "")[:350],
                "links": {
                    "pdf": pub.get("eprint_url") or "",
                    "doi": "",  # you can enrich this manually later
                    "code": "",
                    "scholar": pub.get("pub_url") or "",
                },
            }
        )

    return pubs_out


def fill_empty(existing: dict, fresh: dict) -> bool:
    """Copy values from fresh into existing only where existing is empty. Returns True if changed."""
    changed = False
    for k, v in fresh.items():
        if isinstance(v, dict):
            sub = existing.setdefault(k, {})
            changed |= fill_empty(sub, v)
        elif v not in (None, "") and existing.get(k) in (None, ""):
            existing[k] = v
            changed = True
    return changed


def merge(existing: list, fresh: list):
    by_key = {title_key(p.get("title")): p for p in existing}
    added = updated = 0
    for pub in fresh:
        key = title_key(pub["title"])
        if not key:
            continue
        if key in by_key:
            updated += fill_empty(by_key[key], pub)
        else:
            existing.append(pub)
            by_key[key] = pub
            added += 1
    return existing, added, updated


def main():
    existing = json.loads(OUT_PATH.read_text(encoding="utf-8")) if OUT_PATH.exists() else []

    try:
        fresh = fetch_publications(SCHOLAR_USER_ID, MAX_PAPERS)
    except Exception as err:  # Scholar often rate-limits / CAPTCHAs CI runners
        print(f"Could not fetch from Google Scholar, leaving {OUT_PATH.name} unchanged: {err}")
        return 0

    merged, added, updated = merge(existing, fresh)
    OUT_PATH.write_text(
        json.dumps(merged, ensure_ascii=False, indent=4) + "\n",
        encoding="utf-8",
    )
    print(f"{OUT_PATH.name}: {added} added, {updated} updated, {len(merged)} total")
    return 0


if __name__ == "__main__":
    sys.exit(main())
