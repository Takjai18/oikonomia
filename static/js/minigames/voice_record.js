/**
 * Voice recording minigame for Oikonomia camp tasks.
 * Record → preview → submit (requires min duration). Uses MediaRecorder API.
 */
let streams = [];
let mediaRecorder = null;
let tickTimer = null;

function clearRecordingRuntime() {
    if (tickTimer) {
        clearInterval(tickTimer);
        tickTimer = null;
    }
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
        try {
            mediaRecorder.stop();
        } catch (_e) { /* ignore */ }
    }
    mediaRecorder = null;
    streams.forEach((s) => {
        try {
            s.getTracks().forEach((t) => t.stop());
        } catch (_e) { /* ignore */ }
    });
    streams = [];
}

function pickMimeType() {
    const candidates = [
        "audio/webm;codecs=opus",
        "audio/webm",
        "audio/mp4",
        "audio/ogg;codecs=opus",
    ];
    if (typeof MediaRecorder === "undefined" || !MediaRecorder.isTypeSupported) {
        return "";
    }
    for (const t of candidates) {
        if (MediaRecorder.isTypeSupported(t)) return t;
    }
    return "";
}

function extForMime(mime) {
    if (!mime) return "webm";
    if (mime.includes("mp4")) return "m4a";
    if (mime.includes("ogg")) return "ogg";
    return "webm";
}

