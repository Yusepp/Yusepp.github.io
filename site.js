// site.js — progressive enhancements only.
// All content is rendered at build time by scripts/build.py; the page works without JS.

// -------- Emails (assembled here to keep them away from simple scrapers) --------

function initEmails() {
    document.querySelectorAll(".js-email").forEach(function (a) {
        const email = a.dataset.user + "@" + a.dataset.domain;
        a.href = "mailto:" + email;
        a.textContent = email;
    });
}

// -------- Scrollspy for the sections nav --------

function initScrollspy() {
    const links = Array.from(document.querySelectorAll(".sections-nav .nav-link-compact"));
    const sections = links
        .map(function (link) {
            return document.querySelector(link.getAttribute("href"));
        })
        .filter(Boolean);
    if (!sections.length || !("IntersectionObserver" in window)) return;

    const visible = new Set();

    function setActive(id) {
        links.forEach(function (link) {
            const on = link.getAttribute("href") === "#" + id;
            link.classList.toggle("active", on);
            if (on) link.setAttribute("aria-current", "true");
            else link.removeAttribute("aria-current");
        });
    }

    const observer = new IntersectionObserver(
        function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) visible.add(entry.target);
                else visible.delete(entry.target);
            });
            // Topmost visible section wins
            const first = sections.find(function (s) {
                return visible.has(s);
            });
            if (first) setActive(first.id);
        },
        { rootMargin: "-20% 0px -60% 0px" }
    );
    sections.forEach(function (s) {
        observer.observe(s);
    });
}

// -------- BibTeX copy buttons --------

function initBibtexCopy() {
    if (!navigator.clipboard) return;
    document.querySelectorAll(".pub-copy").forEach(function (btn) {
        btn.hidden = false;
        btn.addEventListener("click", function () {
            const pre = btn.parentElement.querySelector(".pub-bibtex");
            navigator.clipboard.writeText(pre.textContent).then(
                function () {
                    btn.textContent = "Copied!";
                    setTimeout(function () {
                        btn.textContent = "Copy";
                    }, 1500);
                },
                function () {
                    btn.textContent = "Select & copy";
                }
            );
        });
    });
}

// -------- Figure lightbox --------
// Clicking a figure only enlarges it; it never navigates anywhere.

function initLightbox() {
    const dialog = document.getElementById("lightbox");
    if (!dialog || typeof dialog.showModal !== "function") return;
    const img = dialog.querySelector(".lightbox-img");
    let opener = null;

    document.querySelectorAll(".pub-figure-link").forEach(function (btn) {
        btn.addEventListener("click", function () {
            opener = btn;
            img.src = btn.dataset.full;
            img.alt = btn.querySelector("img").alt;
            dialog.showModal();
        });
    });

    // Clicking the backdrop (outside the image and button) closes it
    dialog.addEventListener("click", function (e) {
        if (e.target === dialog) dialog.close();
    });
    dialog.addEventListener("close", function () {
        img.removeAttribute("src");
        if (opener) opener.focus();
    });
}

// -------- Theme toggle (light / dark) --------

function initThemeToggle() {
    const btn = document.getElementById("theme-toggle");
    if (!btn) return;
    const root = document.documentElement;
    const media = window.matchMedia("(prefers-color-scheme: dark)");

    function current() {
        return root.getAttribute("data-theme") || (media.matches ? "dark" : "light");
    }
    function sync() {
        btn.setAttribute("aria-pressed", String(current() === "dark"));
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
    initEmails();
    initScrollspy();
    initBibtexCopy();
    initLightbox();
    initThemeToggle();
});
