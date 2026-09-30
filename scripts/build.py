"""
Render the static site from the JSON files in info/ into _site/.

    pip install -r requirements.txt
    python scripts/build.py
    python -m http.server -d _site
"""

import json
import re
import shutil
import unicodedata
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

try:
    from PIL import Image
except ImportError:  # image sizes are optional (only used to avoid layout shift)
    Image = None

ROOT = Path(__file__).resolve().parent.parent
INFO = ROOT / "info"
OUT = ROOT / "_site"
SITE_URL = "https://yusepp.github.io/"

# Variants of *your* author name to highlight
MY_AUTHOR_NAMES = [
    "Josep Lopez Camuñas",
    "Josep López Camuñas",
    "Josep Lopez Camunas",
    "Josep López Camunas",
]

# Files/folders copied verbatim into _site/
STATIC = ["style.css", "site.js", "assets"]


# -------- Helpers --------


def load(name, default=None):
    path = INFO / name
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def title_key(title):
    """Normalized title used to match publications.json with pub_extras.json."""
    t = unicodedata.normalize("NFKD", title or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


def is_me(author):
    a = title_key(author)
    return any(title_key(n) == a for n in MY_AUTHOR_NAMES)


def split_authors(author_str):
    """'A and B and C' (BibTeX style) -> [{'name': 'A', 'me': False}, ...]"""
    parts = [p.strip() for p in re.split(r"\s+and\s+", author_str or "", flags=re.I)]
    return [{"name": p, "me": is_me(p)} for p in parts if p]


def image_size(rel_path):
    if not Image or not rel_path:
        return None, None
    try:
        with Image.open(ROOT / rel_path) as im:
            return im.size
    except OSError:
        return None, None


def webp_variant(rel_path):
    """Return the .webp sibling of an image if one exists."""
    if not rel_path:
        return ""
    webp = Path(rel_path).with_suffix(".webp")
    return webp.as_posix() if (ROOT / webp).exists() and webp.as_posix() != rel_path else ""


def make_bibtex(pub):
    authors = pub["authorList"]
    first = authors[0]["name"].split()[-1] if authors else "anon"
    first_word = next((w for w in title_key(pub["title"]).split() if len(w) > 3), "paper")
    key = title_key(first).replace(" ", "") + str(pub.get("year") or "") + first_word
    venue = pub.get("venue", "")
    field = "journal" if re.search(r"arxiv|journal|transactions", venue, re.I) else "booktitle"
    kind = "article" if field == "journal" else "inproceedings"
    lines = [
        f"@{kind}{{{key},",
        f"  title = {{{pub['title']}}},",
        f"  author = {{{' and '.join(a['name'] for a in authors)}}},",
    ]
    if venue:
        lines.append(f"  {field} = {{{venue}}},")
    if pub.get("year"):
        lines.append(f"  year = {{{pub['year']}}},")
    lines.append("}")
    return "\n".join(lines)


def obfuscate_email(email):
    if not email or "@" not in email:
        return None
    user, domain = email.split("@", 1)
    return {"user": user, "domain": domain}


# -------- Publications --------


def build_publications():
    pubs = load("publications.json", []) or []
    extras = {title_key(e["title"]): e for e in (load("pub_extras.json", {}) or {}).get("extras", []) if e.get("title")}

    out = []
    for pub in pubs:
        extra = extras.get(title_key(pub.get("title")), {})
        links = pub.get("links") or {}
        p = dict(pub)
        p["authorList"] = split_authors(pub.get("authors"))
        p["venueShort"] = extra.get("venueShort", "")
        image = extra.get("image", "")
        p["image"] = image
        p["imageWebp"] = webp_variant(image)
        p["imageWidth"], p["imageHeight"] = image_size(image)
        # Chips, in display order: Project / Code / PDF / DOI / Paper
        chips = [
            ("Project", extra.get("project")),
            ("Code", extra.get("code") or links.get("code")),
            ("PDF", links.get("pdf")),
            ("DOI", links.get("doi")),
            ("Paper", links.get("scholar")),
        ]
        p["chips"] = [{"label": l, "url": u} for l, u in chips if u]
        # Title link: prefer Project -> PDF -> Paper -> Code -> DOI
        by_label = {c["label"]: c["url"] for c in p["chips"]}
        p["primaryUrl"] = next(
            (by_label[l] for l in ("Project", "PDF", "Paper", "Code", "DOI") if l in by_label), ""
        )
        p["bibtex"] = extra.get("bibtex") or make_bibtex(p)
        out.append(p)

    out.sort(key=lambda p: p.get("year") or 0, reverse=True)

    groups = []
    for p in out:
        label = str(p.get("year") or "Other")
        if not groups or groups[-1]["year"] != label:
            groups.append({"year": label, "pubs": []})
        groups[-1]["pubs"].append(p)
    return out, groups


# -------- Structured data --------


def json_ld(info, rrss, pubs):
    same_as = [
        u
        for u in [
            f"https://github.com/{rrss['github']}" if rrss.get("github") else None,
            rrss.get("scholarUrl"),
            rrss.get("linkedinUrl"),
            rrss.get("twitterUrl"),
        ]
        if u
    ]
    person = {
        "@type": "Person",
        "@id": SITE_URL + "#me",
        "name": info.get("name"),
        "jobTitle": info.get("title"),
        "url": SITE_URL,
        "image": SITE_URL + info["avatarUrl"] if info.get("avatarUrl") else None,
        "affiliation": {"@type": "CollegeOrUniversity", "name": info.get("affiliation")},
        "knowsAbout": info.get("researchTopics", []),
        "sameAs": same_as,
    }
    articles = [
        {
            "@type": "ScholarlyArticle",
            "headline": p["title"],
            "author": [{"@type": "Person", "name": a["name"]} for a in p["authorList"]],
            "datePublished": str(p["year"]) if p.get("year") else None,
            "isPartOf": p.get("venue") or None,
            "url": p.get("primaryUrl") or None,
            "abstract": p.get("summary") or None,
        }
        for p in pubs
    ]

    def clean(obj):
        if isinstance(obj, dict):
            return {k: clean(v) for k, v in obj.items() if v not in (None, "", [])}
        if isinstance(obj, list):
            return [clean(v) for v in obj]
        return obj

    graph = {"@context": "https://schema.org", "@graph": clean([person] + articles)}
    # Escape "</" so the JSON can never close the <script> tag early
    return Markup(json.dumps(graph, ensure_ascii=False, indent=2).replace("</", "<\\/"))


# -------- Main --------


def main():
    info = load("personal_info.json", {})
    rrss = load("rrss.json", {})
    news = (load("news.json", {}) or {}).get("news", [])
    activities = load("activities.json", {})
    misc = load("misc.json", {})
    pubs, pub_groups = build_publications()

    social = []
    if rrss.get("github"):
        social.append({"label": "GitHub", "url": "https://github.com/" + rrss["github"]})
    for key, label in [("scholarUrl", "Scholar"), ("linkedinUrl", "LinkedIn"), ("twitterUrl", "Twitter/X")]:
        if rrss.get(key):
            social.append({"label": label, "url": rrss[key]})

    twitter_handle = ""
    if rrss.get("twitterUrl"):
        twitter_handle = "@" + rrss["twitterUrl"].rstrip("/").rsplit("/", 1)[-1]

    affiliation = info.get("affiliation", "")
    if info.get("affiliation2"):
        affiliation += ", " + info["affiliation2"]

    avatar = info.get("avatarUrl", "")
    avatar_w, avatar_h = image_size(avatar)

    ctx = {
        "site_url": SITE_URL,
        "info": info,
        "affiliation": affiliation,
        "about": [Markup(p) for p in info.get("aboutParagraphs", [])],  # trusted HTML
        "description": " ".join(
            filter(None, [info.get("title"), "at", info.get("affiliation")])
        ),
        "avatar": avatar,
        "avatar_webp": webp_variant(avatar),
        "avatar_w": avatar_w,
        "avatar_h": avatar_h,
        "emails": [e for e in (obfuscate_email(info.get("primaryEmail")), obfuscate_email(info.get("secondaryEmail"))) if e],
        "social": social,
        "twitter_handle": twitter_handle,
        "news": news,
        "teaching": activities.get("teaching", []),
        "awards": activities.get("awards", []),
        "service": activities.get("service", []),
        "footer_note": misc.get("footerNote", "Hosted on GitHub Pages"),
        "pub_groups": pub_groups,
        "json_ld": json_ld(info, rrss, pubs),
        "year": date.today().year,
        "today": date.today().isoformat(),
    }

    env = Environment(
        loader=FileSystemLoader(ROOT / "templates"),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()

    for name, out_name in [
        ("index.html.j2", "index.html"),
        ("404.html.j2", "404.html"),
        ("sitemap.xml.j2", "sitemap.xml"),
    ]:
        (OUT / out_name).write_text(env.get_template(name).render(**ctx), encoding="utf-8")

    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}sitemap.xml\n", encoding="utf-8")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")

    for item in STATIC:
        src = ROOT / item
        if src.is_dir():
            shutil.copytree(src, OUT / item, ignore=shutil.ignore_patterns("*:Zone.Identifier"))
        elif src.exists():
            shutil.copy2(src, OUT / item)

    print(f"Built {OUT.relative_to(ROOT)}/ ({len(pubs)} publications, {len(news)} news items)")


if __name__ == "__main__":
    main()
