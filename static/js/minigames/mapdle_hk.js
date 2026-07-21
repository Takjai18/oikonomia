/**
 * Mapdle HK — Worldle-style geography guesser for Oikonomia.
 * Show a place silhouette → guess from a list → distance + direction + proximity %.
 * Ref: https://worldle.teuteuf.fr/
 */
let timeoutIds = [];

const registerTimeout = (fn, delay) => {
    const id = setTimeout(fn, delay);
    timeoutIds.push(id);
    return id;
};

const clearAllTimers = () => {
    timeoutIds.forEach(clearTimeout);
    timeoutIds = [];
};

/** Distinctive SVG path silhouettes (viewBox 0 0 100 100). Stylized, not survey-accurate. */
const SILHOUETTES = {
    旺角: "M20,70 L20,35 Q22,20 40,18 L55,18 Q72,20 75,35 L78,70 Q70,82 50,85 Q30,82 20,70 Z M35,40 L45,40 L45,55 L35,55 Z M55,38 L65,38 L65,52 L55,52 Z",
    中環: "M15,55 L25,40 L40,35 L55,30 L70,35 L85,50 L80,75 L65,85 L40,88 L20,75 Z M45,50 Q55,45 60,55 L55,70 L40,68 Z",
    沙田: "M30,20 L70,25 L85,45 L80,70 L55,90 L25,80 L15,50 Z M40,45 L60,48 L58,65 L38,62 Z",
    屯門: "M25,30 L50,15 L75,30 L85,55 L70,85 L35,90 L15,60 Z M40,50 L55,45 L60,65 L42,70 Z",
    赤柱: "M40,15 L65,20 L80,45 L75,70 L55,90 L30,85 L20,55 L25,30 Z M45,40 Q55,38 58,50 L50,65 L40,55 Z",
    大澳: "M20,50 Q15,30 35,20 L70,25 Q90,40 85,60 L70,85 L30,90 Q10,70 20,50 Z M40,45 L55,42 L60,60 L45,65 Z",
    科大: "M30,25 L70,20 L85,40 L80,75 L50,95 L20,75 L15,45 Z M35,50 L50,40 L65,50 L55,70 L40,70 Z",
    太平山: "M15,80 L30,40 L45,20 L55,35 L70,15 L85,45 L90,80 L50,90 Z",
    迪士尼: "M25,55 L40,30 L50,45 L60,25 L75,50 L80,75 L50,90 L20,75 Z M48,55 L55,55 L55,70 L48,70 Z",
    機場: "M10,55 L40,45 L55,20 L70,45 L95,50 L90,65 L70,60 L55,85 L40,60 L15,70 Z",
    尖沙咀: "M30,25 L70,20 L85,50 L75,85 L40,90 L20,60 Z M45,45 L60,48 L58,68 L42,65 Z",
    銅鑼灣: "M25,40 L50,20 L75,35 L85,60 L70,85 L35,90 L15,65 Z M40,50 L55,48 L58,65 L42,68 Z",
    觀塘: "M20,35 L55,15 L80,40 L85,70 L55,90 L20,75 Z M40,45 L60,50 L55,70 L38,65 Z",
    荃灣: "M15,45 L40,20 L70,25 L90,50 L80,80 L45,90 L20,70 Z",
    元朗: "M25,25 L75,20 L90,55 L70,90 L25,85 L10,50 Z M40,45 L55,40 L60,60 L42,65 Z",
    西貢: "M35,15 L70,30 L85,55 L75,85 L40,95 L15,70 L20,40 Z M45,50 L58,55 L52,72 L40,65 Z",
};

const DEFAULT_PLACES = [
    { name: "旺角", lat: 22.3193, lng: 114.1694 },
    { name: "中環", lat: 22.2819, lng: 114.1581 },
    { name: "沙田", lat: 22.3771, lng: 114.1974 },
    { name: "屯門", lat: 22.3908, lng: 113.9725 },
    { name: "赤柱", lat: 22.2193, lng: 114.2108 },
    { name: "大澳", lat: 22.2541, lng: 113.8624 },
    { name: "科大", lat: 22.3364, lng: 114.2655 },
    { name: "太平山", lat: 22.2759, lng: 114.1455 },
    { name: "迪士尼", lat: 22.3130, lng: 114.0413 },
    { name: "機場", lat: 22.3080, lng: 113.9185 },
    { name: "尖沙咀", lat: 22.2976, lng: 114.1722 },
    { name: "銅鑼灣", lat: 22.2800, lng: 114.1850 },
    { name: "觀塘", lat: 22.3120, lng: 114.2250 },
    { name: "荃灣", lat: 22.3710, lng: 114.1140 },
    { name: "元朗", lat: 22.4445, lng: 114.0222 },
    { name: "西貢", lat: 22.3810, lng: 114.2700 },
];

/** Max distance across HK for proximity % (~Lantau to Sai Kung). */
const HK_MAX_KM = 70;

