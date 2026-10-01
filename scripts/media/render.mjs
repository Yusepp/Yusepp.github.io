// Render the /peqemo media from HTML scenes, in a light and a dark variant.
//
//   cd scripts/media && npm install && npx playwright install chromium
//   node render.mjs                          # render everything, both themes
//   node render.mjs teaser emoloss           # only some scenes
//   node render.mjs --theme dark             # only one theme (light | dark)
//   node render.mjs teaser --preview 1,5,9   # just dump frames at those seconds (for checking)
//   node render.mjs --gif                    # also export light .gif versions (to projects/peqemo/extras/)
//
// Each scenes/<name>.html defines window.SCENE = {width, height, duration, poster?} and window.seek(t);
// window.PROJECT is injected from projects/peqemo/project.json. The dark variant is the same scene
// opened with ?theme=dark and is saved with a "-dark" suffix (teaser-dark.mp4, framework-dark.png, ...);
// the page swaps to it automatically when the visitor's theme is dark.

import { spawn } from "node:child_process";
import { mkdirSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { chromium } from "playwright";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, "..", "..");
const MEDIA = join(ROOT, "projects", "peqemo", "media");
const EXTRAS = join(ROOT, "projects", "peqemo", "extras");
const PREVIEW = join(HERE, "preview");
const FPS = 30;

// scene -> output file in projects/peqemo/media (light variant; dark adds "-dark")
const OUTPUTS = {
    teaser: "teaser.mp4",
    ptl: "perception-trigger-label.mp4",
    emoloss: "emo-loss.mp4",
    framework: "framework.png",
    dataset: "dataset-pipeline.png",
    problem: "problem.png",
};

const args = process.argv.slice(2);
const flag = (name) => {
    const i = args.indexOf(name);
    return i >= 0 ? args[i + 1] : null;
};
const wantGif = args.includes("--gif");
const previewArg = flag("--preview");
const previewTimes = previewArg ? previewArg.split(",").map(Number) : null;
const themeArg = flag("--theme");
const themes = themeArg ? [themeArg] : ["light", "dark"];
const valued = new Set(["--preview", "--theme"]);
const names = args.filter((a, i) => !a.startsWith("--") && !valued.has(args[i - 1]));
const scenes = names.length ? names : Object.keys(OUTPUTS);

const project = readFileSync(join(ROOT, "projects", "peqemo", "project.json"), "utf8");

const outFile = (name, theme) =>
    join(MEDIA, theme === "dark" ? OUTPUTS[name].replace(/(\.\w+)$/, "-dark$1") : OUTPUTS[name]);
const label = (p) => p.split(/[\\/]/).pop();

function run(cmd, cmdArgs, input) {
    return new Promise((res, rej) => {
        const p = spawn(cmd, cmdArgs, { stdio: [input ? "pipe" : "ignore", "ignore", "pipe"] });
        let err = "";
        p.stderr.on("data", (d) => (err += d));
        p.on("close", (code) => (code === 0 ? res() : rej(new Error(`${cmd} exited ${code}\n${err.slice(-2000)}`))));
        if (input) input(p.stdin);
    });
}

async function openScene(browser, name, theme, scale = 1) {
    const page = await browser.newPage({ deviceScaleFactor: scale });
    await page.addInitScript(`window.PROJECT = ${project};`);
    const url = pathToFileURL(join(HERE, "scenes", `${name}.html`)).href + (theme === "dark" ? "?theme=dark" : "");
    await page.goto(url);
    await page.evaluate(async () => {
        await document.fonts.ready;
        await Promise.all([...document.images].map((i) => i.decode().catch(() => {})));
    });
    const scene = await page.evaluate(() => window.SCENE);
    await page.setViewportSize({ width: scene.width, height: scene.height });
    await page.evaluate(() => window.setup && window.setup());
    return { page, scene };
}

async function renderVideo(browser, name, theme) {
    const { page, scene } = await openScene(browser, name, theme);
    const out = outFile(name, theme);
    const frames = Math.round(scene.duration * FPS);
    await run(
        "ffmpeg",
        ["-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", String(FPS), "-i", "-",
         "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-pix_fmt", "yuv420p",
         "-movflags", "+faststart", "-an", out],
        async (stdin) => {
            for (let f = 0; f < frames; f++) {
                await page.evaluate((t) => window.seek(t), f / FPS);
                const buf = await page.screenshot({ type: "png" });
                if (!stdin.write(buf)) await new Promise((r) => stdin.once("drain", r));
            }
            stdin.end();
        }
    );
    await page.close();
    console.log(`${label(out)}: ${frames} frames, ${scene.width}x${scene.height} @ ${FPS} fps`);
    // Poster: the frame shown before playback / when autoplay is off (reduced motion)
    const poster = out.replace(/\.mp4$/, "-poster.webp");
    await run("ffmpeg", ["-y", "-loglevel", "error", "-ss", String(scene.poster ?? scene.duration / 2), "-i", out,
        "-frames:v", "1", "-c:v", "libwebp", "-quality", "85", poster]);
    console.log(`  + ${label(poster)}`);
    if (wantGif && theme === "light") {
        // GIFs are for slides/READMEs only: kept out of media/ so they aren't deployed with the page
        mkdirSync(EXTRAS, { recursive: true });
        const gif = join(EXTRAS, OUTPUTS[name].replace(/\.mp4$/, ".gif"));
        await run("ffmpeg", ["-y", "-loglevel", "error", "-i", out, "-vf",
            "fps=15,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4",
            gif]);
        console.log(`  + ${label(gif)}`);
    }
}

async function renderStill(browser, name, theme) {
    const { page, scene } = await openScene(browser, name, theme, 1.25);
    await page.evaluate((t) => window.seek(t), scene.duration || 0);
    const out = outFile(name, theme);
    await page.screenshot({ path: out, type: "png" });
    await page.close();
    await run("ffmpeg", ["-y", "-loglevel", "error", "-i", out, "-c:v", "libwebp", "-quality", "88", out.replace(/\.png$/, ".webp")]);
    console.log(`${label(out)} (+ .webp): ${Math.round(scene.width * 1.25)}x${Math.round(scene.height * 1.25)}`);
}

async function preview(browser, name, theme, times) {
    mkdirSync(PREVIEW, { recursive: true });
    const { page } = await openScene(browser, name, theme);
    for (const t of times) {
        await page.evaluate((x) => window.seek(x), t);
        await page.screenshot({ path: join(PREVIEW, `${name}-${theme}-${String(t).replace(".", "_")}s.png`) });
    }
    await page.close();
    console.log(`preview ${name} (${theme}): ${times.join(", ")} s -> ${PREVIEW}`);
}

const browser = await chromium.launch();
try {
    mkdirSync(MEDIA, { recursive: true });
    for (const name of scenes) {
        if (!OUTPUTS[name]) throw new Error(`unknown scene ${name}`);
        for (const theme of themes) {
            if (previewTimes) await preview(browser, name, theme, previewTimes);
            else if (OUTPUTS[name].endsWith(".mp4")) await renderVideo(browser, name, theme);
            else await renderStill(browser, name, theme);
        }
    }
} finally {
    await browser.close();
}
