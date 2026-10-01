// project.js — progressive enhancements for project pages (the page is fully readable without JS).

document.documentElement.classList.add("js");

// -------- Arrow-key navigation inside a tablist --------

function arrowNav(list, selector) {
    list.addEventListener("keydown", function (e) {
        const keys = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 };
        if (!(e.key in keys) && e.key !== "Home" && e.key !== "End") return;
        const items = Array.from(list.querySelectorAll(selector));
        const i = items.indexOf(document.activeElement);
        if (i < 0) return;
        e.preventDefault();
        let next = e.key === "Home" ? 0 : e.key === "End" ? items.length - 1 : (i + keys[e.key] + items.length) % items.length;
        items[next].focus();
        items[next].click();
    });
}

function selectTab(buttons, active) {
    buttons.forEach(function (b) {
        const on = b === active;
        b.setAttribute("aria-selected", String(on));
        b.tabIndex = on ? 0 : -1;
    });
}

// -------- "One image, eight emotions" explorer --------

function initExplorer(root) {
    const imageTabs = Array.from(root.querySelectorAll(".thumb"));
    const panels = Array.from(root.querySelectorAll(".explorer-panel"));

    function showImage(id) {
        panels.forEach(function (p) {
            p.hidden = p.dataset.panel !== id;
        });
        selectTab(imageTabs, imageTabs.find((t) => t.dataset.image === id));
    }

    imageTabs.forEach(function (t) {
        t.hidden = false;
        t.addEventListener("click", function () {
            showImage(t.dataset.image);
        });
    });
    arrowNav(root.querySelector(".explorer-images"), ".thumb");

    panels.forEach(function (panel) {
        const chipList = panel.querySelector(".emotion-chips");
        const chips = Array.from(chipList.querySelectorAll(".chip"));
        const texts = Array.from(panel.querySelectorAll(".justification"));
        chipList.hidden = false;

        function showEmotion(emotion) {
            texts.forEach(function (d) {
                d.open = d.dataset.justification === emotion;
            });
            selectTab(chips, chips.find((c) => c.dataset.emotion === emotion));
        }

        chips.forEach(function (c) {
            c.addEventListener("click", function () {
                showEmotion(c.dataset.emotion);
            });
        });
        arrowNav(chipList, ".chip");

        const start = chips.find((c) => c.classList.contains("is-gt")) || chips[0];
        showEmotion(start.dataset.emotion);
    });

    if (imageTabs.length) showImage(imageTabs[0].dataset.image);
}

// -------- "Show all details" toggle --------

function initDetailsToggle() {
    const btn = document.getElementById("toggle-details");
    if (!btn) return;
    const blocks = Array.from(document.querySelectorAll("details.deeper"));
    btn.hidden = false;

    function sync() {
        const allOpen = blocks.every((d) => d.open);
        btn.setAttribute("aria-pressed", String(allOpen));
        btn.textContent = allOpen ? "Hide all details" : "Show all details";
    }
    btn.addEventListener("click", function () {
        const open = !blocks.every((d) => d.open);
        blocks.forEach((d) => (d.open = open));
        sync();
    });
    blocks.forEach((d) => d.addEventListener("toggle", sync));
    sync();
}

// -------- Copy buttons --------

function initCopy() {
    if (!navigator.clipboard) return;
    document.querySelectorAll(".copy-btn").forEach(function (btn) {
        const target = document.querySelector(btn.dataset.copy);
        if (!target) return;
        btn.hidden = false;
        btn.addEventListener("click", function () {
            navigator.clipboard.writeText(target.textContent).then(
                function () {
                    btn.textContent = "Copied!";
                    setTimeout(() => (btn.textContent = "Copy"), 1500);
                },
                function () {
                    btn.textContent = "Select & copy";
                }
            );
        });
    });
}

// -------- Videos: no autoplay for visitors who prefer reduced motion --------

function initVideos() {
    if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    document.querySelectorAll("video[autoplay]").forEach(function (v) {
        v.removeAttribute("autoplay");
        v.pause();
    });
}

// -------- Theme toggle (same behaviour and storage key as the homepage's site.js) --------

function initThemeToggle() {
    const btn = document.getElementById("theme-toggle");
    if (!btn) return;
    const root = document.documentElement;
    const media = window.matchMedia("(prefers-color-scheme: dark)");

    function current() {
        return root.getAttribute("data-theme") || (media.matches ? "dark" : "light");
    }
    function sync() {
        const dark = current() === "dark";
        btn.setAttribute("aria-pressed", String(dark));
        btn.title = dark ? "Switch to light mode" : "Switch to dark mode";
    }

    btn.hidden = false;
    sync();
    media.addEventListener("change", sync);
    btn.addEventListener("click", function () {
        const next = current() === "dark" ? "light" : "dark";
        root.setAttribute("data-theme", next);
        try {
            localStorage.setItem("theme", next);
        } catch (e) {}
        sync();
    });
}

document.addEventListener("DOMContentLoaded", function () {
    initThemeToggle();
    initVideos();
    document.querySelectorAll("[data-explorer]").forEach(initExplorer);
    initDetailsToggle();
    initCopy();
});