function enrichPlace(p) {
    const silhouette = p.silhouette || p.path || SILHOUETTES[p.name] || null;
    const image = p.image || p.imageUrl || null;
    return { ...p, silhouette, image };
}

function calcDistance(lat1, lon1, lat2, lon2) {
    const R = 6371;
    const dLat = ((lat2 - lat1) * Math.PI) / 180;
    const dLon = ((lon2 - lon1) * Math.PI) / 180;
    const a =
        Math.sin(dLat / 2) * Math.sin(dLat / 2) +
        Math.cos((lat1 * Math.PI) / 180) *
            Math.cos((lat2 * Math.PI) / 180) *
            Math.sin(dLon / 2) *
            Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
}

function calcBearing(lat1, lon1, lat2, lon2) {
    const dLon = ((lon2 - lon1) * Math.PI) / 180;
    const φ1 = (lat1 * Math.PI) / 180;
    const φ2 = (lat2 * Math.PI) / 180;
    const y = Math.sin(dLon) * Math.cos(φ2);
    const x =
        Math.cos(φ1) * Math.sin(φ2) -
        Math.sin(φ1) * Math.cos(φ2) * Math.cos(dLon);
    let brng = (Math.atan2(y, x) * 180) / Math.PI;
    brng = (brng + 360) % 360;
    const arrows = ["⬆️", "↗️", "➡️", "↘️", "⬇️", "↙️", "⬅️", "↖️"];
    return arrows[Math.round(brng / 45) % 8];
}

/** Worldle-style proximity: 100% = on target, 0% = as far as HK_MAX_KM. */
function proximityPercent(distKm, maxKm) {
    const pct = Math.max(0, Math.min(100, 100 - (distKm / maxKm) * 100));
    return Math.round(pct);
}

/** Green/yellow/black squares like Worldle share grid (5 squares). */
function proximitySquares(pct) {
    const filled = Math.floor(pct / 20);
    const half = pct % 20 >= 10 ? 1 : 0;
    const empty = 5 - filled - half;
    return "🟩".repeat(filled) + "🟨".repeat(half) + "⬛".repeat(Math.max(0, empty));
}

