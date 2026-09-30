// Render the /peqemo media from HTML scenes.
//
//   cd scripts/media && npm install && npx playwright install chromium
//   node render.mjs                     # render everything
//   node render.mjs teaser emoloss      # only some scenes
//   node render.mjs teaser --preview 1,5,9   # just dump frames at those seconds (for checking)
//   node render.mjs --gif               # also export .gif versions of the videos (to projects/peqemo/extras/)
//
// Each scenes/<name>.html defines window.SCENE = {width, height, duration} and window.seek(t);
// window.PROJECT is injected from projects/peqemo/project.json. Videos: 30 fps -> ffmpeg H.264.

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

// scene -> output file in projects/peqemo/media
const OUTPUTS = {
    teaser: "teaser.mp4",
    ptl: "perception-trigger-label.mp4",
    emoloss: "emo-loss.mp4",
    framework: "framework.png",
    dataset: "dataset-pipeline.png",
    problem: "problem.png",
};

const args = process.argv.slice(2);
const wantGif = args.includes("--gif");
const pIdx = args.indexOf("--preview");
const previewTimes = pIdx >= 0 ? args[pIdx + 1].split(",").map(Number) : null;
const names = args.filter((a, i) => !a.startsWith("--") && !(pIdx >= 0 && i === pIdx + 1));
const scenes = names.length ? names : Object.keys(OUTPUTS);

const project = readFileSync(join(ROOT, "projects", "peqemo", "project.json"), "utf8");

function run(cmd, cmdArgs, input) {
    return new Promise((res, rej) => {
        const p = spawn(cmd, cmdArgs, { stdio: [input ? "pipe" : "ignore", "ignore", "pipe"] });
        let err = "";
        p.stderr.on("data", (d) => (err += d));
        p.on("close", (code) => (code === 0 ? res() : rej(new Error(`${cmd} exited ${code}\n${err.slice(-2000)}`))));
        if (input) input(p.stdin);
    });
}

async function openScene(browser, name, scale = 1) {
    const page = await browser.newPage({ deviceScaleFactor: scale });
    await page.addInitScript(`window.PROJECT = ${project};`);
    await page.goto(pathToFileURL(join(HERE, "scenes", `${name}.html`)).href);
    await page.evaluate(async () => {
        await document.fonts.ready;
        await Promise.all([...document.images].map((i) => i.decode().catch(() => {})));
    });
    const scene = await page.evaluate(() => window.SCENE);
    await page.setViewportSize({ width: scene.width, height: scene.height });
    await page.evaluate(() => window.setup && window.setup());
    return { page, scene };
}

async function renderVideo(browser, name) {
    const { page, scene } = await openScene(browser, name);
    const out = join(MEDIA, OUTPUTS[name]);
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
    console.log(`${OUTPUTS[name]}: ${frames} frames, ${scene.width}x${scene.height} @ ${FPS} fps`);
    if (wantGif) {
        // GIFs are for slides/READMEs only: kept out of media/ so they aren't deployed with the page
        mkdirSync(EXTRAS, { recursive: true });
        const gif = join(EXTRAS, OUTPUTS[name].replace(/\.mp4$/, ".gif"));
        await run("ffmpeg", ["-y", "-loglevel", "error", "-i", out, "-vf",
            "fps=15,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4",
            gif]);
        console.log(`  + ${gif.split(/[\\/]/).pop()}`);
    }
}

async function renderStill(browser, name) {
    const { page, scene } = await openScene(browser, name, 1.25);
    await page.evaluate((t) => window.seek(t), scene.duration || 0);
    const out = join(MEDIA, OUTPUTS[name]);
    await page.screenshot({ path: out, type: "png" });
    await page.close();
    await run("ffmpeg", ["-y", "-loglevel", "error", "-i", out, "-c:v", "libwebp", "-quality", "88", out.replace(/\.png$/, ".webp")]);
    console.log(`${OUTPUTS[name]} (+ .webp): ${Math.round(scene.width * 1.25)}x${Math.round(scene.height * 1.25)}`);
}

async function preview(browser, name, times) {
    mkdirSync(PREVIEW, { recursive: true });
    const { page } = await openScene(browser, name);
    for (const t of times) {
        await page.evaluate((x) => window.seek(x), t);
        await page.screenshot({ path: join(PREVIEW, `${name}-${String(t).replace(".", "_")}s.png`) });
    }
    await page.close();
    console.log(`preview ${name}: ${times.join(", ")} s -> ${PREVIEW}`);
}

const browser = await chromium.launch();
try {
    mkdirSync(MEDIA, { recursive: true });
    for (const name of scenes) {
        if (!OUTPUTS[name]) throw new Error(`unknown scene ${name}`);
        if (previewTimes) await preview(browser, name, previewTimes);
        else if (OUTPUTS[name].endsWith(".mp4")) await renderVideo(browser, name);
        else await renderStill(browser, name);
    }
} finally {
    await browser.close();
}
