/**
 * Team flash memory — all members play together.
 * Mobile: never destroy #fm-ans during input phase (poll must not dismiss keyboard).
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
  let lastKey = '';
  let submitting = false;
  let inputBound = false;

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
      .fm-btn {
        width:100%; min-height:48px; border:none; border-radius:14px; font-weight:800;
        font-size:15px; cursor:pointer; margin-top:8px; -webkit-tap-highlight-color: transparent;
      }
      .fm-btn.primary { background:#d97706; color:#18181b; }
      .fm-btn.ghost { background:#3f3f46; color:#e4e4e7; }
      .fm-btn:disabled { opacity:0.45; cursor:not-allowed; }
      .fm-input {
        width:100%; box-sizing:border-box; padding:14px; border-radius:12px;
        border:2px solid #52525b; background:#09090b; color:#fafafa;
        font-size:1.4rem; font-weight:700; letter-spacing:0.2em; text-align:center;
        font-family: ui-monospace, monospace; text-transform:uppercase;
        /* Keep mobile keyboard stable */
        -webkit-user-select: text; user-select: text;
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
    return `<div class="fm-members" id="fm-members">${list.map((m) => {
      const cls = m.online ? 'on' : 'off';
      return `<span class="fm-chip ${cls}">${m.online ? '●' : '○'} ${m.display_name || m.squad_id}${m.answered ? ' ✓' : ''}</span>`;
    }).join('')}</div>
    <div class="fm-status" id="fm-online">在線 ${st.online_count || 0} / 應到 ${st.expected_count || '?'}</div>`;
  }

  function stateKey(st) {
    return [
      st.status,
      st.phase,
      st.round,
      st.my_answered ? 1 : 0,
      st.status === 'won' ? 1 : 0,
      st.status === 'lost' ? 1 : 0,
      (st.last_round_result && st.last_round_result.passed) ? 1 : 0,
    ].join('|');
  }

  function patchInputPhase(st) {
    // Update only non-input widgets so mobile keyboard stays up.
    const roundEl = body.querySelector('#fm-round-label');
    if (roundEl) {
      roundEl.textContent = `第 ${st.round || 1} / ${st.total_rounds || 10} 輪 · 輸入你記住的內容`;
    }
    const timerEl = body.querySelector('#fm-input-timer');
    if (timerEl) {
      timerEl.textContent = `剩餘 ${st.input_remaining ?? '—'}s`;
    }
    const memHost = body.querySelector('#fm-members-host');
    if (memHost) {
      memHost.innerHTML = membersHtml(st);
    }
    const submit = body.querySelector('#fm-submit');
    const input = body.querySelector('#fm-ans');
    if (st.my_answered) {
      if (input) {
        input.disabled = true;
        input.blur();
      }
      if (submit) {
        submit.disabled = true;
        submit.textContent = '已提交，等待隊友…';
      }
    }
  }

  function bindInputHandlers() {
    if (inputBound) return;
    const input = body.querySelector('#fm-ans');
    const submit = body.querySelector('#fm-submit');
    if (!input || !submit) return;
    inputBound = true;

    const send = async () => {
      if (submitting || input.disabled) return;
      const val = (input.value || '').trim();
      if (!val) {
        input.focus();
        return;
      }
      submitting = true;
      submit.disabled = true;
      try {
        const next = await api('/api/team_minigame/flash_answer', {
          method: 'POST',
          body: JSON.stringify({ task_id: taskId, answer: val }),
        });
        render(next);
      } catch (e) {
        alert(e.message || '提交失敗');
        submit.disabled = false;
        input.focus();
      } finally {
        submitting = false;
      }
    };

    submit.onclick = (ev) => {
      ev.preventDefault();
      send();
    };
    // Use form submit for better mobile keyboard "go" behavior
    const form = body.querySelector('#fm-form');
    if (form) {
      form.onsubmit = (ev) => {
        ev.preventDefault();
        send();
      };
    }
    input.addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter') {
        ev.preventDefault();
        send();
      }
    });
  }

  function render(st) {
    if (unmounted || !body) return;
    const status = st.status;
    const key = stateKey(st);

    // Soft-patch during stable input phase (preserve keyboard)
    if (
      status === 'playing'
      && st.phase === 'input'
      && lastKey.startsWith('playing|input|')
      && key.split('|').slice(0, 3).join('|') === lastKey.split('|').slice(0, 3).join('|')
      && body.querySelector('#fm-ans')
    ) {
      patchInputPhase(st);
      lastKey = key;
      return;
    }

    if (status === 'lobby') {
      inputBound = false;
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
          render(await api('/api/team_minigame/start', {
            method: 'POST',
            body: JSON.stringify({ task_id: taskId }),
          }));
        } catch (e) {
          alert(e.message || '無法開始');
        }
      });
      body.querySelector('#fm-refresh')?.addEventListener('click', () => tick());
      lastKey = key;
      return;
    }

    if (status === 'won') {
      inputBound = false;
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
      lastKey = key;
      return;
    }

    if (status === 'lost') {
      inputBound = false;
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
        lastKey = '';
        await join();
      });
      lastKey = key;
      return;
    }

    // playing
    const phase = st.phase;
    const round = st.round || 1;
    const total = st.total_rounds || 10;

    if (phase === 'show') {
      inputBound = false;
      body.innerHTML = `
        <div class="fm-card">
          <div class="fm-status">第 ${round} / ${total} 輪 · 記住這串！</div>
          <div class="fm-code">${st.show_code || '····'}</div>
          <div class="fm-status">顯示剩餘 ${st.show_remaining ?? '—'}s</div>
          <div id="fm-members-host">${membersHtml(st)}</div>
        </div>`;
    } else if (phase === 'input') {
      const enteringFresh = !(
        lastKey.startsWith(`playing|input|${round}|`)
        && body.querySelector('#fm-ans')
      );
      if (enteringFresh) {
        inputBound = false;
        body.innerHTML = `
          <div class="fm-card">
            <div class="fm-status" id="fm-round-label">第 ${round} / ${total} 輪 · 輸入你記住的內容</div>
            <div class="fm-code hidden-code">••••</div>
            <form id="fm-form" action="javascript:void(0)" autocomplete="off">
              <input
                class="fm-input"
                id="fm-ans"
                name="answer"
                type="text"
                inputmode="text"
                enterkeyhint="done"
                autocomplete="off"
                autocapitalize="characters"
                autocorrect="off"
                spellcheck="false"
                placeholder="輸入"
                ${st.my_answered ? 'disabled' : ''}
              />
              <button type="submit" class="fm-btn primary" id="fm-submit" ${st.my_answered || submitting ? 'disabled' : ''}>
                ${st.my_answered ? '已提交，等待隊友…' : '提交答案'}
              </button>
            </form>
            <div class="fm-status" id="fm-input-timer">剩餘 ${st.input_remaining ?? '—'}s</div>
            <div id="fm-members-host">${membersHtml(st)}</div>
          </div>`;
        bindInputHandlers();
        if (!st.my_answered) {
          // Focus once when entering input phase — keep keyboard open
          const input = body.querySelector('#fm-ans');
          setTimeout(() => {
            try {
              input?.focus({ preventScroll: false });
              // iOS: click focus trick
              input?.click?.();
            } catch (_) {
              input?.focus();
            }
          }, 80);
        }
      } else {
        patchInputPhase(st);
      }
    } else if (phase === 'result') {
      inputBound = false;
      const lr = st.last_round_result || {};
      body.innerHTML = `
        <div class="fm-card">
          <div class="fm-toast" style="color:${lr.passed ? '#34d399' : '#f87171'}">
            ${lr.passed ? '✓ 本輪通過' : '✗ 本輪失敗'}
          </div>
          <div class="fm-status">正確：${lr.code || '—'} · 答對 ${lr.correct_count ?? 0} 人（需 ${lr.need ?? 2}）</div>
          <div id="fm-members-host">${membersHtml(st)}</div>
        </div>`;
    } else {
      inputBound = false;
      body.innerHTML = `<div class="fm-card"><div class="fm-status">同步中…</div></div>`;
    }

    lastKey = key;
  }

  async function tick() {
    if (unmounted) return;
    try {
      const st = await api(`/api/team_minigame/status?task_id=${encodeURIComponent(taskId)}`);
      render(st);
    } catch (_) { /* ignore */ }
  }

  async function join() {
    const st = await api('/api/team_minigame/join', {
      method: 'POST',
      body: JSON.stringify({ task_id: taskId }),
    });
    render(st);
    stopPoll();
    // Slightly slower poll while typing is fine; soft-patch protects keyboard
    pollTimer = setInterval(tick, 900);
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
