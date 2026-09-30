# yusepp.github.io

Personal research homepage. All content lives in `info/*.json`. `scripts/build.py` renders it into static HTML in `_site/`, and GitHub Actions deploys that to Pages.

## Edit content

| File | What |
| --- | --- |
| `info/personal_info.json` | Name, `tagline` (also used for search/link previews), bio, emails, research topics, CV |
| `info/rrss.json` | GitHub / Scholar / LinkedIn / X links |
| `info/news.json` | News items, newest first. Add `"expires": "YYYY-MM-DD"` to hide one automatically |
| `info/publications.json` | Papers, synced monthly from OpenAlex + Semantic Scholar (manual edits are kept) |
| `info/pub_extras.json` | Per-paper extras matched by title: `tldr`, `venueShort`, `image`, `project`, `code`, `bibtex` |
| `info/activities.json` | `talks`, `projects`, `teaching`, `awards`, `service` (empty lists are hidden) |
| `info/misc.json` | Footer note, `goatcounterCode` |

For paper figures, drop a PNG in `assets/papers/` plus a `.webp` next to it (it's used automatically when present). Figures open full-size when clicked.

The build warns about news older than 18 months, and generates the 1200×630 link-preview image (`assets/og.png`) from your name, title and avatar.

### Examples

```json
"talks": [
    { "label": "2026.05", "title": "Auditing vision models with agents", "event": "Some Workshop", "url": "https://..." }
],
"projects": [
    { "name": "openmaia", "description": "Open-source interpretability agent", "url": "https://github.com/..." }
]
```

## Visitor stats (optional)

Sign up at [goatcounter.com](https://www.goatcounter.com) (free, no cookies). Then put your site code (the `CODE` in `CODE.goatcounter.com`) in `info/misc.json` → `"goatcounterCode"`. Leave it empty to turn stats off.

## Preview locally

```bash
pip install -r requirements.txt
python scripts/build.py
python -m http.server -d _site
```

## Automation

- **Deploy:** pushing to `master` runs `.github/workflows/deploy.yml` (Settings → Pages → Source = GitHub Actions).
- **Monthly:** `.github/workflows/update-publications.yml` merges new papers/links from OpenAlex and Semantic Scholar, redeploys if anything changed, and posts a dead-link report (lychee) in the run summary.

Fonts are self-hosted from Google Fonts' open-source repo (SIL OFL, licenses in `assets/fonts/`).
