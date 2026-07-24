/**
 * Team flash memory — all members play together.
 * Server shows a short code 0.5–1s; each player types it.
 * 10 rounds; each round needs ≥2 correct (or all if team < 2).
 */
let pollTimer = null;
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

function stopPoll() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

export function mount(rootEl, options) {
  unmount(rootEl);
  unmounted = false;
  completedFired = false;
  const taskId = options.taskId;
  const config = options.config || {};
  let lastPhase = null;
  let submitting = false;

  rootEl.innerHTML = `
    <style>
      .fm-wrap { max-width: 420px; margin: 0 auto; font-family: system-ui,sans-serif; color:#e4e4e7; }
      .fm-title { font-size:1.15rem; font-weight:800; color:#fbbf24; margin-bottom:6px; }
      .fm-hint { font-size:12px; color:#a1a1aa; line-height:1.45; margin-bottom:12px; }
      .fm-card { background:#18181b; border:1px solid #3f3f46; border-radius:16px; padding:14px; margin-bottom:10px; }
      .fm-code {
        font-size:2.2rem; font-weight:900; letter-spacing:0.25em; text-align:center;
        font-family: ui-monospace, monospace; color:#fafafa; min-height:3rem;
        display:flex; align-items:center; justify-content:center;
      }
      .fm-code.hidden-code { color:transparent; text-shadow:0 0 12px rgba(250,250,250,0.15); }
      .fm-members { display:flex; flex-wrap:wrap; gap:6px; margin-top:8px; }
      .fm-chip {
        font-size:11px; padding:4px 8px; border-radius:999px; border:1px solid #52525b;
        background:#27272a;
      }
      .fm-chip.on { border-color:#34d399; color:#6ee7b7; }
      .fm-chip.off { opacity:0.5; }
      .fm-chip.ok { border-color:#34d399; background:#052e1a; color:#6ee7b7; }
      .fm-btn {
        width:100%; min-height:48px; border:none; border-radius:14px; font-weight:800;
        font-size:15px; cursor:pointer; margin-top:8px;
      }
      .fm-btn.primary { background:#d97706; color:#18181b; }
      .fm-btn.ghost { background:#3f3f46; color:#e4e4e7; }
      .fm-btn:disabled { opacity:0.45; cursor:not-allowed; }
      .fm-input {
        width:100%; box-sizing:border-box; padding:14px; border-radius:12px;
        border:2px solid #52525b; background:#09090b; color:#fafafa;
        font-size:1.4rem; font-weight:700; letter-spacing:0.2em; text-align:center;
        font-family: ui-monospace, monospace; text-transform:uppercase;
      }
      .fm-status { text-align:center; font-size:13px; color:#a1a1aa; margin:8px 0; }
      .fm-toast { text-align:center; font-weight:700; margin:8px 0; }
    </style>
    <div class="fm-wrap">
      <div class="fm-title">潛行下山 · 記憶閃光</div>
      <p class="fm-hint">全隊必須同時參與。螢幕會短暫顯示一串數字／英數，記住後輸入。共 10 輪，每輪至少 2 人答對；字串會越來越長。</p>
      <div id="fm-body"></div>
    </div>
  `;

  const body = rootEl.querySelector('#fm-body');

  function membersHtml(st) {
    const list = st.members || [];
    if (!list.length) return '<div class="fm-status">等待隊員加入…</div>';
    return `<div class="fm-members">${list.map((m) => {
      const cls = m.online ? 'on' : 'off';
      return `<span class="fm-chip ${cls}">${m.online ? '●' : '○'} ${m.display_name || m.squad_id}${m.answered ? ' ✓' : ''}</span>`;
    }).join('')}</div>
    <div class="fm-status">在線 ${st.online_count || 0} / 應到 ${st.expected_count || '?'}</div>`;
  }

  function render(st) {
    if (unmounted || !body) return;
    const status = st.status;

    if (status === 'lobby') {
      body.innerHTML = `
        <div class="fm-card">
          <div class="fm-status">大廳 — 請全隊打開此任務</div>
          ${membersHtml(st)}
          <button type="button" class="fm-btn primary" id="fm-start" ${st.all_online ? '' : 'disabled'}>
            ${st.all_online ? '全隊就緒 · 開始遊戲' : '等待全隊加入…'}
          </button>
          <button type="button" class="fm-btn ghost" id="fm-refresh">重新整理狀態</button>
        </div>`;
      body.querySelector('#fm-start')?.addEventListener('click', async () => {
        try {
          const next = await api('/api/team_minigame/start', {
            method: 'POST',
            body: JSON.stringify({ task_id: taskId }),
          });
          render(next);
        } catch (e) {
          alert(e.message || '無法開始');
        }
      });
      body.querySelector('#fm-refresh')?.addEventListener('click', () => tick());
      return;
    }

    if (status === 'won') {
      body.innerHTML = `
        <div class="fm-card" style="text-align:center">
          <div style="font-size:2rem">🎉</div>
          <h2 style="color:#34d399">全隊通過潛行路線！</h2>
          <p class="fm-status">10 輪記憶挑戰完成</p>
        </div>`;
      if (options.onComplete && !completedFired) {
        completedFired = true;
        options.onComplete({
          taskId,
          gameId: 'flash_memory',
          result: 'win',
          teamSession: true,
        });
      }
      stopPoll();
      return;
    }

    if (status === 'lost') {
      const lr = st.last_round_result || {};
      body.innerHTML = `
        <div class="fm-card" style="text-align:center">
          <h2 style="color:#f87171">潛行失敗</h2>
          <p class="fm-status">第 ${lr.round || '?'} 輪只有 ${lr.correct_count ?? 0} 人答對（需要 ${lr.need ?? 2}）</p>
          <p class="fm-status">正確答案：<strong>${lr.code || '—'}</strong></p>
          <button type="button" class="fm-btn primary" id="fm-retry">重新召集全隊</button>
        </div>`;
      body.querySelector('#fm-retry')?.addEventListener('click', async () => {
        await api('/api/team_minigame/reset', {
          method: 'POST',
          body: JSON.stringify({ task_id: taskId }),
        });
        await join();
      });
      return;
    }

    // playing
    const phase = st.phase;
    const round = st.round || 1;
    const total = st.total_rounds || 10;
    let phaseUi = '';

    if (phase === 'show') {
      phaseUi = `
        <div class="fm-status">第 ${round} / ${total} 輪 · 記住這串！</div>
        <div class="fm-code">${st.show_code || '····'}</div>
        <div class="fm-status">顯示剩餘 ${st.show_remaining ?? '—'}s</div>`;
    } else if (phase === 'input') {
      phaseUi = `
        <div class="fm-status">第 ${round} / ${total} 輪 · 輸入你記住的內容</div>
        <div class="fm-code hidden-code">••••</div>
        <input class="fm-input" id="fm-ans" autocomplete="off" autocapitalize="characters" placeholder="輸入" ${st.my_answered ? 'disabled' : ''} />
        <button type="button" class="fm-btn primary" id="fm-submit" ${st.my_answered || submitting ? 'disabled' : ''}>
          ${st.my_answered ? '已提交，等待隊友…' : '提交答案'}
        </button>
        <div class="fm-status">剩餘 ${st.input_remaining ?? '—'}s</div>`;
    } else if (phase === 'result') {
      const lr = st.last_round_result || {};
      phaseUi = `
        <div class="fm-toast" style="color:${lr.passed ? '#34d399' : '#f87171'}">
          ${lr.passed ? '✓ 本輪通過' : '✗ 本輪失敗'}
        </div>
        <div class="fm-status">正確：${lr.code || '—'} · 答對 ${lr.correct_count ?? 0} 人（需 ${lr.need ?? 2}）</div>`;
    } else {
      phaseUi = `<div class="fm-status">同步中…</div>`;
    }

    body.innerHTML = `
      <div class="fm-card">
        ${phaseUi}
        ${membersHtml(st)}
      </div>`;

    const input = body.querySelector('#fm-ans');
    const submit = body.querySelector('#fm-submit');
    if (submit && input && !st.my_answered) {
      const send = async () => {
        if (submitting) return;
        submitting = true;
        try {
          const next = await api('/api/team_minigame/flash_answer', {
            method: 'POST',
            body: JSON.stringify({ task_id: taskId, answer: input.value }),
          });
          render(next);
        } catch (e) {
          alert(e.message || '提交失敗');
        } finally {
          submitting = false;
        }
      };
      submit.onclick = send;
      input.onkeydown = (ev) => {
        if (ev.key === 'Enter') send();
      };
      if (phase === 'input' && lastPhase !== 'input') {
        setTimeout(() => input.focus(), 50);
      }
    }
    lastPhase = phase;
  }

  async function tick() {
    if (unmounted) return;
    try {
      const st = await api(`/api/team_minigame/status?task_id=${encodeURIComponent(taskId)}`);
      render(st);
    } catch (_) { /* ignore transient */ }
  }

  async function join() {
    const st = await api('/api/team_minigame/join', {
      method: 'POST',
      body: JSON.stringify({ task_id: taskId }),
    });
    render(st);
    stopPoll();
    pollTimer = setInterval(tick, 700);
  }

  body.innerHTML = `<div class="fm-status">連接全隊房間…</div>`;
  join().catch((e) => {
    body.innerHTML = `<div class="fm-status" style="color:#f87171">${e.message || '加入失敗'}</div>`;
  });
}

export function unmount(rootEl) {
  unmounted = true;
  stopPoll();
  if (rootEl) rootEl.innerHTML = '';
}
