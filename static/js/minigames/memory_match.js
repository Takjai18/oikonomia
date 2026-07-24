/**
 * Memory match — 3 waves (60s / 50s / 45s), team half must fully clear all 3.
 */
let timerId = null;
let pollTimer = null;
let lockBoard = false;
let firstCard = null;
let matched = 0;
let timeLeft = 0;
let unmounted = true;
let completedFired = false;

const EMOJI_POOL = [
  '🔥', '❄️', '🐐', '🦅', '🗡️', '🛡️', '💎', '🗝️',
  '🌲', '⛰️', '🩸', '🌙', '⚡', '🪞', '📜', '🎭',
];

const DEFAULT_WAVES = [60, 50, 45];

async function api(path, opts = {}) {
  const res = await fetch(path, {
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
    ...opts,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data.success === false) {
    const err = new Error(data.error || '請求失敗');
    err.data = data;
    throw err;
  }
  return data;
}

function cleanupTimers() {
  if (timerId) {
    clearInterval(timerId);
    timerId = null;
  }
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

function shuffle(arr) {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

export function mount(rootEl, options) {
  unmount(rootEl);
  unmounted = false;
  completedFired = false;

  const taskId = options.taskId;
  const config = {
    pairs: 8,
    previewSec: 2,
    waveTimesSec: DEFAULT_WAVES,
    ...(options.config || {}),
  };
  const pairs = Math.max(4, Math.min(12, parseInt(config.pairs, 10) || 8));
  let waveTimes = Array.isArray(config.waveTimesSec) ? config.waveTimesSec.map((x) => parseInt(x, 10) || 45) : DEFAULT_WAVES;
  if (waveTimes.length < 3) waveTimes = DEFAULT_WAVES;

  let teamState = null;
  let localWave = 0; // 0-based index of current wave being played (0,1,2)
  let playing = false;

  rootEl.innerHTML = `
    <style>
      .mm-wrap { max-width: 420px; margin: 0 auto; font-family: system-ui, sans-serif; color:#e4e4e7; }
      .mm-title { font-size:1.1rem; font-weight:800; color:#fbbf24; margin-bottom:6px; }
      .mm-hint { font-size:12px; color:#a1a1aa; line-height:1.45; margin-bottom:10px; }
      .mm-hud { display:flex; justify-content:space-between; font-weight:700; margin-bottom:10px; flex-wrap:wrap; gap:6px; }
      .mm-grid { display:grid; gap:8px; }
      .mm-card {
        aspect-ratio: 1; border-radius: 12px; border: 2px solid #3f3f46;
        background: #27272a; color: transparent; font-size: 1.5rem;
        display:flex; align-items:center; justify-content:center;
        cursor:pointer; user-select:none; -webkit-tap-highlight-color:transparent;
      }
      .mm-card.flipped, .mm-card.matched {
        background: #18181b; color: #fafafa; border-color: #a1a1aa;
      }
      .mm-card.matched { border-color: #34d399; background: #052e1a; }
      .mm-msg { text-align:center; margin-top:10px; color:#a1a1aa; font-size:13px; }
      .mm-btn {
        display:block; width:100%; margin-top:10px; padding:14px; border:none;
        border-radius:12px; background:#d97706; color:#18181b; font-weight:800; font-size:15px; cursor:pointer;
      }
      .mm-btn.ghost { background:#3f3f46; color:#e4e4e7; }
      .mm-btn:disabled { opacity:0.45; }
      .mm-chip { font-size:11px; padding:4px 8px; border-radius:999px; border:1px solid #52525b; background:#27272a; display:inline-block; margin:2px; }
      .mm-chip.on { border-color:#34d399; color:#6ee7b7; }
      .mm-chip.won { border-color:#22c55e; background:#052e1a; color:#86efac; }
      .mm-card-box { background:#18181b; border:1px solid #3f3f46; border-radius:16px; padding:12px; }
    </style>
    <div class="mm-wrap">
      <div class="mm-title">搜尋 Iggy · 記憶配對</div>
      <p class="mm-hint">共 3 輪：60 秒 → 50 秒 → 45 秒。每輪開始有 2 秒預覽牌面。你需連續過三關；全隊至少一半人完成三輪才算任務成功。</p>
      <div id="mm-root"></div>
    </div>
  `;
  const host = rootEl.querySelector('#mm-root');

  function membersLine(st) {
    const need = st.need_winners || 1;
    const win = st.winners_count || 0;
    const chips = (st.members || []).map((m) => {
      let cls = m.online ? 'on' : '';
      if (m.won) cls = 'won';
      const wave = m.won ? '✓三輪' : '';
      return `<span class="mm-chip ${cls}">${m.display_name || m.squad_id} ${wave}</span>`;
    }).join('');
    return `<div style="margin:8px 0">${chips || ''}</div>
      <div class="mm-msg">全隊進度：${win} / ${need} 人完成三輪（需半隊）</div>`;
  }

  function showLobby(st) {
    playing = false;
    host.innerHTML = `
      <div class="mm-card-box">
        <div class="mm-msg">大廳 — 至少半隊同時進入後開始</div>
        ${membersLine(st)}
        <button type="button" class="mm-btn" id="mm-start">開始配對挑戰</button>
        <button type="button" class="mm-btn ghost" id="mm-refresh">重新整理</button>
      </div>`;
    host.querySelector('#mm-start')?.addEventListener('click', async () => {
      try {
        const next = await api('/api/team_minigame/start', {
          method: 'POST',
          body: JSON.stringify({ task_id: taskId }),
        });
        teamState = next;
        if (next.wave_times) waveTimes = next.wave_times;
        beginLocalWaves(next);
      } catch (e) {
        alert(e.message || '無法開始');
      }
    });
    host.querySelector('#mm-refresh')?.addEventListener('click', () => tick());
  }

  function showTeamWon(st) {
    host.innerHTML = `
      <div class="mm-card-box" style="text-align:center">
        <div style="font-size:2rem">🎉</div>
        <h2 style="color:#34d399">半隊完成搜尋！</h2>
        ${membersLine(st)}
      </div>`;
    if (options.onComplete && !completedFired) {
      completedFired = true;
      options.onComplete({
        taskId,
        gameId: 'memory_match',
        result: 'win',
        teamSession: true,
      });
    }
    cleanupTimers();
  }

  function beginLocalWaves(st) {
    teamState = st;
    localWave = Math.min(2, Math.max(0, parseInt(st.my_wave, 10) || 0));
    if (st.my_won || st.status === 'won') {
      if (st.status === 'won') showTeamWon(st);
      else showWaitingForTeam(st);
      return;
    }
    startWave(localWave);
  }

  function showWaitingForTeam(st) {
    playing = false;
    host.innerHTML = `
      <div class="mm-card-box" style="text-align:center">
        <h2 style="color:#6ee7b7">你已完成三輪！</h2>
        <p class="mm-msg">等待隊友… 需半隊完成才可交任務</p>
        ${membersLine(st)}
      </div>`;
  }

  function startWave(waveIndex) {
    if (unmounted) return;
    playing = true;
    lockBoard = false;
    firstCard = null;
    matched = 0;
    if (timerId) {
      clearInterval(timerId);
      timerId = null;
    }

    const limit = waveTimes[waveIndex] || 45;
    timeLeft = limit;
    const icons = EMOJI_POOL.slice(0, pairs);
    const deck = shuffle([...icons, ...icons]);
    const cols = pairs <= 6 ? 3 : 4;
    const waveLabel = waveIndex + 1;

    host.innerHTML = `
      <div class="mm-card-box">
        <div class="mm-hud">
          <span>第 ${waveLabel} / 3 輪</span>
          <span id="mm-time">時間 ${timeLeft}s</span>
          <span id="mm-score">配對 0 / ${pairs}</span>
        </div>
        <div class="mm-grid" id="mm-grid" style="grid-template-columns: repeat(${cols}, 1fr)"></div>
        <p class="mm-msg">限時 ${limit} 秒 · 配錯扣 3 秒 · 連續過三關</p>
        <div id="mm-team-mini"></div>
      </div>`;

    const mini = host.querySelector('#mm-team-mini');
    if (mini && teamState) mini.innerHTML = membersLine(teamState);

    const grid = host.querySelector('#mm-grid');
    deck.forEach((icon, idx) => {
      const card = document.createElement('button');
      card.type = 'button';
      card.className = 'mm-card';
      card.dataset.icon = icon;
      card.dataset.idx = String(idx);
      card.textContent = '?';
      card.addEventListener('click', () => onFlip(card));
      grid.appendChild(card);
    });

    const previewSec = Math.max(0, parseInt(config.previewSec, 10) || 0);
    if (previewSec > 0) {
      lockBoard = true;
      host.querySelectorAll('.mm-card').forEach((c) => {
        c.classList.add('flipped');
        c.textContent = c.dataset.icon;
      });
      setTimeout(() => {
        if (unmounted || !playing) return;
        host.querySelectorAll('.mm-card').forEach((c) => {
          if (!c.classList.contains('matched')) {
            c.classList.remove('flipped');
            c.textContent = '?';
          }
        });
        lockBoard = false;
      }, previewSec * 1000);
    }

    timerId = setInterval(() => {
      if (!playing) return;
      timeLeft -= 1;
      const el = host.querySelector('#mm-time');
      if (el) el.textContent = `時間 ${timeLeft}s`;
      if (timeLeft <= 0) endWave(false);
    }, 1000);
  }

  function onFlip(card) {
    if (!playing || lockBoard || timeLeft <= 0) return;
    if (card.classList.contains('flipped') || card.classList.contains('matched')) return;

    card.classList.add('flipped');
    card.textContent = card.dataset.icon;

    if (!firstCard) {
      firstCard = card;
      return;
    }
    if (firstCard === card) return;

    lockBoard = true;
    const a = firstCard;
    const b = card;
    if (a.dataset.icon === b.dataset.icon) {
      a.classList.add('matched');
      b.classList.add('matched');
      matched += 1;
      const score = host.querySelector('#mm-score');
      if (score) score.textContent = `配對 ${matched} / ${pairs}`;
      firstCard = null;
      lockBoard = false;
      if (matched >= pairs) endWave(true);
    } else {
      timeLeft = Math.max(0, timeLeft - 3);
      const el = host.querySelector('#mm-time');
      if (el) el.textContent = `時間 ${timeLeft}s`;
      setTimeout(() => {
        a.classList.remove('flipped');
        b.classList.remove('flipped');
        a.textContent = '?';
        b.textContent = '?';
        firstCard = null;
        lockBoard = false;
        if (timeLeft <= 0) endWave(false);
      }, 550);
    }
  }

  async function endWave(win) {
    if (!playing) return;
    playing = false;
    if (timerId) {
      clearInterval(timerId);
      timerId = null;
    }
    const waveNum = localWave + 1;
    try {
      teamState = await api('/api/team_minigame/memory_wave', {
        method: 'POST',
        body: JSON.stringify({
          task_id: taskId,
          wave: waveNum,
          success: !!win,
        }),
      });
    } catch (e) {
      host.innerHTML = `
        <div class="mm-card-box" style="text-align:center">
          <p class="mm-msg" style="color:#f87171">${e.message || '同步失敗'}</p>
          <button type="button" class="mm-btn" id="mm-retry">重試本輪</button>
        </div>`;
      host.querySelector('#mm-retry')?.addEventListener('click', () => startWave(localWave));
      return;
    }

    if (teamState.status === 'won') {
      showTeamWon(teamState);
      return;
    }

    if (win) {
      localWave = waveNum; // completed this wave
      if (waveNum >= 3 || teamState.my_won) {
        showWaitingForTeam(teamState);
        return;
      }
      host.innerHTML = `
        <div class="mm-card-box" style="text-align:center">
          <h2 style="color:#34d399">第 ${waveNum} 輪通過！</h2>
          <p class="mm-msg">下一輪限時 ${waveTimes[waveNum] || 45} 秒</p>
          ${membersLine(teamState)}
          <button type="button" class="mm-btn" id="mm-next">進入第 ${waveNum + 1} 輪</button>
        </div>`;
      host.querySelector('#mm-next')?.addEventListener('click', () => startWave(localWave));
    } else {
      host.innerHTML = `
        <div class="mm-card-box" style="text-align:center">
          <h2 style="color:#f87171">第 ${waveNum} 輪時間到</h2>
          <p class="mm-msg">配對 ${matched} / ${pairs} · 限時 ${waveTimes[localWave]} 秒</p>
          ${membersLine(teamState)}
          <button type="button" class="mm-btn" id="mm-retry">重試本輪</button>
        </div>`;
      host.querySelector('#mm-retry')?.addEventListener('click', () => startWave(localWave));
    }
  }

  async function tick() {
    if (unmounted) return;
    try {
      const st = await api(`/api/team_minigame/status?task_id=${encodeURIComponent(taskId)}`);
      teamState = st;
      if (st.wave_times) waveTimes = st.wave_times;
      if (st.status === 'won') {
        showTeamWon(st);
        return;
      }
      if (st.status === 'lobby') {
        if (!playing) showLobby(st);
        return;
      }
      if (st.status === 'playing') {
        if (st.my_won && !playing) {
          showWaitingForTeam(st);
          return;
        }
        // update mini team line while playing
        const mini = host.querySelector('#mm-team-mini');
        if (mini && playing) mini.innerHTML = membersLine(st);
        if (!playing && !st.my_won && !host.querySelector('#mm-grid') && !host.querySelector('#mm-next')) {
          beginLocalWaves(st);
        }
      }
    } catch (_) {}
  }

  async function join() {
    host.innerHTML = `<div class="mm-msg">連接全隊房間…</div>`;
    const st = await api('/api/team_minigame/join', {
      method: 'POST',
      body: JSON.stringify({ task_id: taskId }),
    });
    teamState = st;
    if (st.wave_times) waveTimes = st.wave_times;
    if (st.status === 'won') {
      showTeamWon(st);
    } else if (st.status === 'playing') {
      beginLocalWaves(st);
    } else {
      showLobby(st);
    }
    cleanupTimers();
    pollTimer = setInterval(tick, 1200);
  }

  join().catch((e) => {
    host.innerHTML = `<div class="mm-msg" style="color:#f87171">${e.message || '加入失敗'}</div>`;
  });
}

export function unmount(rootEl) {
  unmounted = true;
  cleanupTimers();
  lockBoard = false;
  firstCard = null;
  if (rootEl) rootEl.innerHTML = '';
}
