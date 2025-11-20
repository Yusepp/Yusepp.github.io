// main.js

// -------- Publication image mapping --------
// Map *lowercased* titles to image paths in assets/papers/*.png
const PUB_IMAGES = {
    "automated detection of visual attribute reliance with a self-reflective agent":
        "assets/papers/saia.png",
    "experimenting with affective computing models in video interviews with spanish-speaking older adults":
        "assets/papers/elder.png",
    "openmaia: a multimodal automated interpretability agent based on open-source models":
        "assets/papers/openmaia.png",
    // Add more titles -> image paths as you like
};

function getPubImage(title) {
    if (!title) return "";
    const key = title.toLowerCase().trim();
    return PUB_IMAGES[key] || "";
}

// -------- Author formatting / highlighting --------

// Variants of *your* author name to highlight
const MY_AUTHOR_NAMES = [
    "Josep Lopez Camuñas",
    "Josep López Camuñas",
    "Josep Lopez Camunas",
    "Josep López Camunas",
];

function escapeRegExp(str) {
    return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function highlightMyName(authorStr) {
    let result = authorStr;
    MY_AUTHOR_NAMES.forEach(function (name) {
        const re = new RegExp(escapeRegExp(name), "gi");
        result = result.replace(re, function (match) {
            // keep original spelling/case in the text, just wrap in <strong>
            return "<strong>" + match + "</strong>";
        });
    });
    return result;
}

/**
 * Turn "A and B and C and D" into
 * "A, B, C, D" and bold your name.
 */
function formatAuthors(authorStr) {
    if (!authorStr) return "";
    // Split on " and " (case-insensitive), multiple times if needed.
    const parts = authorStr
        .split(/\s+and\s+/i)
        .map(function (p) {
            return p.trim();
        })
        .filter(Boolean);

    if (!parts.length) return "";

    const formatted = parts.map(function (p) {
        return highlightMyName(p);
    });

    return formatted.join(", ");
}

// -------- CONFIG LOADER --------

async function loadConfig() {
    let cfg;
    try {
        const res = await fetch("config.json");
        if (!res.ok) {
            throw new Error("config.json HTTP " + res.status);
        }
        cfg = await res.json();
    } catch (err) {
        console.error("Error loading config.json:", err);
        return;
    }

    function setText(id, value) {
        const el = document.getElementById(id);
        if (el && value != null) el.textContent = value;
    }

    function setHTML(id, html) {
        const el = document.getElementById(id);
        if (el && html != null) el.innerHTML = html;
    }

    // ---------- Page meta / footer ----------
    setText("footer-name", cfg.name);
    const yearEl = document.getElementById("footer-year");
    if (yearEl) yearEl.textContent = new Date().getFullYear();
    if (cfg.name) {
        document.title = cfg.name + " – Research Homepage";
    }

    // ---------- Profile basics ----------
    setText("profile-name", cfg.name || "Your Name");
    setText("profile-title", cfg.title || "");
    const affiliation = cfg.affiliation2
        ? (cfg.affiliation || "") + ", " + cfg.affiliation2
        : cfg.affiliation;
    setText("profile-affiliation", affiliation || "");
    setText("profile-location", cfg.location || "");

    // ---------- Photo / avatar ----------
    const photoEl = document.getElementById("profile-photo");
    const avatarEl = document.getElementById("profile-avatar-fallback");
    if (photoEl && avatarEl) {
        if (cfg.avatarUrl) {
            photoEl.src = cfg.avatarUrl;
            photoEl.style.display = "block";
            avatarEl.style.display = "none";
            photoEl.onerror = function () {
                photoEl.style.display = "none";
                avatarEl.style.display = "flex";
            };
        } else {
            photoEl.style.display = "none";
            avatarEl.style.display = "flex";
        }
        if (cfg.initials) {
            avatarEl.textContent = cfg.initials;
        }
    }

    // ---------- Emails ----------
    if (cfg.primaryEmail) {
        setHTML(
            "profile-email-primary",
            '<a href="mailto:' +
                cfg.primaryEmail +
                '">' +
                cfg.primaryEmail +
                "</a>",
        );
    }
    if (cfg.secondaryEmail) {
        setHTML(
            "profile-email-secondary",
            '<a href="mailto:' +
                cfg.secondaryEmail +
                '">' +
                cfg.secondaryEmail +
                "</a>",
        );
    }

    // ---------- Online links ----------
    const links = [];
    if (cfg.github) {
        links.push({
            label: "GitHub",
            url: "https://github.com/" + cfg.github,
        });
    }
    if (cfg.scholarUrl) {
        links.push({ label: "Scholar", url: cfg.scholarUrl });
    }
    if (cfg.linkedinUrl) {
        links.push({ label: "LinkedIn", url: cfg.linkedinUrl });
    }
    if (cfg.orcidUrl) {
        links.push({ label: "ORCID", url: cfg.orcidUrl });
    }
    if (cfg.twitterUrl) {
        links.push({ label: "Twitter/X", url: cfg.twitterUrl });
    }

    const linksContainer = document.getElementById("profile-links");
    if (linksContainer) {
        linksContainer.innerHTML = "";
        links.forEach(function (link) {
            const a = document.createElement("a");
            a.className = "profile-chip";
            a.href = link.url;
            a.target = "_blank";
            a.rel = "noopener";
            a.textContent = link.label;
            linksContainer.appendChild(a);
        });
    }

    // ---------- Research topics ----------
    const topicsEl = document.getElementById("research-topics");
    if (topicsEl) {
        topicsEl.innerHTML = "";
        (cfg.researchTopics || []).forEach(function (topic) {
            const span = document.createElement("span");
            span.textContent = topic;
            topicsEl.appendChild(span);
        });
    }

    // ---------- Internship note ----------
    if (cfg.openToInternships && cfg.internshipNote) {
        const block = document.getElementById("internship-block");
        const note = document.getElementById("internship-note");
        if (block && note) {
            note.textContent = cfg.internshipNote;
            block.classList.remove("d-none");
        }
    }

    // ---------- CV link ----------
    if (cfg.cvUrl) {
        const cvBlock = document.getElementById("cv-block");
        const cvLink = document.getElementById("cv-link");
        if (cvBlock && cvLink) {
            cvLink.href = cfg.cvUrl;
            cvBlock.classList.remove("d-none");
        }
    }

    // ---------- News ----------
    const newsList = document.getElementById("news-list");
    if (newsList) {
        newsList.innerHTML = "";
        (cfg.news || []).forEach(function (item) {
            const li = document.createElement("li");
            li.className = "mb-1";
            const dateSpan = document.createElement("span");
            dateSpan.className = "news-date";
            dateSpan.textContent = "[" + item.label + "]";
            li.appendChild(dateSpan);
            li.appendChild(document.createTextNode(" "));
            if (item.url) {
                const a = document.createElement("a");
                a.href = item.url;
                a.target = "_blank";
                a.rel = "noopener";
                a.textContent = item.text;
                li.appendChild(a);
            } else {
                li.appendChild(document.createTextNode(item.text));
            }
            newsList.appendChild(li);
        });
    }

    // ---------- Teaching ----------
    const teachingList = document.getElementById("teaching-list");
    if (teachingList) {
        teachingList.innerHTML = "";
        (cfg.teaching || []).forEach(function (t) {
            const li = document.createElement("li");
            li.className = "mb-1";
            const termSpan = document.createElement("span");
            termSpan.className = "teaching-term";
            termSpan.textContent = "[" + t.term + "]";
            li.appendChild(termSpan);
            li.appendChild(document.createTextNode(" "));
            if (t.url) {
                const a = document.createElement("a");
                a.href = t.url;
                a.target = "_blank";
                a.rel = "noopener";
                a.textContent = t.course;
                li.appendChild(a);
            } else {
                li.appendChild(document.createTextNode(t.course));
            }
            if (t.role) {
                li.appendChild(document.createTextNode(" — " + t.role));
            }
            teachingList.appendChild(li);
        });
    }

    // ---------- Awards ----------
    const awardsList = document.getElementById("awards-list");
    if (awardsList) {
        awardsList.innerHTML = "";
        (cfg.awards || []).forEach(function (text) {
            const li = document.createElement("li");
            li.className = "mb-1";
            li.textContent = text;
            awardsList.appendChild(li);
        });
    }

    // ---------- Service ----------
    const serviceList = document.getElementById("service-list");
    if (serviceList) {
        serviceList.innerHTML = "";
        (cfg.service || []).forEach(function (text) {
            const li = document.createElement("li");
            li.className = "mb-1";
            li.textContent = text;
            serviceList.appendChild(li);
        });
    }
}

// -------- PUBLICATIONS LOADER --------

async function loadPublications() {
    let pubs;
    try {
        const res = await fetch("publications.json");
        if (!res.ok) {
            throw new Error("publications.json HTTP " + res.status);
        }
        pubs = await res.json();
    } catch (err) {
        console.error("Error loading publications.json:", err);
        const listEl = document.getElementById("pub-list");
        if (listEl) {
            listEl.innerHTML =
                '<div class="text-muted">No publications loaded. Check <code>publications.json</code>.</div>';
        }
        return;
    }

    // Sort by year descending
    pubs.sort(function (a, b) {
        return (b.year || 0) - (a.year || 0);
    });

    const listEl = document.getElementById("pub-list");
    if (!listEl) return;

    listEl.innerHTML = "";

    pubs.forEach(function (pub) {
        const links = pub.links || {};

        const card = document.createElement("div");
        card.className = "pub-card";

        // Title
        const titleEl = document.createElement("div");
        titleEl.className = "pub-card-title";
        titleEl.textContent = pub.title || "";
        card.appendChild(titleEl);

        // Meta: authors (formatted) · venue · year
        const metaEl = document.createElement("div");
        metaEl.className = "pub-card-meta";

        const metaPieces = [];

        if (pub.authors) {
            metaPieces.push(formatAuthors(pub.authors)); // returns HTML
        }
        if (pub.venue) {
            metaPieces.push(pub.venue);
        }
        if (pub.year) {
            metaPieces.push(String(pub.year));
        }

        metaEl.innerHTML = metaPieces.join(" · ");
        card.appendChild(metaEl);

        // Optional big image UNDER title/meta
        const imgPath = getPubImage(pub.title);
        if (imgPath) {
            const imgWrap = document.createElement("div");
            imgWrap.className = "pub-card-image-block";

            const img = document.createElement("img");
            img.className = "pub-card-image";
            img.src = imgPath;
            img.alt = pub.title || "Publication figure";
            img.loading = "lazy";

            imgWrap.appendChild(img);
            card.appendChild(imgWrap);
        }

        // Chips for links (PDF / Code / DOI / Scholar...)
        const chipsWrap = document.createElement("div");
        chipsWrap.className = "pub-card-chips";

        function addChip(label, key) {
            const url = links[key];
            if (!url) return;
            const a = document.createElement("a");
            a.className = "pub-chip";
            a.href = url;
            a.target = "_blank";
            a.rel = "noopener";
            a.textContent = label;
            chipsWrap.appendChild(a);
        }

        addChip("PDF", "pdf");
        addChip("Code", "code");
        addChip("DOI", "doi");
        addChip("Scholar", "scholar");

        if (chipsWrap.children.length) {
            card.appendChild(chipsWrap);
        }

        // Make the whole card clickable if we have a "primary" URL
        const primaryUrl =
            links.pdf || links.doi || links.scholar || links.code || "";
        if (primaryUrl) {
            card.classList.add("pub-card-clickable");
            card.addEventListener("click", function (e) {
                if (e.target.closest("a")) return;
                window.open(primaryUrl, "_blank", "noopener");
            });
        }

        listEl.appendChild(card);
    });
}

// -------- BOOTSTRAP --------

document.addEventListener("DOMContentLoaded", function () {
    loadConfig();
    loadPublications();
});
