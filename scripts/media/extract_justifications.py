"""
Extract PeqEMO's conditioned justifications (Appendix F, pp. 31-34) into projects/peqemo/project.json.

    python scripts/media/extract_justifications.py path/to/paper.pdf          # show differences
    python scripts/media/extract_justifications.py path/to/paper.pdf --write  # update project.json

How it stays faithful:
- body text is exactly 10 pt; emotion headers are 12 pt. Everything else is ignored, which removes
  the hidden 7.5 pt injected text on p.34 and the watermark.
- fragments are assigned to the left/right column by x position (not distance to the line start),
  so words drawn as separate mid-line fragments are kept.
- lines are rebuilt by y, ordered by x; Perception/Trigger split as before.
Compares against projects/peqemo/project.json and (with --write) updates only the explorer texts.
"""
import json
import re
import sys

from pypdf import PdfReader

PDF = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "paper.pdf"
EMOTIONS = ["Amusement", "Anger", "Awe", "Contentment", "Disgust", "Excitement", "Fear", "Sadness"]
PAGES = {31: "pansies", 32: "interior", 33: "monkey", 34: "team"}
COL_SPLIT = 400  # left column x ~11, right column x ~410


def fragments(page):
    out = []

    def on_text(text, cm, tm, font, size):
        if not text.strip():
            return
        eff = round(size * (cm[0] or 1), 2)
        x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
        y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
        out.append((y, x, eff, text))

    page.extract_text(visitor_text=on_text)
    return out


def clean(s):
    s = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def split(lines):
    text_lines = [l for l in lines if l]
    width = max(len(t) for t in text_lines)
    # 1) explicit marker, 2) first short line ending a sentence, 3) sentence break nearest the middle
    joined = " ".join(text_lines)
    if "\\n" in joined:
        a, b = joined.split("\\n", 1)
        return a, b
    # Trigger paragraphs never open by describing the scene, so skip breaks followed by descriptive openers
    descriptive = re.compile(r"(The (lighting|scene|background|overall|image|composition)|In the background)")
    for i, t in enumerate(text_lines):
        if (i >= 2 and t.rstrip().endswith(".") and len(t) < 0.85 * width and i < len(text_lines) - 1
                and not descriptive.match(text_lines[i + 1])):
            return " ".join(text_lines[: i + 1]), " ".join(text_lines[i + 1:])
    for m in re.finditer(r"[a-z]\.(?=The )", joined):
        if not descriptive.match(joined[m.end():]):
            return joined[: m.end()], joined[m.end():]
    # a line that ends a sentence exactly at the line end, followed by a new non-descriptive sentence
    cands = [i for i in range(2, len(text_lines) - 2)
             if text_lines[i].rstrip().endswith(".") and re.match(r"[A-Z]", text_lines[i + 1])
             and not descriptive.match(text_lines[i + 1])]
    if cands:
        i = min(cands, key=lambda k: abs(k - len(text_lines) / 2))
        return " ".join(text_lines[: i + 1]), " ".join(text_lines[i + 1:])
    bounds = [m.end() for m in re.finditer(r"\. (?=[A-Z])", joined)]
    cut = min(bounds, key=lambda i: abs(i - len(joined) / 2))
    return joined[:cut], joined[cut:]


def extract(reader, page_no):
    frags = fragments(reader.pages[page_no - 1])
    headers = [(y, x, t.strip()) for y, x, s, t in frags if s == 12.0 and t.strip() in EMOTIONS]
    body = [(y, x, t) for y, x, s, t in frags if s == 10.0]
    result = {}
    for hy, hx, name in headers:
        left = hx < COL_SPLIT
        same_col = [h for h in headers if (h[1] < COL_SPLIT) == left]
        below = [h[0] for h in same_col if h[0] < hy - 1]
        floor = max(below) if below else -1e9
        mine = [(y, x, t) for y, x, t in body if (x < COL_SPLIT) == left and floor < y < hy]
        rows = {}
        for y, x, t in mine:
            rows.setdefault(round(y), []).append((x, t))
        lines = ["".join(t for _, t in sorted(frs)).replace("Justification:", "").strip()
                 for _, frs in sorted(rows.items(), key=lambda kv: -kv[0])]
        p, t = split(lines)
        result[name] = {"perception": clean(p), "trigger": clean(t)}
    return result


def main():
    reader = PdfReader(PDF)
    project_path = "projects/peqemo/project.json"
    project = json.load(open(project_path, encoding="utf-8"))
    changed = 0
    for page_no, img_id in PAGES.items():
        fresh = extract(reader, page_no)
        img = next(e for e in project["explorer"] if e["id"] == img_id)
        for j in img["justifications"]:
            new = fresh[j["emotion"]]
            for part in ("perception", "trigger"):
                old = re.sub(r"\s+", " ", j[part]).strip()
                if old != new[part]:
                    changed += 1
                    # show just the differing region
                    a, b = old, new[part]
                    i = next((k for k in range(min(len(a), len(b))) if a[k] != b[k]), min(len(a), len(b)))
                    print(f"* {img_id}/{j['emotion']}/{part}:\n    OLD …{a[max(0, i - 60): i + 110]!r}\n    NEW …{b[max(0, i - 60): i + 110]!r}")
                j[part] = new[part]
    print(f"{changed} text(s) differ")
    if "--write" in sys.argv:
        json.dump(project, open(project_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        open(project_path, "a", encoding="utf-8").write("\n")
        print("project.json updated")


if __name__ == "__main__":
    main()
