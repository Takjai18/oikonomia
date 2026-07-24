/**
 * Team whack-a-mole — 60s, hit 45 moles. Team wins when ≥2 members succeed.
 */
let pollTimer = null;
let gameTimer = null;
let spawnTimer = null;
let unmounted = true;
let completedFired = false;

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

function stopAll() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
  if (gameTimer) {
    clearInterval(gameTimer);
    gameTimer = null;
  }
  if (spawnTimer) {
    clearTimeout(spawnTimer);
    spawnTimer = null;
  }
}

export function mount(rootEl, options) {
  unmount(rootEl);
  unmounted = false;
  completedFired = false;

  const taskId = options.taskId;
  const config = options.config || {};
  let timeLimit = parseInt(config.timeLimitSec, 10) || 60;
  let targetHits = parseInt(config.targetHits, 10) || 45;
  let needWinners = parseInt(config.minWinners, 10) || 2;

  let teamState = null;
  let playing = false;
  let hits = 0;
  let timeLeft = timeLimit;
  let activeHole = -1;
  let moleToken = 0;

  rootEl.innerHTML = `
    <style>
      .wm-wrap { max-width: 420px; margin: 0 auto; font-family: system-ui,sans-serif; color:#e4e4e7; }
      .wm-title { font-size:1.15rem; font-weight:800; color:#fbbf24; margin-bottom:6px; }
      .wm-hint { font-size:12px; color:#a1a1aa; line-height:1.45; margin-bottom:10px; }
      .wm-card { background:#18181b; border:1px solid #3f3f46; border-radius:16px; padding:14px; }
      .wm-hud { display:flex; justify-content:space-between; font-weight:800; margin-bottom:12px; gap:8px; flex-wrap:wrap; }
      .wm-grid {
        display:grid; grid-template-columns: repeat(3, 1fr); gap:10px;
        touch-action: manipulation;
      }
      .wm-hole {
        aspect-ratio: 1; border-radius: 16px; border: 2px solid #3f3f46;
        background: #0c0c0e; position: relative; overflow: hidden;
        cursor: pointer; -webkit-tap-highlight-color: transparent;
        user-select: none;
      }
      .wm-hole.active {
        border-color: #d97706; background: #1c1410;
      }
      .wm-mole {
        position:absolute; left:50%; bottom:8%; transform: translateX(-50%) translateY(120%);
        width: 62%; height: 62%; border-radius: 50% 50% 40% 40%;
        background: linear-gradient(180deg, #b45309, #78350f);
        box-shadow: inset 0 -6px 0 rgba(0,0,0,.25);
        transition: transform .12s ease-out;
        display:flex; align-items:center; justify-content:center;
        font-size: 1.4rem;
      }
      .wm-hole.active .wm-mole { transform: translateX(-50%) translateY(0); }
      .wm-btn {
        width:100%; min-height:48px; margin-top:10px; border:none; border-radius:14px;
        font-weight:800; font-size:15px; cursor:pointer; background:#d97706; color:#18181b;
      }
      .wm-btn.ghost { background:#3f3f46; color:#e4e4e7; }
      .wm-btn:disabled { opacity:0.45; }
      .wm-chip {
        font-size:11px; padding:4px 8px; border-radius:999px; border:1px solid #52525b;
        background:#27272a; display:inline-block; margin:2px;
      }
      .wm-chip.on { border-color:#34d399; color:#6ee7b7; }
      .wm-chip.won { border-color:#22c55e; background:#052e1a; color:#86efac; }
      .wm-msg { text-align:center; font-size:13px; color:#a1a1aa; margin:8px 0; }
    </style>
    <div class="wm-wrap">
      <div class="wm-title">Act 1 Mission 2 · 打地鼠</div>
      <p class="wm-hint">全隊一起玩。每人 60 秒內打中 45 隻；至少 2 人通關即完成任務。失敗可重試。</p>
      <div id="wm-body"></div>
    </div>
  `;
  const body = rootEl.querySelector('#wm-body');

  function membersLine(st) {
    const need = st.need_winners || needWinners;
    const win = st.winners_count || 0;
    const chips = (st.members || []).map((m) => {
      let cls = m.online ? 'on' : '';
      if (m.won) cls = 'won';
      const extra = m.won ? ' ✓' : '';
      return `<span class="wm-chip ${cls}">${m.display_name || m.squad_id}${extra}</span>`;
    }).join('');
    return `<div style="margin:8px 0">${chips || ''}</div>
      <div class="wm-msg">通關人數 ${win} / ${need}</div>`;
  }

  function showLobby(st) {
    playing = false;
    body.innerHTML = `
      <div class="wm-card">
        <div class="wm-msg">大廳 — 請隊員同時打開此任務</div>
        ${membersLine(st)}
        <button type="button" class="wm-btn" id="wm-start">開始打地鼠</button>
        <button type="button" class="wm-btn ghost" id="wm-refresh">重新整理</button>
      </div>`;
    body.querySelector('#wm-start')?.addEventListener('click', async () => {
      try {
        const next = await api('/api/team_minigame/start', {
          method: 'POST',
          body: JSON.stringify({ task_id: taskId }),
        });
        teamState = next;
        applyConfig(next);
        if (next.my_won) showWaiting(next);
        else startLocalRun();
      } catch (e) {
        alert(e.message || '無法開始');
      }
    });
    body.querySelector('#wm-refresh')?.addEventListener('click', () => tick());
  }

  function applyConfig(st) {
    if (st.time_limit_sec) timeLimit = st.time_limit_sec;
    if (st.target_hits) targetHits = st.target_hits;
    if (st.need_winners) needWinners = st.need_winners;
  }

  function showTeamWon(st) {
    body.innerHTML = `
      <div class="wm-card" style="text-align:center">
        <div style="font-size:2rem">🎉</div>
        <h2 style="color:#34d399">全隊通過封鎖線！</h2>
        ${membersLine(st)}
      </div>`;
    if (options.onComplete && !completedFired) {
      completedFired = true;
      options.onComplete({
        taskId,
        gameId: 'whack_a_mole',
        result: 'win',
        teamSession: true,
      });
    }
    stopAll();
  }

  function showWaiting(st) {
    playing = false;
    body.innerHTML = `
      <div class="wm-card" style="text-align:center">
        <h2 style="color:#6ee7b7">你已通關！</h2>
        <p class="wm-msg">等待隊友（需至少 ${st.need_winners || needWinners} 人通關）</p>
        ${membersLine(st)}
      </div>`;
  }

  function startLocalRun() {
    if (unmounted) return;
    playing = true;
    hits = 0;
    timeLeft = timeLimit;
    activeHole = -1;
    moleToken += 1;

    body.innerHTML = `
      <div class="wm-card">
        <div class="wm-hud">
          <span id="wm-time">⏱ ${timeLeft}s</span>
          <span id="wm-hits">🐹 ${hits} / ${targetHits}</span>
        </div>
        <div class="wm-grid" id="wm-grid"></div>
        <div id="wm-team-mini"></div>
      </div>`;
    const mini = body.querySelector('#wm-team-mini');
    if (mini && teamState) mini.innerHTML = membersLine(teamState);

    const grid = body.querySelector('#wm-grid');
    for (let i = 0; i < 9; i++) {
      const hole = document.createElement('button');
      hole.type = 'button';
      hole.className = 'wm-hole';
      hole.dataset.idx = String(i);
      hole.innerHTML = `<div class="wm-mole">🐹</div>`;
      hole.addEventListener('pointerdown', (ev) => {
        ev.preventDefault();
        onWhack(i);
      });
      grid.appendChild(hole);
    }

    gameTimer = setInterval(() => {
      if (!playing) return;
      timeLeft -= 1;
      const el = body.querySelector('#wm-time');
      if (el) el.textContent = `⏱ ${timeLeft}s`;
      if (timeLeft <= 0) endLocalRun(false);
    }, 1000);

    scheduleMole();
  }

  /** Last 30s: speed ramps up to ~2× (shorter spawn delay + uptime). */
  function speedFactor() {
    if (timeLeft > 30) return 1;
    // timeLeft 30 → 1.0x, timeLeft 0 → 2.0x
    const t = Math.max(0, Math.min(30, timeLeft));
    return 1 + (30 - t) / 30; // 1.0 … 2.0
  }

  function scheduleMole() {
    if (!playing || unmounted) return;
    // Hide current
    setActive(-1);
    const sp = speedFactor();
    const delay = (180 + Math.random() * 220) / sp;
    spawnTimer = setTimeout(() => {
      if (!playing || unmounted) return;
      let next = Math.floor(Math.random() * 9);
      if (next === activeHole) next = (next + 1 + Math.floor(Math.random() * 8)) % 9;
      setActive(next);
      const upMs = (480 + Math.random() * 320) / sp;
      const token = ++moleToken;
      spawnTimer = setTimeout(() => {
        if (token !== moleToken || !playing) return;
        setActive(-1);
        scheduleMole();
      }, upMs);
    }, delay);
  }

  function setActive(idx) {
    activeHole = idx;
    body.querySelectorAll('.wm-hole').forEach((el) => {
      const i = parseInt(el.dataset.idx, 10);
      el.classList.toggle('active', i === idx);
    });
  }

  function onWhack(idx) {
    if (!playing || idx !== activeHole) return;
    hits += 1;
    const el = body.querySelector('#wm-hits');
    if (el) el.textContent = `🐹 ${hits} / ${targetHits}`;
    // Immediate next mole for pace
    moleToken += 1;
    setActive(-1);
    if (hits >= targetHits) {
      endLocalRun(true);
      return;
    }
    scheduleMole();
  }

  async function endLocalRun(win) {
    if (!playing) return;
    playing = false;
    if (gameTimer) {
      clearInterval(gameTimer);
      gameTimer = null;
    }
    if (spawnTimer) {
      clearTimeout(spawnTimer);
      spawnTimer = null;
    }
    setActive(-1);

    body.innerHTML = `
      <div class="wm-card" style="text-align:center">
        <div class="wm-msg">同步結果中…（${hits} 擊）</div>
      </div>`;

    try {
      teamState = await api('/api/team_minigame/whack_result', {
        method: 'POST',
        body: JSON.stringify({
          task_id: taskId,
          hits,
          success: !!win,
        }),
      });
    } catch (e) {
      body.innerHTML = `
        <div class="wm-card" style="text-align:center">
          <p class="wm-msg" style="color:#f87171">${e.message || '同步失敗'}</p>
          <button type="button" class="wm-btn" id="wm-retry">重試</button>
        </div>`;
      body.querySelector('#wm-retry')?.addEventListener('click', () => startLocalRun());
      return;
    }

    if (teamState.status === 'won') {
      showTeamWon(teamState);
      return;
    }
    if (teamState.my_won || win) {
      showWaiting(teamState);
      return;
    }
    body.innerHTML = `
      <div class="wm-card" style="text-align:center">
        <h2 style="color:#f87171">時間到</h2>
        <p class="wm-msg">打中 ${hits} / ${targetHits} 隻 · 再試一次！</p>
        ${membersLine(teamState)}
        <button type="button" class="wm-btn" id="wm-retry">再打一局</button>
      </div>`;
    body.querySelector('#wm-retry')?.addEventListener('click', () => startLocalRun());
  }

  async function tick() {
    if (unmounted) return;
    try {
      const st = await api(`/api/team_minigame/status?task_id=${encodeURIComponent(taskId)}`);
      teamState = st;
      applyConfig(st);
      if (st.status === 'won') {
        showTeamWon(st);
        return;
      }
      if (st.status === 'lobby' && !playing) {
        showLobby(st);
        return;
      }
      if (st.status === 'playing') {
        if (st.my_won && !playing) {
          showWaiting(st);
          return;
        }
        const mini = body.querySelector('#wm-team-mini');
        if (mini && playing) mini.innerHTML = membersLine(st);
        if (!playing && !st.my_won && !body.querySelector('#wm-grid') && !body.querySelector('#wm-retry')) {
          startLocalRun();
        }
      }
    } catch (_) {}
  }

  async function join() {
    body.innerHTML = `<div class="wm-msg">連接全隊房間…</div>`;
    const st = await api('/api/team_minigame/join', {
      method: 'POST',
      body: JSON.stringify({ task_id: taskId }),
    });
    teamState = st;
    applyConfig(st);
    if (st.status === 'won') showTeamWon(st);
    else if (st.status === 'playing') {
      if (st.my_won) showWaiting(st);
      else startLocalRun();
    } else showLobby(st);

    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(tick, 1200);
  }

  join().catch((e) => {
    body.innerHTML = `<div class="wm-msg" style="color:#f87171">${e.message || '加入失敗'}</div>`;
  });
}

export function unmount(rootEl) {
  unmounted = true;
  stopAll();
  if (rootEl) rootEl.innerHTML = '';
}
