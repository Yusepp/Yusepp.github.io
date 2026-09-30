"""
Pull publications from OpenAlex and Semantic Scholar and MERGE them into info/publications.json.

Both APIs are free, need no key, and (unlike Google Scholar) don't block CI runners.
Existing entries are matched by normalized title and never lose data:
only empty fields are filled in, so hand-curated venues, years and links survive.
New papers are appended. If both sources fail, the file is left untouched.

Standard library only:  python scripts/update_publications.py
"""

import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

# Author ids: https://openalex.org/authors?search=... and https://www.semanticscholar.org/search?q=...
OPENALEX_AUTHOR_ID = "A5116077900"
SEMANTIC_SCHOLAR_AUTHOR_ID = "2342502730"
CONTACT_EMAIL = "jlopezcamu@uoc.edu"  # OpenAlex "polite pool" (faster, more reliable)

OUT_PATH = Path(__file__).resolve().parent.parent / "info" / "publications.json"

# Papers you always want to skip (case-insensitive, checked in title + venue)
SKIP_PATTERNS = [
    "predictive maintenance using deep learning",
]


def title_key(title):
    t = unicodedata.normalize("NFKD", title or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


def should_skip_paper(title: str, venue: str) -> bool:
    text = f"{title} {venue}".lower()
    return any(pattern in text for pattern in SKIP_PATTERNS)


def get_json(url, retries=4):
    req = urllib.request.Request(url, headers={"User-Agent": f"yusepp.github.io publication sync ({CONTACT_EMAIL})"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                return json.load(res)
        except urllib.error.HTTPError as err:
            # Semantic Scholar's shared unauthenticated pool often answers 429; back off and retry
            if err.code in (429, 503) and attempt < retries - 1:
                time.sleep(5 * 2**attempt)
                continue
            raise


def is_arxiv_venue(venue):
    return not venue or "arxiv" in venue.lower() or "corr" == venue.lower()


def empty_pub(title):
    return {
        "title": title,
        "authors": "",
        "venue": "",
        "year": None,
        "summary": "",
        "links": {"pdf": "", "doi": "", "arxiv": "", "code": "", "scholar": ""},
    }


# -------- Sources --------


def fetch_openalex():
    url = (
        "https://api.openalex.org/works"
        f"?filter=author.id:{OPENALEX_AUTHOR_ID}&per-page=100&mailto={CONTACT_EMAIL}"
        "&select=title,publication_year,doi,primary_location,authorships,abstract_inverted_index"
    )
    out = []
    for w in get_json(url).get("results", []):
        p = empty_pub((w.get("title") or "").strip())
        p["authors"] = " and ".join(a["author"]["display_name"] for a in w.get("authorships", []))
        p["year"] = w.get("publication_year")
        loc = w.get("primary_location") or {}
        p["venue"] = ((loc.get("source") or {}).get("display_name")) or ""
        doi = w.get("doi") or ""
        m = re.search(r"arxiv\.(\d{4}\.\d{4,5})", doi, re.I)
        if m:
            p["links"]["arxiv"] = m.group(1)
        elif doi:
            p["links"]["doi"] = doi
        if loc.get("pdf_url"):
            p["links"]["pdf"] = loc["pdf_url"]
        inv = w.get("abstract_inverted_index")
        if inv:  # {word: [positions]} -> text
            words = sorted((pos, word) for word, poss in inv.items() for pos in poss)
            p["summary"] = " ".join(word for _, word in words)
        out.append(p)
    return out


def fetch_semantic_scholar():
    url = (
        f"https://api.semanticscholar.org/graph/v1/author/{SEMANTIC_SCHOLAR_AUTHOR_ID}/papers"
        "?fields=title,venue,year,externalIds,authors,abstract,openAccessPdf&limit=100"
    )
    out = []
    for w in get_json(url).get("data", []):
        p = empty_pub((w.get("title") or "").strip())
        p["authors"] = " and ".join(a["name"] for a in w.get("authors", []))
        p["year"] = w.get("year")
        p["venue"] = w.get("venue") or ""
        ids = w.get("externalIds") or {}
        if ids.get("ArXiv"):
            p["links"]["arxiv"] = ids["ArXiv"]
        doi = ids.get("DOI") or ""
        if doi and not doi.lower().startswith("10.48550/arxiv"):
            p["links"]["doi"] = "https://doi.org/" + doi
        p["summary"] = w.get("abstract") or ""
        pdf = (w.get("openAccessPdf") or {}).get("url")
        if pdf:
            p["links"]["pdf"] = pdf
        out.append(p)
    return out


# -------- Combine --------


def combine(sources):
    """Dedupe across sources (and arXiv vs published versions) by title; prefer published metadata."""
    by_key = {}
    for pubs in sources:
        for p in pubs:
            key = title_key(p["title"])
            if not key:
                continue
            cur = by_key.get(key)
            if cur is None:
                by_key[key] = p
                continue
            # Prefer a real venue over arXiv
            if is_arxiv_venue(cur["venue"]) and not is_arxiv_venue(p["venue"]):
                cur["venue"] = p["venue"]
            for field in ("authors", "year", "summary"):
                if not cur[field] and p[field]:
                    cur[field] = p[field]
            if len(p["summary"]) > len(cur["summary"]):
                cur["summary"] = p["summary"]
            for k, v in p["links"].items():
                if v and not cur["links"].get(k):
                    cur["links"][k] = v

    out = []
    for p in by_key.values():
        if should_skip_paper(p["title"], p["venue"]):
            print(f"Skipping blacklisted publication: {p['title']} ({p['venue']})")
            continue
        arxiv = p["links"]["arxiv"]
        if arxiv:
            p["links"]["arxiv"] = f"https://arxiv.org/abs/{arxiv}"
            if not p["links"]["pdf"]:
                p["links"]["pdf"] = f"https://arxiv.org/pdf/{arxiv}"
        if is_arxiv_venue(p["venue"]) and arxiv:
            p["venue"] = f"arXiv preprint arXiv:{arxiv}"
        out.append(p)
    return out


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
            cur = by_key[key]
            # Full abstracts replace ones cut off mid-sentence by the old Scholar scraper
            old = (cur.get("summary") or "").rstrip()
            if old and not old.endswith((".", "!", "?")) and len(pub.get("summary", "")) > len(old):
                cur["summary"] = pub["summary"]
                updated += 1
            updated += fill_empty(cur, pub)
        else:
            existing.append(pub)
            by_key[key] = pub
            added += 1
    return existing, added, updated


def main():
    existing = json.loads(OUT_PATH.read_text(encoding="utf-8")) if OUT_PATH.exists() else []

    sources = []
    for name, fetch in [("OpenAlex", fetch_openalex), ("Semantic Scholar", fetch_semantic_scholar)]:
        try:
            pubs = fetch()
            print(f"{name}: {len(pubs)} works")
            sources.append(pubs)
        except Exception as err:
            print(f"{name}: failed ({err}), continuing without it")

    if not sources:
        print(f"No source available, leaving {OUT_PATH.name} unchanged")
        return 0

    merged, added, updated = merge(existing, combine(sources))
    OUT_PATH.write_text(json.dumps(merged, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    print(f"{OUT_PATH.name}: {added} added, {updated} updated, {len(merged)} total")
    return 0


if __name__ == "__main__":
    sys.exit(main())
