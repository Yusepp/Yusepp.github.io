// main.js (multi-JSON + pub_extras.json for image/project/code)

// -------- Helpers for mapping keys --------

function titleKey(title) {
    if (!title) return "";
    return title.toLowerCase().trim();
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
            // Keep original spelling/case, just wrap in <strong>
            return "<strong>" + match + "</strong>";
        });
    });
    return result;
}

/**
 * Turn "A and B and C and D" into "A, B, C, D"
 * and bold your name.
 */
function formatAuthors(authorStr) {
    if (!authorStr) return "";
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

// -------- Helper: safe JSON fetch --------

async function fetchJsonSafe(url) {
    try {
        const res = await fetch(url);
        if (!res.ok) {
            throw new Error(url + " HTTP " + res.status);
        }
        return await res.json();
    } catch (err) {
        console.error("Error loading " + url + ":", err);
        return null;
    }
}

// -------- PERSONAL INFO (profile, research, about) --------

async function loadPersonalInfo() {
    const data = await fetchJsonSafe("info/personal_info.json");
    if (!data) return;

    function setText(id, value) {
        const el = document.getElementById(id);
        if (el && value != null) el.textContent = value;
    }

    // Page meta / footer name
    setText("footer-name", data.name);
    const yearEl = document.getElementById("footer-year");
    if (yearEl) yearEl.textContent = new Date().getFullYear();
    if (data.name) {
        document.title = data.name + " – Research Homepage";
    }

    // Profile basics
    setText("profile-name", data.name || "Your Name");
    setText("profile-title", data.title || "");
    const affiliation = data.affiliation2
        ? (data.affiliation || "") + ", " + data.affiliation2
        : data.affiliation;
    setText("profile-affiliation", affiliation || "");
    setText("profile-location", data.location || "");

    // Photo / avatar
    const photoEl = document.getElementById("profile-photo");
    const avatarEl = document.getElementById("profile-avatar-fallback");
    if (photoEl && avatarEl) {
        if (data.avatarUrl) {
            photoEl.src = data.avatarUrl;
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
        if (data.initials) {
            avatarEl.textContent = data.initials;
        }
    }

    // Emails
    const emailPrimary = document.getElementById("profile-email-primary");
    if (emailPrimary && data.primaryEmail) {
        emailPrimary.innerHTML =
            '<a href="mailto:' +
            data.primaryEmail +
            '">' +
            data.primaryEmail +
            "</a>";
    }
    const emailSecondary = document.getElementById("profile-email-secondary");
    if (emailSecondary && data.secondaryEmail) {
        emailSecondary.innerHTML =
            '<a href="mailto:' +
            data.secondaryEmail +
            '">' +
            data.secondaryEmail +
            "</a>";
    }

    // Research topics
    const topicsEl = document.getElementById("research-topics");
    if (topicsEl) {
        topicsEl.innerHTML = "";
        (data.researchTopics || []).forEach(function (topic) {
            const span = document.createElement("span");
            span.textContent = topic;
            topicsEl.appendChild(span);
        });
    }

    // Internship note
    if (data.openToInternships && data.internshipNote) {
        const block = document.getElementById("internship-block");
        const note = document.getElementById("internship-note");
        if (block && note) {
            note.textContent = data.internshipNote;
            block.classList.remove("d-none");
        }
    }

    // CV link
    if (data.cvUrl) {
        const cvBlock = document.getElementById("cv-block");
        const cvLink = document.getElementById("cv-link");
        if (cvBlock && cvLink) {
            cvLink.href = data.cvUrl;
            cvBlock.classList.remove("d-none");
        }
    }

    // About text (optional override)
    const aboutBody = document.getElementById("about-body");
    if (
        aboutBody &&
        Array.isArray(data.aboutParagraphs) &&
        data.aboutParagraphs.length
    ) {
        aboutBody.innerHTML = data.aboutParagraphs
            .map(function (p) {
                return "<p>" + p + "</p>";
            })
            .join("");
    }
}

// -------- SOCIAL LINKS (rrss.json) --------

async function loadSocialLinks() {
    const data = await fetchJsonSafe("info/rrss.json");
    if (!data) return;

    const links = [];
    if (data.github) {
        links.push({
            label: "GitHub",
            url: "https://github.com/" + data.github,
        });
    }
    if (data.scholarUrl) {
        links.push({ label: "Scholar", url: data.scholarUrl });
    }
    if (data.linkedinUrl) {
        links.push({ label: "LinkedIn", url: data.linkedinUrl });
    }
    if (data.twitterUrl) {
        links.push({ label: "Twitter/X", url: data.twitterUrl });
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
}

// -------- NEWS (news.json) --------

async function loadNews() {
    const data = await fetchJsonSafe("info/news.json");
    if (!data || !Array.isArray(data.news)) return;

    const newsList = document.getElementById("news-list");
    if (!newsList) return;

    newsList.innerHTML = "";
    data.news.forEach(function (item) {
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

// -------- TEACHING + AWARDS + SERVICE (activities.json) --------

async function loadActivities() {
    const data = await fetchJsonSafe("info/activities.json");
    if (!data) return;

    // Teaching
    const teachingList = document.getElementById("teaching-list");
    if (teachingList && Array.isArray(data.teaching)) {
        teachingList.innerHTML = "";
        data.teaching.forEach(function (t) {
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

    // Awards
    const awardsList = document.getElementById("awards-list");
    if (awardsList && Array.isArray(data.awards)) {
        awardsList.innerHTML = "";
        data.awards.forEach(function (text) {
            const li = document.createElement("li");
            li.className = "mb-1";
            li.textContent = text;
            awardsList.appendChild(li);
        });
    }

    // Service
    const serviceList = document.getElementById("service-list");
    if (serviceList && Array.isArray(data.service)) {
        serviceList.innerHTML = "";
        data.service.forEach(function (text) {
            const li = document.createElement("li");
            li.className = "mb-1";
            li.textContent = text;
            serviceList.appendChild(li);
        });
    }
}

// -------- MISC (misc.json, optional) --------

async function loadMisc() {
    const data = await fetchJsonSafe("info/misc.json");
    if (!data) return;

    if (data.footerNote) {
        const footerNoteEl = document.getElementById("footer-note");
        if (footerNoteEl) {
            footerNoteEl.textContent = data.footerNote;
        }
    }
}

// -------- PUBLICATIONS (publications.json + pub_extras.json) --------

async function loadPublications() {
    // Load both base publications and extras in parallel
    const [pubs, extrasData] = await Promise.all([
        fetchJsonSafe("info/publications.json"),
        fetchJsonSafe("info/pub_extras.json"),
    ]);

    if (!Array.isArray(pubs)) {
        const listEl = document.getElementById("pub-list");
        if (listEl) {
            listEl.innerHTML =
                '<div class="text-muted">No publications loaded. Check <code>publications.json</code>.</div>';
        }
        return;
    }

    // Build extras map by normalized title
    const extrasMap = {};
    if (extrasData && Array.isArray(extrasData.extras)) {
        extrasData.extras.forEach(function (entry) {
            if (entry && entry.title) {
                extrasMap[titleKey(entry.title)] = entry;
            }
        });
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
        const key = titleKey(pub.title);
        const extras = extrasMap[key] || {};

        const imgPath = extras.image || "";
        const projectUrl = extras.project || "";
        const codeUrl = extras.code || "";

        const pdfUrl = links.pdf || "";
        const doiUrl = links.doi || "";
        const paperUrl = links.scholar || ""; // Scholar link, but label "Paper"

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
            metaPieces.push(formatAuthors(pub.authors)); // HTML with <strong>
        }
        if (pub.venue) {
            metaPieces.push(pub.venue);
        }
        if (pub.year) {
            metaPieces.push(String(pub.year));
        }

        metaEl.innerHTML = metaPieces.join(" · ");
        card.appendChild(metaEl);

        // Optional big image under title/meta
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

        // Pills: Project / Code / PDF / DOI / Paper
        const chipsWrap = document.createElement("div");
        chipsWrap.className = "pub-card-chips";

        function addChip(label, url) {
            if (!url) return;
            const a = document.createElement("a");
            a.className = "pub-chip";
            a.href = url;
            a.target = "_blank";
            a.rel = "noopener";
            a.textContent = label;
            chipsWrap.appendChild(a);
        }

        addChip("Project", projectUrl); // from extras
        addChip("Code", codeUrl); // from extras
        addChip("PDF", pdfUrl);
        addChip("DOI", doiUrl);
        addChip("Paper", paperUrl); // scholar link, nicer label

        if (chipsWrap.children.length) {
            card.appendChild(chipsWrap);
        }

        // Whole card clickable:
        // prefer Project → PDF → Paper → Code → DOI
        const primaryUrl =
            projectUrl || pdfUrl || paperUrl || codeUrl || doiUrl;

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
    loadPersonalInfo();
    loadSocialLinks();
    loadNews();
    loadActivities();
    loadMisc();
    loadPublications();
});
