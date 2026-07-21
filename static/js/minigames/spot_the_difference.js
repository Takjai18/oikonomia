
let timerId = null;
let resizeHandler = null;
let completeTimeoutId = null;

export function mount(rootEl, options) {
    if (timerId) {
        clearInterval(timerId);
        timerId = null;
    }
    if (completeTimeoutId) {
        clearTimeout(completeTimeoutId);
        completeTimeoutId = null;
    }
    if (resizeHandler) {
        window.removeEventListener('resize', resizeHandler);
        resizeHandler = null;
    }

    const defaultHotspots = [ { x: 20, y: 40, w: 40, h: 40, found: false }, { x: 135, y: 15, w: 30, h: 30, found: false }, { x: 70, y: 10, w: 60, h: 50, found: false }, { x: 130, y: 50, w: 40, h: 40, found: false }, { x: 5, y: 0, w: 50, h: 20, found: false } ];
    const config = { diffCount: 5, timeLimitSec: 90, hotspots: defaultHotspots, ...options.config };
    const currentHotspots = JSON.parse(JSON.stringify(config.hotspots));
    let found = 0, timeLeft = config.timeLimitSec;
    rootEl.innerHTML = `<style>.std-container { font-family: sans-serif; max-width: 500px; margin: 0 auto; padding: 10px; text-align: center; } .std-header { display: flex; justify-content: space-between; font-size: 18px; font-weight: bold; margin-bottom: 10px; } .std-svg-container { position: relative; width: 100%; display: flex; flex-direction: column; gap: 10px; } .std-svg-box { border: 2px solid #ccc; border-radius: 8px; overflow: hidden; background: #e0f7fa; position:relative; touch-action: none; } .std-toast { position: fixed; top: 20px; left: 50%; transform: translateX(-50%); background: rgba(0,0,0,0.8); color: white; padding: 10px 20px; border-radius: 20px; display: none; z-index: 100; pointer-events: none; } .std-btn { display: block; width: 100%; padding: 15px; margin: 10px 0; background: #3498db; color: white; border: none; border-radius: 8px; font-size: 18px; cursor: pointer; } .found-marker { position: absolute; border: 3px solid #e74c3c; border-radius: 50%; pointer-events: none; transform: translate(-50%, -50%); box-sizing: border-box; }</style><div class="std-container"><div class="std-header"><span id="std-time">時間: ${timeLeft}s</span><span id="std-score">找到: 0 / ${config.diffCount}</span></div><div class="std-svg-container"><div>(原圖)</div><div class="std-svg-box" id="std-svg-left"><svg viewBox="0 0 200 100" width="100%" height="auto"><rect x="20" y="50" width="40" height="40" fill="#f1c40f"/><circle cx="150" cy="30" r="15" fill="#e74c3c"/><polygon points="100,20 120,60 80,60" fill="#2ecc71"/><rect x="140" y="60" width="20" height="20" fill="#9b59b6"/><line x1="10" y1="10" x2="50" y2="10" stroke="#34495e" stroke-width="4"/></svg></div><div>(點擊不同處)</div><div class="std-svg-box" id="std-svg-right" style="cursor:crosshair;"><svg viewBox="0 0 200 100" width="100%" height="auto"><rect x="20" y="40" width="40" height="40" fill="#f1c40f"/> <circle cx="150" cy="30" r="15" fill="#3498db"/><polygon points="100,10 130,60 70,60" fill="#2ecc71"/><line x1="10" y1="10" x2="50" y2="10" stroke="#34495e" stroke-width="8"/></svg></div></div><div id="std-toast" class="std-toast"></div></div>`;
    const showToast = (msg) => { const t = rootEl.querySelector('#std-toast'); if(!t) return; t.textContent = msg; t.style.display = 'block'; setTimeout(() => { if(t) t.style.display = 'none'; }, 1500); };
    const rightBox = rootEl.querySelector('#std-svg-right');
    const handleResize = () => { const rect = rightBox.getBoundingClientRect(); const markers = rightBox.querySelectorAll('.found-marker'); markers.forEach(marker => { const origX = parseFloat(marker.dataset.ox), origY = parseFloat(marker.dataset.oy), origW = parseFloat(marker.dataset.ow), origH = parseFloat(marker.dataset.oh); marker.style.left = ((origX + origW/2) / 200 * rect.width) + 'px'; marker.style.top = ((origY + origH/2) / 100 * rect.height) + 'px'; marker.style.width = (origW / 200 * rect.width + 10) + 'px'; marker.style.height = (origH / 100 * rect.height + 10) + 'px'; }); };
    resizeHandler = handleResize;
    window.addEventListener('resize', resizeHandler);
    rightBox.addEventListener('click', (e) => { if (timeLeft <= 0 || found >= config.diffCount) return; const rect = rightBox.getBoundingClientRect(); const scaleX = 200 / rect.width, scaleY = 100 / rect.height; const clickX = (e.clientX - rect.left) * scaleX, clickY = (e.clientY - rect.top) * scaleY; let hit = false; currentHotspots.forEach(spot => { if (!spot.found && clickX >= spot.x && clickX <= spot.x + spot.w && clickY >= spot.y && clickY <= spot.y + spot.h) { spot.found = true; found++; hit = true; const markerX = (spot.x + spot.w/2) / 200 * rect.width, markerY = (spot.y + spot.h/2) / 100 * rect.height; const marker = document.createElement('div'); marker.className = 'found-marker'; marker.dataset.ox = spot.x; marker.dataset.oy = spot.y; marker.dataset.ow = spot.w; marker.dataset.oh = spot.h; marker.style.left = markerX + 'px'; marker.style.top = markerY + 'px'; marker.style.width = (spot.w / 200 * rect.width + 10) + 'px'; marker.style.height = (spot.h / 100 * rect.height + 10) + 'px'; rightBox.appendChild(marker); } }); if (hit) { rootEl.querySelector('#std-score').textContent = `找到: ${found} / ${config.diffCount}`; if (found >= config.diffCount) endGame(true); } else { showToast("點錯了！扣2秒"); timeLeft = Math.max(0, timeLeft - 2); rootEl.querySelector('#std-time').textContent = `時間: ${timeLeft}s`; } });
    const tick = () => { timeLeft--; const timeEl = rootEl.querySelector('#std-time'); if(timeEl) timeEl.textContent = `時間: ${timeLeft}s`; if (timeLeft <= 0) endGame(false); };
    timerId = setInterval(tick, 1000);
    const endGame = (win) => {
        if (timerId) {
            clearInterval(timerId);
            timerId = null;
        }
        if (resizeHandler) {
            window.removeEventListener('resize', resizeHandler);
            resizeHandler = null;
        }
        if (win) {
            showToast("成功找齊！");
            completeTimeoutId = setTimeout(() => {
                completeTimeoutId = null;
                if (options.onComplete) {
                    options.onComplete({
                        taskId: options.taskId,
                        gameId: 'spot_the_difference',
                        result: 'win',
                    });
                }
            }, 1000);
        } else {
            rootEl.innerHTML = `<div class="std-container"><h2>時間到！</h2><p>只找到 ${found} 處。</p><button class="std-btn" id="std-retry">重新挑戰</button></div>`;
            rootEl.querySelector('#std-retry').onclick = () => mount(rootEl, options);
        }
    };
}

export function unmount(rootEl) {
    if (timerId) {
        clearInterval(timerId);
        timerId = null;
    }
    if (completeTimeoutId) {
        clearTimeout(completeTimeoutId);
        completeTimeoutId = null;
    }
    if (resizeHandler) {
        window.removeEventListener('resize', resizeHandler);
        resizeHandler = null;
    }
    rootEl.innerHTML = '';
}
