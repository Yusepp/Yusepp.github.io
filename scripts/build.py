"""
Render the static site from the JSON files in info/ into _site/.

    pip install -r requirements.txt
    python scripts/build.py
    python -m http.server -d _site
"""

import hashlib
import json
import re
import shutil
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # image sizes and the preview image are skipped without Pillow
    Image = None

ROOT = Path(__file__).resolve().parent.parent
INFO = ROOT / "info"
OUT = ROOT / "_site"
FONTS = ROOT / "scripts" / "fonts"  # TTFs used to draw the link-preview image
SITE_URL = "https://yusepp.github.io/"

# Spellings of your name that appear in author lists; all are shown as info.name
MY_AUTHOR_NAMES = [
    "Josep Lopez Camuñas",
    "Josep López Camuñas",
    "Josep Lopez Camunas",
    "Josep López Camunas",
]

# News older than this gets a build warning (set "expires" on an item to hide it automatically)
NEWS_STALE_MONTHS = 18

# Files/folders copied verbatim into _site/
STATIC = ["style.css", "site.js", "project.css", "project.js", "assets"]

warnings = []


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


def split_authors(author_str, my_name):
    """'A and B and C' (BibTeX style) -> [{'name': 'A', 'me': False}, ...], with your name normalized."""
    parts = [p.strip() for p in re.split(r"\s+and\s+", author_str or "", flags=re.I)]
    return [{"name": my_name if is_me(p) else p, "me": is_me(p)} for p in parts if p]


def trim_to_sentence(text):
    """Drop a trailing partial sentence left by truncated abstracts."""
    text = (text or "").strip()
    if not text or text.endswith((".", "!", "?")):
        return text
    cut = max(text.rfind(". "), text.rfind("? "), text.rfind("! "))
    return text[: cut + 1] if cut > 0 else ""


def asset_version(rel_path):
    """Short content hash, appended as ?v= so browsers refetch a file whenever it changes."""
    path = ROOT / rel_path
    return hashlib.sha256(path.read_bytes()).hexdigest()[:10] if path.exists() else ""


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


def link_label(url):
    host = urlparse(url).netloc.lower()
    for domain, label in [
        ("arxiv.org", "arXiv"),
        ("openreview.net", "OpenReview"),
        ("thecvf.com", "CVF"),
        ("doi.org", "DOI"),
        ("github.com", "Code"),
    ]:
        if host == domain or host.endswith("." + domain):
            return label
    return "Paper"


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
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", (pub.get("links") or {}).get("doi", ""))
    if doi:
        lines.append(f"  doi = {{{doi}}},")
    lines.append("}")
    return "\n".join(lines)


def obfuscate_email(email):
    if not email or "@" not in email:
        return None
    user, domain = email.split("@", 1)
    return {"user": user, "domain": domain}


# -------- Publications --------


