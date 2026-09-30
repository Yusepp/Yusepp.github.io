"""
Pull publications from OpenAlex, Semantic Scholar and (as a fallback) Google Scholar,
and MERGE them into info/publications.json.

1. OpenAlex + Semantic Scholar: free APIs, no key, reliable from CI.
2. arXiv: full abstracts for every paper those APIs link to an arXiv id.
3. Google Scholar (optional, needs `pip install scholarly "bibtexparser<2"`): only asked about
   papers the APIs don't know or have no complete abstract for (e.g. OpenReview-only workshop
   papers), to keep requests minimal, since Google may block scrapers.

Existing entries are matched by normalized title and never lose data:
only empty fields are filled in, so hand-curated venues, years and links survive.
New papers are appended. If every source fails, the file is left untouched.

    python scripts/update_publications.py
"""

import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

# Author ids: https://openalex.org/authors?search=... and https://www.semanticscholar.org/search?q=...
OPENALEX_AUTHOR_ID = "A5116077900"
SEMANTIC_SCHOLAR_AUTHOR_ID = "2342502730"
GOOGLE_SCHOLAR_USER_ID = "cHzwkWMAAAAJ"  # the 'user=XXXX' part of your Scholar profile URL
CONTACT_EMAIL = "jlopezcamu@uoc.edu"  # OpenAlex "polite pool" (faster, more reliable)

OUT_PATH = Path(__file__).resolve().parent.parent / "info" / "publications.json"

# Papers you always want to skip (case-insensitive, checked in title + venue)
SKIP_PATTERNS = [
    "predictive maintenance using deep learning",
]


def title_key(title):
    t = unicodedata.normalize("NFKD", title or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


def abstract_complete(text):
    """False for missing abstracts and ones cut off mid-sentence."""
    return bool(text) and text.rstrip().endswith((".", "!", "?"))


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


def fetch_arxiv(arxiv_ids):
    """Full abstracts straight from arXiv for every paper the other APIs linked to an arXiv id."""
    ids = sorted({i for i in arxiv_ids if i})
    if not ids:
        return []
    xml = urllib.request.urlopen(
        urllib.request.Request(
            "http://export.arxiv.org/api/query?max_results=100&id_list=" + ",".join(ids),
            headers={"User-Agent": f"yusepp.github.io publication sync ({CONTACT_EMAIL})"},
        ),
        timeout=30,
    ).read()
    ns = {"a": "http://www.w3.org/2005/Atom"}
    out = []
    for entry in ET.fromstring(xml).findall("a:entry", ns):
        clean = lambda s: re.sub(r"\s+", " ", s or "").strip()
        p = empty_pub(clean(entry.findtext("a:title", "", ns)))
        p["authors"] = " and ".join(clean(a.findtext("a:name", "", ns)) for a in entry.findall("a:author", ns))
        p["summary"] = clean(entry.findtext("a:summary", "", ns))
        m = re.search(r"abs/(\d{4}\.\d{4,5})", entry.findtext("a:id", "", ns))
        if m:
            p["links"]["arxiv"] = m.group(1)
        out.append(p)
    return out


def fetch_google_scholar(needs):
    """Fallback: only fill (one request each) the Scholar entries for which needs(title) is True."""
    from scholarly import scholarly  # optional dependency, see module docstring

    author = scholarly.fill(scholarly.search_author_id(GOOGLE_SCHOLAR_USER_ID), sections=["publications"])
    out = []
    for ref in author.get("publications", []):
        if not needs(ref.get("bib", {}).get("title", "")):
            continue
        bib = scholarly.fill(ref).get("bib", {})
        p = empty_pub((bib.get("title") or "").strip())
        p["authors"] = bib.get("author", "")
        p["venue"] = bib.get("venue") or bib.get("journal") or bib.get("conference") or ""
        try:
            p["year"] = int(bib.get("pub_year") or 0) or None
        except ValueError:
            pass
        p["summary"] = bib.get("abstract", "")
        p["links"]["pdf"] = ref.get("eprint_url") or ""
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
            # A longer complete abstract replaces a shorter one (the old Scholar scraper cut them at 350 chars)
            old = (cur.get("summary") or "").strip()
            new = (pub.get("summary") or "").strip()
            if old and abstract_complete(new) and len(new) > len(old):
                cur["summary"] = new
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

    # arXiv: full abstracts for any paper linked to an arXiv id (ids may already be full URLs in the file)
    arxiv_ids = [
        re.sub(r".*/abs/", "", (p.get("links") or {}).get("arxiv") or "")
        for p in existing + [p for pubs in sources for p in pubs]
    ]
    try:
        pubs = fetch_arxiv(arxiv_ids)
        print(f"arXiv: {len(pubs)} works")
        sources.append(pubs)
    except Exception as err:
        print(f"arXiv: failed ({err}), continuing without it")

    # Google Scholar fallback: one request for the paper list, then one per paper that is
    # unknown to the APIs or still lacks a complete abstract
    complete = set()
    for p in existing + [p for pubs in sources for p in pubs]:
        if abstract_complete(p.get("summary")):
            complete.add(title_key(p.get("title")))
    try:
        pubs = fetch_google_scholar(lambda title: title_key(title) not in complete)
        print(f"Google Scholar: {len(pubs)} works filled in")
        sources.append(pubs)
    except ImportError:
        print('Google Scholar: skipped (pip install scholarly "bibtexparser<2" to enable)')
    except Exception as err:
        print(f"Google Scholar: failed ({err}), continuing without it")

    if not sources:
        print(f"No source available, leaving {OUT_PATH.name} unchanged")
        return 0

    merged, added, updated = merge(existing, combine(sources))
    OUT_PATH.write_text(json.dumps(merged, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    print(f"{OUT_PATH.name}: {added} added, {updated} updated, {len(merged)} total")
    return 0


if __name__ == "__main__":
    sys.exit(main())