export function mount(rootEl, options) {
    clearRecordingRuntime();

    const config = {
        prompt: "請大聲讀出下面句子，並錄音提交。",
        script: "界線不會自己守住。",
        minSeconds: 3,
        maxSeconds: 60,
        hintVideo: null,
        hintImage: null,
        ...((options && options.config) || {}),
    };

    let chunks = [];
    let recordedBlob = null;
    let recordedUrl = null;
    let recording = false;
    let elapsedMs = 0;
    let submitted = false;

    const mimeType = pickMimeType();

    rootEl.innerHTML = `
        <style>
            .vr-box { font-family: system-ui, -apple-system, sans-serif; max-width: 420px; margin: 0 auto; padding: 14px; color: #e4e4e7; text-align: center; }
            .vr-title { font-size: 18px; font-weight: 700; margin: 0 0 8px; color: #fafafa; }
            .vr-prompt { font-size: 13px; color: #a1a1aa; margin-bottom: 12px; line-height: 1.45; }
            .vr-hint-media {
                margin: 0 auto 12px; max-width: 100%; border-radius: 12px; overflow: hidden;
                border: 1px solid #3f3f46; background: #18181b;
            }
            .vr-hint-media video, .vr-hint-media img {
                display: block; width: 100%; max-height: 220px; object-fit: contain; margin: 0 auto;
            }
            .vr-script {
                background: #27272a; border: 1px solid #3f3f46; border-radius: 12px;
                padding: 14px 12px; font-size: 18px; font-weight: 700; color: #fbbf24;
                margin-bottom: 14px; line-height: 1.4;
            }
            .vr-timer { font-size: 28px; font-weight: 700; font-variant-numeric: tabular-nums; margin: 8px 0 14px; color: #fafafa; }
            .vr-timer.live { color: #f87171; }
            .vr-row { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-bottom: 10px; }
            .vr-btn {
                flex: 1 1 120px; max-width: 180px; padding: 14px 12px; border: none; border-radius: 12px;
                font-size: 16px; font-weight: 700; cursor: pointer; touch-action: manipulation;
            }
            .vr-btn:disabled { opacity: 0.45; cursor: not-allowed; }
            .vr-rec { background: #dc2626; color: #fff; }
            .vr-stop { background: #e4e4e7; color: #18181b; }
            .vr-retry { background: #3f3f46; color: #fafafa; }
            .vr-submit { background: #16a34a; color: #fff; }
            .vr-audio { width: 100%; margin: 10px 0 6px; }
            .vr-hint { font-size: 12px; color: #71717a; line-height: 1.4; }
            .vr-status { font-size: 13px; color: #a1a1aa; min-height: 1.2em; margin-bottom: 8px; }
            .vr-dot {
                display: inline-block; width: 10px; height: 10px; border-radius: 50%;
                background: #71717a; margin-right: 6px; vertical-align: middle;
            }
            .vr-dot.on { background: #ef4444; box-shadow: 0 0 0 4px rgba(239,68,68,0.25); animation: vr-pulse 1s infinite; }
            @keyframes vr-pulse { 50% { opacity: 0.5; } }
        </style>
        <div class="vr-box">
            <h3 class="vr-title">錄音任務</h3>
            <p class="vr-prompt">${escapeHtml(config.prompt)}</p>
            ${config.hintVideo ? `<div class="vr-hint-media"><video src="${escapeHtml(config.hintVideo)}" controls playsinline preload="metadata"></video></div>` : ""}
            ${!config.hintVideo && config.hintImage ? `<div class="vr-hint-media"><img src="${escapeHtml(config.hintImage)}" alt="任務提示" /></div>` : ""}
            <div class="vr-script">${escapeHtml(config.script)}</div>
            <div class="vr-status" id="vr-status"><span class="vr-dot" id="vr-dot"></span>準備就緒</div>
            <div class="vr-timer" id="vr-timer">0:00</div>
            <div class="vr-row">
                <button type="button" class="vr-btn vr-rec" id="vr-start">🎙️ 開始錄音</button>
                <button type="button" class="vr-btn vr-stop" id="vr-stop" disabled>停止</button>
            </div>
            <div class="vr-row">
                <button type="button" class="vr-btn vr-retry" id="vr-retry" disabled>重錄</button>
                <button type="button" class="vr-btn vr-submit" id="vr-submit" disabled>提交任務</button>
            </div>
            <audio class="vr-audio" id="vr-playback" controls playsinline style="display:none"></audio>
            <p class="vr-hint">最少錄 ${config.minSeconds} 秒，最多 ${config.maxSeconds} 秒。請允許瀏覽器使用麥克風（建議用 Safari / Chrome，唔好用 WhatsApp 內置瀏覽器）。</p>
        </div>
    `;

    const elStatus = rootEl.querySelector("#vr-status");
    const elDot = rootEl.querySelector("#vr-dot");
    const elTimer = rootEl.querySelector("#vr-timer");
    const btnStart = rootEl.querySelector("#vr-start");
    const btnStop = rootEl.querySelector("#vr-stop");
    const btnRetry = rootEl.querySelector("#vr-retry");
    const btnSubmit = rootEl.querySelector("#vr-submit");
    const playback = rootEl.querySelector("#vr-playback");

    function setStatus(text, live) {
        elStatus.innerHTML = `<span class="vr-dot${live ? " on" : ""}" id="vr-dot"></span>${text}`;
        elTimer.classList.toggle("live", !!live);
    }

    function formatMs(ms) {
        const s = Math.floor(ms / 1000);
        const m = Math.floor(s / 60);
        const r = s % 60;
        return `${m}:${String(r).padStart(2, "0")}`;
    }

    function revokeUrl() {
        if (recordedUrl) {
            URL.revokeObjectURL(recordedUrl);
            recordedUrl = null;
        }
    }

    function updateTimerDisplay() {
        elTimer.textContent = formatMs(elapsedMs);
    }

    function stopTracks() {
        streams.forEach((s) => {
            try {
                s.getTracks().forEach((t) => t.stop());
            } catch (_e) { /* ignore */ }
        });
        streams = [];
    }

    async function startRecording() {
        if (recording || submitted) return;
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            setStatus("此裝置／瀏覽器唔支援錄音");
            return;
        }
        if (typeof MediaRecorder === "undefined") {
            setStatus("此瀏覽器唔支援 MediaRecorder");
            return;
        }

        revokeUrl();
        recordedBlob = null;
        chunks = [];
        elapsedMs = 0;
        updateTimerDisplay();
        playback.style.display = "none";
        playback.removeAttribute("src");
        btnSubmit.disabled = true;
        btnRetry.disabled = true;

        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            streams.push(stream);
            const opts = mimeType ? { mimeType } : undefined;
            mediaRecorder = opts ? new MediaRecorder(stream, opts) : new MediaRecorder(stream);
            mediaRecorder.ondataavailable = (e) => {
                if (e.data && e.data.size > 0) chunks.push(e.data);
            };
            mediaRecorder.onstop = () => {
                recording = false;
                stopTracks();
                if (tickTimer) {
                    clearInterval(tickTimer);
                    tickTimer = null;
                }
                const type = mimeType || (chunks[0] && chunks[0].type) || "audio/webm";
                recordedBlob = new Blob(chunks, { type });
                revokeUrl();
                recordedUrl = URL.createObjectURL(recordedBlob);
                playback.src = recordedUrl;
                playback.style.display = "block";

                const secs = elapsedMs / 1000;
                btnStart.disabled = false;
                btnStop.disabled = true;
                btnRetry.disabled = false;

                if (secs < config.minSeconds) {
                    setStatus(`錄得太短（${secs.toFixed(1)}s），至少要 ${config.minSeconds} 秒，請重錄`);
                    btnSubmit.disabled = true;
                    recordedBlob = null;
                } else {
                    setStatus(`已錄好 ${secs.toFixed(1)} 秒，可試聽後提交`);
                    btnSubmit.disabled = false;
                }
            };

            mediaRecorder.start(250);
            recording = true;
            btnStart.disabled = true;
            btnStop.disabled = false;
            setStatus("錄音中…", true);
            const started = Date.now();
            tickTimer = setInterval(() => {
                elapsedMs = Date.now() - started;
                updateTimerDisplay();
                if (elapsedMs >= config.maxSeconds * 1000) {
                    stopRecording();
                }
            }, 200);
        } catch (err) {
            console.error(err);
            setStatus("無法開啟麥克風（請檢查權限）");
            btnStart.disabled = false;
            btnStop.disabled = true;
        }
    }

    function stopRecording() {
        if (!recording || !mediaRecorder) return;
        try {
            if (mediaRecorder.state !== "inactive") mediaRecorder.stop();
        } catch (_e) { /* ignore */ }
    }

    btnStart.onclick = () => startRecording();
    btnStop.onclick = () => stopRecording();
    btnRetry.onclick = () => {
        if (recording) stopRecording();
        revokeUrl();
        recordedBlob = null;
        chunks = [];
        elapsedMs = 0;
        updateTimerDisplay();
        playback.style.display = "none";
        btnSubmit.disabled = true;
        btnRetry.disabled = true;
        btnStart.disabled = false;
        setStatus("準備就緒");
    };

    btnSubmit.onclick = () => {
        if (submitted || !recordedBlob) return;
        const secs = elapsedMs / 1000;
        if (secs < config.minSeconds) {
            setStatus(`最少要錄 ${config.minSeconds} 秒`);
            return;
        }
        submitted = true;
        btnSubmit.disabled = true;
        btnStart.disabled = true;
        btnStop.disabled = true;
        btnRetry.disabled = true;
        setStatus("提交中…");

        const ext = extForMime(recordedBlob.type || mimeType);
        const filename = `recording.${ext}`;
        if (options && typeof options.onComplete === "function") {
            options.onComplete({
                taskId: options.taskId,
                gameId: "voice_record",
                result: "win",
                durationSec: Math.round(secs * 10) / 10,
                audioBlob: recordedBlob,
                audioFilename: filename,
            });
        }
    };
}

export function unmount(rootEl) {
    clearRecordingRuntime();
    const playback = rootEl && rootEl.querySelector && rootEl.querySelector("#vr-playback");
    if (playback && playback.src && playback.src.startsWith("blob:")) {
        try {
            URL.revokeObjectURL(playback.src);
        } catch (_e) { /* ignore */ }
    }
    if (rootEl) rootEl.innerHTML = "";
}

function escapeHtml(s) {
    return String(s || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}