def build_publications(my_name):
    pubs = load("publications.json", []) or []
    extras = {title_key(e["title"]): e for e in (load("pub_extras.json", {}) or {}).get("extras", []) if e.get("title")}

    out = []
    for pub in pubs:
        extra = extras.get(title_key(pub.get("title")), {})
        links = pub.get("links") or {}
        p = dict(pub)
        p["authorList"] = split_authors(pub.get("authors"), my_name)
        p["venueShort"] = extra.get("venueShort", "")
        p["tldr"] = extra.get("tldr", "")
        p["summary"] = trim_to_sentence(pub.get("summary"))
        image = extra.get("image", "")
        p["image"] = image
        p["imageWebp"] = webp_variant(image)
        p["imageWidth"], p["imageHeight"] = image_size(image)

        # Chips in display order; each labelled by where it goes, duplicates dropped
        candidates = [
            ("Project", extra.get("project")),
            ("Code", extra.get("code") or links.get("code")),
            (None, links.get("arxiv")),
            ("PDF", links.get("pdf")),
            (None, links.get("scholar")),  # venue / landing page
            ("DOI", links.get("doi")),
        ]
        chips, seen = [], set()
        for label, url in candidates:
            if not url or url in seen:
                continue
            seen.add(url)
            chips.append({"label": label or link_label(url), "url": url})
        p["chips"] = chips

        # Title link: Project -> arXiv -> venue page -> PDF -> DOI -> Code
        by_label = {}
        for c in chips:
            by_label.setdefault(c["label"], c["url"])
        p["primaryUrl"] = next(
            (by_label[l] for l in ("Project", "arXiv", "OpenReview", "CVF", "Paper", "PDF", "DOI", "Code") if l in by_label),
            "",
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


# -------- News --------


def build_news(items, today):
    """Hide expired items; warn about expired or very old ones so the page doesn't go stale."""
    out = []
    for item in items:
        expires = item.get("expires")
        if expires and date.fromisoformat(expires) < today:
            warnings.append(f"news: hiding expired item [{item.get('label')}] {item.get('text', '')[:60]}")
            continue
        m = re.match(r"(\d{4})\.(\d{1,2})", item.get("label", ""))
        if m:
            age = (today.year - int(m.group(1))) * 12 + today.month - int(m.group(2))
            if age > NEWS_STALE_MONTHS:
                warnings.append(f"news: [{item['label']}] is {age} months old, consider removing it")
        out.append(item)
    return out


# -------- Link-preview image --------


def make_og_image(info, avatar, out_path):
    """Draw a 1200x630 preview card in the site's retro-window style."""
    if not Image:
        warnings.append("Pillow not installed: skipping the link-preview image")
        return False

    W, H = 1200, 630
    ink, muted, accent = (17, 24, 39), (75, 85, 99), (0, 94, 255)
    img = Image.new("RGB", (W, H), (238, 242, 255))
    d = ImageDraw.Draw(img)

    for x in range(0, W, 24):  # grid background
        d.line([(x, 0), (x, H)], fill=(226, 230, 244))
    for y in range(0, H, 24):
        d.line([(0, y), (W, y)], fill=(226, 230, 244))

    # Card with hard offset shadow
    x0, y0, x1, y1 = 56, 56, W - 64, H - 64
    d.rounded_rectangle([x0 + 10, y0 + 10, x1 + 10, y1 + 10], 10, fill=(60, 66, 84))
    d.rounded_rectangle([x0, y0, x1, y1], 10, fill=(253, 253, 253), outline=ink, width=4)

    # Avatar in a framed box
    size = 330
    ax, ay = x0 + 48, y0 + (y1 - y0 - size) // 2
    d.rectangle([ax - 12, ay - 12, ax + size + 12, ay + size + 12], fill=(229, 231, 235), outline=ink, width=4)
    if avatar and (ROOT / avatar).exists():
        with Image.open(ROOT / avatar) as a:
            img.paste(a.convert("RGB").resize((size, size), Image.LANCZOS), (ax, ay))

    pixel = lambda s: ImageFont.truetype(str(FONTS / "PressStart2P-Regular.ttf"), s)
    mono = lambda s, w="Regular": ImageFont.truetype(str(FONTS / f"IBMPlexMono-{w}.ttf"), s)

    tx = ax + size + 60
    max_w = x1 - tx - 40

    def wrap(text, font):
        lines, line = [], ""
        for word in text.split():
            test = (line + " " + word).strip()
            if d.textlength(test, font=font) <= max_w or not line:
                line = test
            else:
                lines.append(line)
                line = word
        return lines + ([line] if line else [])

    y = y0 + 70
    f = pixel(38)
    for line in wrap(info.get("name", ""), f):
        d.text((tx, y), line, font=f, fill=ink)
        y += 58
    y += 18
    f = mono(28, "SemiBold")
    for line in wrap(info.get("title", ""), f):
        d.text((tx, y), line, font=f, fill=ink)
        y += 38
    y += 14
    f = mono(24)
    for line in wrap(info.get("affiliation", ""), f):
        d.text((tx, y), line, font=f, fill=muted)
        y += 34

    d.text((tx, y1 - 70), urlparse(SITE_URL).netloc, font=pixel(20), fill=accent)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, optimize=True)
    return True


# -------- Project pages (projects/<slug>/ -> _site/<slug>/) --------


def make_project_og_image(project, out_path):
    """1200x630 preview card in the clean academic style of project pages."""
    if not Image:
        return False
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    sans = lambda s, w=400: ImageFont.truetype(str(FONTS / f"NotoSans-{w}.ttf"), s)
    d.rectangle([0, 0, W, 14], fill=(54, 54, 54))

    def wrap(text, font, max_w):
        lines, line = [], ""
        for word in text.split():
            test = (line + " " + word).strip()
            if d.textlength(test, font=font) <= max_w or not line:
                line = test
            else:
                lines.append(line)
                line = word
        return lines + ([line] if line else [])

    y = 90
    d.text((80, y), project.get("short", ""), font=sans(96, 700), fill=(54, 54, 54))
    y += 140
    f = sans(38, 700)
    for line in wrap(project.get("title", ""), f, W - 160)[:3]:
        d.text((80, y), line, font=f, fill=(74, 74, 74))
        y += 54
    y += 20
    f = sans(28)
    for line in wrap(project.get("venue", ""), f, W - 160)[:1]:
        d.text((80, y), line, font=f, fill=(122, 122, 122))
    d.text((80, H - 80), f"{urlparse(SITE_URL).netloc}/{project['slug']}", font=sans(26, 700), fill=(50, 115, 220))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, optimize=True)
    return True


