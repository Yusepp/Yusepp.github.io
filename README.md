# yusepp.github.io

Personal research homepage. All content lives in `info/*.json`. `scripts/build.py` renders it into static HTML in `_site/`, and GitHub Actions deploys that to Pages.

## Edit content

| File | What |
| --- | --- |
| `info/personal_info.json` | Name, `tagline` (also used for search/link previews), bio, emails, research topics, CV |
| `info/rrss.json` | GitHub / Scholar / LinkedIn / X links |
| `info/news.json` | News items, newest first. Add `"expires": "YYYY-MM-DD"` to hide one automatically |
| `info/publications.json` | Papers, synced monthly from OpenAlex + Semantic Scholar + arXiv, with Google Scholar as a fallback (manual edits are kept) |
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

## Project pages (`yusepp.github.io/<slug>`)

Every folder `projects/<slug>/` with a `project.json` becomes a standalone paper page at `/<slug>/` (e.g. [`/peqemo`](https://yusepp.github.io/peqemo/)), rendered by `templates/project.html.j2` with `project.css` / `project.js`.

- **Text:** everything lives in `project.json`: `title`, `authors`, `venue`, `links` (an empty `url` shows the button as "soon"), `tldr`, `sections` (each with plain-language `blocks` plus an optional "Go deeper" `deeper` part), the `explorer` data and the `bibtex`.
- **Media:** each figure, GIF or video is a slot in `project.json` → `media` (`file`, `kind`, `aspect`, `caption`, `todo`). If `projects/<slug>/media/<file>` exists it's shown; otherwise the page shows a placeholder with the file name and what should go there. The build lists every empty slot:
  ```
  WARNING: peqemo: 15 media placeholders still empty: teaser.mp4, problem.png, ...
  ```
  To fill one, drop the file into `projects/<slug>/media/` with that exact name and rebuild. For images you can also add a `.webp` with the same name. Keep videos short and small (MP4/H.264, muted loop).
- **Block types** for `sections[].blocks`: `p`, `list`, `media`, `cards`, `stats`, `bars`, `table`, `code`, `cases`, `html`, `explorer`.
- **New project:** copy `projects/peqemo/` to `projects/<new-slug>/`, edit `project.json`, rebuild.

### Re-rendering the PeqEMO media

The photos and animations in `projects/peqemo/media/` are generated from the paper, so they can be re-made after edits:

```bash
# photos embedded in the paper (explorer images, Fig. 4/5 cases), as .jpg + .webp
python scripts/media/extract_photos.py path/to/paper.pdf

# animations + diagrams: HTML scenes in scripts/media/scenes/ -> MP4 (1080p30, H.264) / PNG + WebP
cd scripts/media
npm install && npx playwright install chromium    # once
node render.mjs                                    # everything (add --gif for slide-friendly GIFs in projects/peqemo/extras/)
node render.mjs teaser --preview 3,9,15            # dump a few frames to scripts/media/preview/ to check a scene
```

Each scene reads the real justifications from `project.json`, so text shown in videos is always the model's verbatim output. Cue boxes on photos are placed by hand in each scene file (fractions of the photo size).

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
- **Monthly:** `.github/workflows/update-publications.yml` merges new papers/links from OpenAlex and Semantic Scholar, full abstracts from arXiv, and anything still missing (e.g. OpenReview-only papers) from Google Scholar, then redeploys if anything changed, and posts a dead-link report (lychee) in the run summary.

Fonts are self-hosted from Google Fonts' open-source repo (SIL OFL, licenses in `assets/fonts/`).
