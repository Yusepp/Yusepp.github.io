// Deterministic animation helpers: every scene defines window.SCENE and window.seek(t),
// and render.mjs calls seek() for each frame, so output never depends on real time.
// window.PROJECT (projects/peqemo/project.json) is injected by render.mjs.

const clamp01 = (x) => Math.max(0, Math.min(1, x));
const ease = (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);
// Progress of t through [a, b], eased, in 0..1.
const prog = (t, a, b) => ease(clamp01((t - a) / (b - a)));
const lin = (t, a, b) => clamp01((t - a) / (b - a));

function fade(el, p, dy = 16) {
    el.style.opacity = p;
    el.style.transform = `translateY(${(1 - p) * dy}px)`;
}

function pop(el, p) {
    el.style.opacity = clamp01(p * 2);
    el.style.transform = `scale(${0.85 + 0.15 * p})`;
}

// Type text proportionally to p (linear, like a typewriter); show a caret while typing.
function type(el, text, p) {
    const n = Math.round(text.length * clamp01(p));
    el.textContent = text.slice(0, n);
    if (p > 0 && p < 1) {
        const c = document.createElement("span");
        c.className = "caret";
        el.appendChild(c);
    }
}

// First n sentences of a text (verbatim), with an ellipsis if something was cut.
function sentences(text, n) {
    text = text.replace(/\s+/g, " ").trim();
    const parts = text.match(/[^.!?]+[.!?]+(\s|$)/g) || [text];
    const out = parts.slice(0, n).join("").trim();
    return parts.length > n ? out + " …" : out;
}

function explorerItem(imageId) {
    return window.PROJECT.explorer.find((e) => e.id === imageId);
}

function justification(imageId, emotion) {
    return explorerItem(imageId).justifications.find((j) => j.emotion === emotion);
}

// Place a cue box over a photo element using fractions of the photo's size.
function placeCue(el, photo, box) {
    const w = photo.offsetWidth;
    const h = photo.offsetHeight;
    el.style.left = photo.offsetLeft + box.x * w + "px";
    el.style.top = photo.offsetTop + box.y * h + "px";
    el.style.width = box.w * w + "px";
    el.style.height = box.h * h + "px";
}