def build_projects(env, today):
    """Render every projects/<slug>/project.json as a standalone page at /<slug>/.
    Media slots whose file is missing from projects/<slug>/media/ render as placeholders."""
    slugs = []
    for pj in sorted((ROOT / "projects").glob("*/project.json")):
        src = pj.parent
        project = json.loads(pj.read_text(encoding="utf-8"))
        slug = project.setdefault("slug", src.name)
        out = OUT / slug

        media_dir = src / "media"
        missing = []
        for mid, slot in project.get("media", {}).items():
            path = media_dir / slot["file"]
            slot["exists"] = path.exists()
            slot["src"] = f"media/{slot['file']}"
            webp = path.with_suffix(".webp")
            slot["webp"] = f"media/{webp.name}" if slot["kind"] == "image" and webp.exists() else ""
            poster = path.with_name(path.stem + "-poster.webp")  # still frame shown before/while paused
            slot["poster"] = f"media/{poster.name}" if slot["kind"] == "video" and poster.exists() else ""
            if not slot["exists"]:
                missing.append(slot["file"])
        if missing:
            warnings.append(f"{slug}: {len(missing)} media placeholders still empty: {', '.join(missing)}")

        out.mkdir(parents=True, exist_ok=True)
        if media_dir.exists():
            shutil.copytree(media_dir, out / "media", dirs_exist_ok=True, ignore=shutil.ignore_patterns(".gitkeep"))
        og = make_project_og_image(project, out / "og.png")

        html = env.get_template("project.html.j2").render(
            p=project,
            site_url=SITE_URL,
            page_url=f"{SITE_URL}{slug}/",
            og_image=f"{SITE_URL}{slug}/og.png" if og else "",
            css_v=asset_version("project.css"),
            js_v=asset_version("project.js"),
            today=today.isoformat(),
            year=today.year,
        )
        (out / "index.html").write_text(html, encoding="utf-8")
        slugs.append(slug)
    return slugs


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
        "alternateName": [n for n in MY_AUTHOR_NAMES if n != info.get("name")],
        "description": info.get("tagline"),
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
            "sameAs": (p.get("links") or {}).get("doi") or None,
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
    today = date.today()
    info = load("personal_info.json", {})
    rrss = load("rrss.json", {})
    news = build_news((load("news.json", {}) or {}).get("news", []), today)
    activities = load("activities.json", {})
    misc = load("misc.json", {})
    pubs, pub_groups = build_publications(info.get("name", ""))

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

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()

    og_image = "assets/og.png" if make_og_image(info, avatar, OUT / "assets" / "og.png") else ""

    ctx = {
        "site_url": SITE_URL,
        "css_v": asset_version("style.css"),
        "js_v": asset_version("site.js"),
        "cv_v": asset_version(info["cvUrl"]) if info.get("cvUrl") else "",  # new CV -> new URL, no stale cache
        "info": info,
        "affiliation": affiliation,
        "tagline": info.get("tagline", ""),
        "about": [Markup(p) for p in info.get("aboutParagraphs", [])],  # trusted HTML
        "description": info.get("tagline")
        or " ".join(filter(None, [info.get("title"), "at", info.get("affiliation")])),
        "avatar": avatar,
        "avatar_webp": webp_variant(avatar),
        "avatar_w": avatar_w,
        "avatar_h": avatar_h,
        "og_image": og_image,
        "emails": [e for e in (obfuscate_email(info.get("primaryEmail")), obfuscate_email(info.get("secondaryEmail"))) if e],
        "social": social,
        "twitter_handle": twitter_handle,
        "news": news,
        "teaching": activities.get("teaching", []),
        "awards": activities.get("awards", []),
        "service": activities.get("service", []),
        "talks": activities.get("talks", []),
        "projects": activities.get("projects", []),
        "footer_note": misc.get("footerNote", "Hosted on GitHub Pages"),
        "goatcounter": misc.get("goatcounterCode", ""),
        "pub_groups": pub_groups,
        "json_ld": json_ld(info, rrss, pubs),
        "year": today.year,
        "today": today.isoformat(),
    }

    env = Environment(
        loader=FileSystemLoader(ROOT / "templates"),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    ctx["projects"] = build_projects(env, today)

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
            shutil.copytree(src, OUT / item, dirs_exist_ok=True, ignore=shutil.ignore_patterns("*:Zone.Identifier"))
        elif src.exists():
            shutil.copy2(src, OUT / item)

    for w in warnings:
        print("WARNING:", w)
    print(
        f"Built {OUT.relative_to(ROOT)}/ ({len(pubs)} publications, {len(news)} news items, "
        f"project pages: {', '.join('/' + s for s in ctx['projects']) or 'none'})"
    )


if __name__ == "__main__":
    main()