function renderSilhouetteHtml(place) {
    if (place.image) {
        const safe = String(place.image).replace(/"/g, "&quot;");
        return `<img class="md-silhouette-img" src="${safe}" alt="地方輪廓" draggable="false" />`;
    }
    const path = place.silhouette || "M20,20 L80,20 L80,80 L20,80 Z";
    return `
        <svg class="md-silhouette-svg" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
            <path d="${path}" fill="#1a1a1a" stroke="none" />
        </svg>`;
}

export function mount(rootEl, options) {
    clearAllTimers();

    const rawPlaces = options.config?.places || DEFAULT_PLACES;
    const places = rawPlaces.map(enrichPlace);
    const config = {
        maxGuesses: 6,
        winRadiusKm: 0.5,
        maxDistKm: HK_MAX_KM,
        ...options.config,
        places,
    };

    let targetIndex = 0;
    if (options.taskId) {
        let hash = 0;
        for (let i = 0; i < options.taskId.length; i++) {
            hash = options.taskId.charCodeAt(i) + ((hash << 5) - hash);
        }
        targetIndex = Math.abs(hash) % places.length;
    } else {
        targetIndex = Math.floor(Math.random() * places.length);
    }
    const targetPlace = places[targetIndex];

    let guesses = [];
    let isGameOver = false;

    rootEl.innerHTML = `
        <style>
            .md-container { font-family: system-ui, -apple-system, sans-serif; max-width: 420px; margin: 0 auto; padding: 12px; text-align: center; color: #1a1a1a; }
            .md-title { font-size: 18px; font-weight: 700; margin: 0 0 4px; }
            .md-sub { font-size: 12px; color: #666; margin-bottom: 12px; line-height: 1.4; }
            .md-silhouette-wrap {
                background: #f0f0f0;
                border-radius: 12px;
                padding: 16px;
                margin-bottom: 14px;
                min-height: 200px;
                display: flex;
                align-items: center;
                justify-content: center;
                border: 1px solid #ddd;
            }
            .md-silhouette-svg { width: min(70vw, 240px); height: min(70vw, 240px); max-width: 100%; }
            .md-silhouette-img { max-width: 100%; max-height: 240px; object-fit: contain; filter: brightness(0); }
            .md-input-area { display: flex; gap: 8px; margin-bottom: 10px; }
            .md-select { flex: 1; padding: 12px; font-size: 16px; border: 2px solid #ccc; border-radius: 8px; background: #fff; min-width: 0; }
            .md-btn { padding: 12px 16px; font-size: 16px; background: #1a1a1a; color: #fff; border: none; border-radius: 8px; cursor: pointer; font-weight: 700; white-space: nowrap; touch-action: manipulation; }
            .md-btn:disabled { background: #999; cursor: not-allowed; }
            .md-rem { font-size: 14px; color: #444; margin-bottom: 10px; font-weight: 600; }
            .md-history { display: flex; flex-direction: column; gap: 6px; text-align: left; }
            .md-guess-row {
                display: grid;
                grid-template-columns: 1fr auto;
                gap: 4px 8px;
                background: #f5f5f5;
                padding: 10px 12px;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
                align-items: center;
                border: 1px solid #e5e5e5;
            }
            .md-guess-row.win { background: #d5f5e3; border-color: #2ecc71; }
            .md-guess-meta { font-size: 13px; color: #333; text-align: right; }
            .md-guess-sq { font-size: 12px; letter-spacing: 1px; grid-column: 1 / -1; }
            .md-toast {
                position: fixed; top: 20px; left: 50%; transform: translateX(-50%);
                background: rgba(0,0,0,0.85); color: #fff; padding: 10px 18px;
                border-radius: 20px; display: none; z-index: 100; pointer-events: none;
                font-size: 14px; max-width: 90vw;
            }
        </style>
        <div class="md-container">
            <h3 class="md-title">Mapdle · 香港</h3>
            <p class="md-sub">睇輪廓估地方（Worldle 玩法）· 每次估完會顯示距離同方向</p>
            <div class="md-silhouette-wrap" id="md-silhouette" aria-label="目標地方輪廓">
                ${renderSilhouetteHtml(targetPlace)}
            </div>
            <div class="md-input-area">
                <select class="md-select" id="md-select" aria-label="選擇地點">
                    <option value="" disabled selected>選擇地點…</option>
                    ${places.map((p) => `<option value="${p.name}">${p.name}</option>`).join("")}
                </select>
                <button type="button" class="md-btn" id="md-submit">猜測</button>
            </div>
            <div class="md-rem">剩餘次數：<span id="md-rem">${config.maxGuesses}</span> / ${config.maxGuesses}</div>
            <div class="md-history" id="md-history"></div>
            <div id="md-toast" class="md-toast"></div>
        </div>
    `;

    const showToast = (msg, duration = 2000) => {
        const t = rootEl.querySelector("#md-toast");
        if (!t) return;
        t.textContent = msg;
        t.style.display = "block";
        registerTimeout(() => {
            if (t) t.style.display = "none";
        }, duration);
    };

    const submitBtn = rootEl.querySelector("#md-submit");
    const selectEl = rootEl.querySelector("#md-select");
    const historyEl = rootEl.querySelector("#md-history");
    const remEl = rootEl.querySelector("#md-rem");

    submitBtn.onclick = () => {
        if (isGameOver) {
            clearAllTimers();
            mount(rootEl, options);
            return;
        }

        const selectedName = selectEl.value;
        if (!selectedName) {
            showToast("請先選擇地點");
            return;
        }

        const guessedPlace = places.find((p) => p.name === selectedName);
        if (!guessedPlace) {
            showToast("無效地點");
            return;
        }
        if (guesses.some((g) => g.name === selectedName)) {
            showToast("已經估過呢個地方");
            return;
        }

        const dist = calcDistance(
            guessedPlace.lat,
            guessedPlace.lng,
            targetPlace.lat,
            targetPlace.lng,
        );
        const isWin =
            selectedName === targetPlace.name || dist <= (config.winRadiusKm || 0.5);
        const arrow = isWin
            ? "🎯"
            : calcBearing(
                  guessedPlace.lat,
                  guessedPlace.lng,
                  targetPlace.lat,
                  targetPlace.lng,
              );
        const pct = isWin
            ? 100
            : proximityPercent(dist, config.maxDistKm || HK_MAX_KM);
        const squares = proximitySquares(pct);

        guesses.push({ name: selectedName, dist, arrow, pct, squares });

        const row = document.createElement("div");
        row.className = `md-guess-row${isWin ? " win" : ""}`;
        row.innerHTML = `
            <span>${selectedName}</span>
            <span class="md-guess-meta">${isWin ? "0 km 🎯" : `${dist.toFixed(1)} km ${arrow}`} · ${pct}%</span>
            <span class="md-guess-sq">${squares}</span>
        `;
        historyEl.insertBefore(row, historyEl.firstChild);

        remEl.textContent = String(config.maxGuesses - guesses.length);
        selectEl.value = "";

        if (isWin) {
            isGameOver = true;
            selectEl.disabled = true;
            submitBtn.disabled = true;
            showToast(`✅ 正確！係「${targetPlace.name}」`, 2200);
            registerTimeout(() => {
                if (options.onComplete) {
                    options.onComplete({
                        taskId: options.taskId,
                        gameId: "mapdle_hk",
                        result: "win",
                        guesses: guesses.length,
                        target: targetPlace.name,
                    });
                }
            }, 1600);
        } else if (guesses.length >= config.maxGuesses) {
            isGameOver = true;
            selectEl.disabled = true;
            showToast(`用盡次數。答案係：${targetPlace.name}`, 3500);
            submitBtn.textContent = "重試";
            submitBtn.disabled = false;
        }
    };
}

export function unmount(rootEl) {
    clearAllTimers();
    rootEl.innerHTML = "";
}
