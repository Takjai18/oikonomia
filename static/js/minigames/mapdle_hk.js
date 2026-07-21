
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

export function mount(rootEl, options) {
    const defaultPlaces = [
        { name: "旺角", lat: 22.3193, lng: 114.1694 },
        { name: "中環", lat: 22.2819, lng: 114.1581 },
        { name: "沙田", lat: 22.3771, lng: 114.1974 },
        { name: "屯門", lat: 22.3908, lng: 113.9725 },
        { name: "赤柱", lat: 22.2193, lng: 114.2108 },
        { name: "大澳", lat: 22.2541, lng: 113.8624 },
        { name: "科大", lat: 22.3364, lng: 114.2655 },
        { name: "太平山", lat: 22.2759, lng: 114.1455 },
        { name: "迪士尼", lat: 22.3130, lng: 114.0413 },
        { name: "機場", lat: 22.3080, lng: 113.9185 }
    ];

    const config = { maxGuesses: 6, winRadiusKm: 0.5, places: defaultPlaces, ...options.config };
    
    let targetIndex = 0;
    if (options.taskId) {
        let hash = 0;
        for (let i = 0; i < options.taskId.length; i++) hash = options.taskId.charCodeAt(i) + ((hash << 5) - hash);
        targetIndex = Math.abs(hash) % config.places.length;
    } else {
        targetIndex = Math.floor(Math.random() * config.places.length);
    }
    const targetPlace = config.places[targetIndex];

    let guesses = [];
    let isGameOver = false;

    rootEl.innerHTML = `
        <style>
            .md-container { font-family: sans-serif; max-width: 450px; margin: 0 auto; padding: 15px; text-align: center; background: #fdfefe; border-radius: 12px; }
            .md-header { font-size: 20px; font-weight: bold; margin-bottom: 20px; color: #2c3e50; }
            .md-input-area { display: flex; gap: 10px; justify-content: center; margin-bottom: 20px; }
            .md-select { flex: 1; padding: 12px; font-size: 16px; border: 2px solid #bdc3c7; border-radius: 8px; background: white; }
            .md-btn { padding: 12px 20px; font-size: 16px; background: #3498db; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; }
            .md-btn:disabled { background: #95a5a6; cursor: not-allowed; }
            .md-history { display: flex; flex-direction: column; gap: 8px; }
            .md-guess-row { display: flex; justify-content: space-between; background: #ecf0f1; padding: 12px; border-radius: 8px; font-size: 16px; font-weight: bold; align-items: center; }
            .md-guess-row.win { background: #d5f5e3; border: 2px solid #2ecc71; }
            .md-toast { position: fixed; top: 20px; left: 50%; transform: translateX(-50%); background: rgba(0,0,0,0.8); color: white; padding: 10px 20px; border-radius: 20px; display: none; z-index: 100; pointer-events: none; }
        </style>
        <div class="md-container">
            <div class="md-header">地點鎖定 (香港)</div>
            <div class="md-input-area">
                <select class="md-select" id="md-select">
                    <option value="" disabled selected>選擇地點...</option>
                    ${config.places.map(p => `<option value="${p.name}">${p.name}</option>`).join('')}
                </select>
                <button class="md-btn" id="md-submit">猜測</button>
            </div>
            <div class="md-header" style="font-size:16px;">剩餘次數: <span id="md-rem">${config.maxGuesses}</span></div>
            <div class="md-history" id="md-history"></div>
            <div id="md-toast" class="md-toast"></div>
        </div>
    `;

    const showToast = (msg, duration=2000) => {
        const t = rootEl.querySelector('#md-toast');
        if(!t) return;
        t.textContent = msg;
        t.style.display = 'block';
        registerTimeout(() => { if(t) t.style.display = 'none'; }, duration);
    };

    const calcDistance = (lat1, lon1, lat2, lon2) => {
        const R = 6371; 
        const dLat = (lat2 - lat1) * Math.PI / 180;
        const dLon = (lon2 - lon1) * Math.PI / 180;
        const a = Math.sin(dLat/2) * Math.sin(dLat/2) + Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.sin(dLon/2) * Math.sin(dLon/2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
        return R * c;
    };

    const calcBearing = (lat1, lon1, lat2, lon2) => {
        const dLon = (lon2 - lon1) * Math.PI / 180;
        lat1 = lat1 * Math.PI / 180;
        lat2 = lat2 * Math.PI / 180;
        const y = Math.sin(dLon) * Math.cos(lat2);
        const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLon);
        let brng = Math.atan2(y, x) * 180 / Math.PI;
        brng = (brng + 360) % 360;
        const arrows = ["⬆️", "↗️", "➡️", "↘️", "⬇️", "↙️", "⬅️", "↖️"];
        const idx = Math.round(brng / 45) % 8;
        return arrows[idx];
    };

    const submitBtn = rootEl.querySelector('#md-submit');
    const selectEl = rootEl.querySelector('#md-select');
    const historyEl = rootEl.querySelector('#md-history');

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

        const guessedPlace = config.places.find(p => p.name === selectedName);
        if (guesses.some(g => g.name === selectedName)) {
            showToast("已經猜過這個地點了");
            return;
        }

        const dist = calcDistance(guessedPlace.lat, guessedPlace.lng, targetPlace.lat, targetPlace.lng);
        const arrow = dist <= config.winRadiusKm ? "🎯" : calcBearing(guessedPlace.lat, guessedPlace.lng, targetPlace.lat, targetPlace.lng);
        
        guesses.push({ name: selectedName, dist, arrow });
        
        const row = document.createElement('div');
        row.className = `md-guess-row ${dist <= config.winRadiusKm ? 'win' : ''}`;
        row.innerHTML = `<span>${selectedName}</span> <span>${dist.toFixed(1)} km ${arrow}</span>`;
        historyEl.insertBefore(row, historyEl.firstChild);
        
        rootEl.querySelector('#md-rem').textContent = config.maxGuesses - guesses.length;
        selectEl.value = "";

        if (dist <= config.winRadiusKm) {
            isGameOver = true;
            selectEl.disabled = true;
            submitBtn.disabled = true;
            showToast("✅ 成功鎖定目標！", 2000);
            registerTimeout(() => {
                if (options.onComplete) options.onComplete({ taskId: options.taskId, gameId: 'mapdle_hk', result: 'win' });
            }, 1500);
        } else if (guesses.length >= config.maxGuesses) {
            isGameOver = true;
            selectEl.disabled = true;
            showToast(`任務失敗，目標地點是: ${targetPlace.name}`, 3000);
            submitBtn.textContent = "重試";
        }
    };
}

export function unmount(rootEl) {
    clearAllTimers();
    rootEl.innerHTML = '';
}
