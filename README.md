# yusepp.github.io

Personal research homepage. All content lives in `info/*.json`. `scripts/build.py` renders it into static HTML in `_site/`, and GitHub Actions deploys that to Pages.

## Edit content

| File | What |
| --- | --- |
| `info/personal_info.json` | Name, title, bio, emails, research topics, internship note, CV |
| `info/rrss.json` | GitHub / Scholar / LinkedIn / X links |
| `info/news.json` | News items (newest first) |
| `info/publications.json` | Papers (merged monthly from Google Scholar, manual edits are kept) |
| `info/pub_extras.json` | Per-paper extras matched by title: `image`, `project`, `code`, `venueShort`, `bibtex` |
| `info/activities.json` | Teaching, awards, service |

For paper figures, drop a PNG in `assets/papers/` plus a `.webp` next to it (it's used automatically when present).

## Preview locally

```bash
pip install -r requirements.txt
python scripts/build.py
python -m http.server -d _site
```

## Deploy

Pushing to `master` runs `.github/workflows/deploy.yml`.
One-time setup: **Settings → Pages → Source = GitHub Actions**.
