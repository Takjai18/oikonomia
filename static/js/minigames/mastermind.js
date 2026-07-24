/**
 * Team Mastermind — shared secret; every member must crack it within 10 guesses.
 * Pegs: 綠=位置正確, 白=顏色正確位置錯, 紅=錯誤
 */
let pollTimer = null;
let unmounted = true;
let completedFired = false;

const COLOR_META = {
  R: { label: '紅', hex: '#e74c3c' },
  B: { label: '藍', hex: '#3498db' },
  G: { label: '綠', hex: '#27ae60' },
  Y: { label: '黃', hex: '#f1c40f' },
  P: { label: '紫', hex: '#9b59b6' },
  O: { label: '橙', hex: '#e67e22' },
};

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
  let draft = [];
  let cursor = 0;
  let codeLength = parseInt(config.codeLength, 10) || 4;
  let maxGuesses = parseInt(config.maxGuesses, 10) || 10;
  let myHistory = [];
  let colors = Object.keys(COLOR_META);

  rootEl.innerHTML = `
    <style>
      .mm-wrap { max-width: 420px; margin: 0 auto; font-family: system-ui,sans-serif; color:#e4e4e7; }
      .mm-title { font-size:1.15rem; font-weight:800; color:#fbbf24; margin-bottom:6px; }
      .mm-hint { font-size:12px; color:#a1a1aa; line-height:1.45; margin-bottom:12px; }
      .mm-card { background:#18181b; border:1px solid #3f3f46; border-radius:16px; padding:14px; margin-bottom:10px; }
      .mm-legend { display:flex; gap:10px; flex-wrap:wrap; font-size:11px; color:#a1a1aa; margin-bottom:10px; }
      .mm-legend span { display:inline-flex; align-items:center; gap:4px; }
      .mm-pin { width:12px; height:12px; border-radius:999px; display:inline-block; }
      .mm-pin.green { background:#22c55e; }
      .mm-pin.white { background:#fafafa; border:1px solid #a1a1aa; }
      .mm-pin.red { background:#ef4444; }
      .mm-members { display:flex; flex-wrap:wrap; gap:6px; }
      .mm-chip { font-size:11px; padding:4px 8px; border-radius:999px; border:1px solid #52525b; background:#27272a; }
      .mm-chip.on { border-color:#34d399; color:#6ee7b7; }
      .mm-chip.won { border-color:#22c55e; background:#052e1a; color:#86efac; }
      .mm-chip.lost { border-color:#ef4444; color:#fca5a5; }
      .mm-row { display:flex; align-items:center; gap:8px; margin-bottom:8px; }
      .mm-pegs { display:flex; gap:6px; }
      .mm-peg {
        width:36px; height:36px; border-radius:999px; border:2px solid #3f3f46; background:#09090b;
      }
      .mm-peg.draft { box-shadow:0 0 0 2px #f59e0b; }
      .mm-fb { display:flex; flex-wrap:wrap; gap:3px; width:48px; }
      .mm-palette { display:flex; flex-wrap:wrap; gap:8px; justify-content:center; margin:12px 0; }
      .mm-swatch {
        width:42px; height:42px; border-radius:12px; border:2px solid #52525b; cursor:pointer;
        color:#fff; font-size:11px; font-weight:700; display:flex; align-items:center; justify-content:center;
        text-shadow:0 1px 2px rgba(0,0,0,.5);
      }
      .mm-btn {
        min-height:44px; border:none; border-radius:12px; font-weight:800; font-size:15px; cursor:pointer;
      }
      .mm-btn.primary { background:#d97706; color:#18181b; width:100%; }
      .mm-btn.ghost { background:#3f3f46; color:#e4e4e7; width:100%; margin-top:8px; }
      .mm-btn:disabled { opacity:0.45; cursor:not-allowed; }
      .mm-actions { display:grid; grid-template-columns:1fr 1fr; gap:8px; }
      .mm-status { text-align:center; font-size:13px; color:#a1a1aa; margin:6px 0; }
      .mm-hist { max-height:200px; overflow-y:auto; }
    </style>
    <div class="mm-wrap">
      <div class="mm-title">${config.themeTitle || '村莊情報 · 解碼'}</div>
      <p class="mm-hint">${config.themeHint || '全隊一起破解顏色密碼。每人最多 10 次猜測，全隊都破解才算過關。'}</p>
      <div class="mm-legend">
        <span><i class="mm-pin green"></i> 綠＝位置正確</span>
        <span><i class="mm-pin white"></i> 白＝顏色對、位置錯</span>
        <span><i class="mm-pin red"></i> 紅＝錯誤</span>
      </div>
      <div id="mm-body"></div>
    </div>
  `;

  const body = rootEl.querySelector('#mm-body');

  function pegHtml(colorId, active) {
    const c = COLOR_META[colorId];
    const bg = c ? c.hex : '#09090b';
    return `<div class="mm-peg ${active ? 'draft' : ''}" style="background:${bg}" title="${c ? c.label : ''}"></div>`;
  }

  function pinsHtml(h) {
    const pins = [];
    for (let i = 0; i < (h.green || 0); i++) pins.push('<i class="mm-pin green"></i>');
    for (let i = 0; i < (h.white || 0); i++) pins.push('<i class="mm-pin white"></i>');
    for (let i = 0; i < (h.red || 0); i++) pins.push('<i class="mm-pin red"></i>');
    while (pins.length < codeLength) pins.push('<i class="mm-pin" style="background:#3f3f46"></i>');
    return pins.join('');
  }

  function membersHtml(st) {
    return `<div class="mm-members">${(st.members || []).map((m) => {
      let cls = m.online ? 'on' : '';
      if (m.won) cls = 'won';
      if (m.lost) cls = 'lost';
      const tag = m.won ? ' ✓破解' : (m.lost ? ' ✗失敗' : '');
      return `<span class="mm-chip ${cls}">${m.display_name || m.squad_id}${tag}</span>`;
    }).join('')}</div>
    <div class="mm-status">在線 ${st.online_count || 0} / ${st.expected_count || '?'}</div>`;
  }

  function renderPlay(st) {
    codeLength = st.code_length || codeLength;
    maxGuesses = st.max_guesses || maxGuesses;
    myHistory = st.my_history || myHistory;
    if (Array.isArray(st.colors) && st.colors.length) colors = st.colors;
    if (draft.length !== codeLength) {
      draft = Array(codeLength).fill(null);
      cursor = 0;
    }

    const disabled = st.my_won || st.my_lost || st.status !== 'playing';
    const hist = myHistory.map((h) => `
      <div class="mm-row">
        <div class="mm-pegs">${(h.guess || []).map((id) => pegHtml(id, false)).join('')}</div>
        <div class="mm-fb">${pinsHtml(h)}</div>
      </div>`).join('');

    body.innerHTML = `
      <div class="mm-card">
        <div class="mm-status">你的進度：${st.my_guesses || 0} / ${maxGuesses} 次
          ${st.my_won ? ' · <span style="color:#22c55e">已破解</span>' : ''}
          ${st.my_lost ? ' · <span style="color:#ef4444">已用盡</span>' : ''}
        </div>
        ${membersHtml(st)}
        <div class="mm-hist">${hist || '<div class="mm-status">尚未猜測</div>'}</div>
        ${disabled ? '' : `
          <div class="mm-row">
            <div class="mm-pegs" id="mm-draft"></div>
          </div>
          <div class="mm-palette" id="mm-palette"></div>
          <div class="mm-actions">
            <button type="button" class="mm-btn ghost" id="mm-clear" style="margin:0">清除</button>
            <button type="button" class="mm-btn primary" id="mm-submit" style="width:auto" disabled>提交</button>
          </div>
        `}
      </div>`;

    if (disabled) return;

    const draftEl = body.querySelector('#mm-draft');
    const paletteEl = body.querySelector('#mm-palette');
    const submitBtn = body.querySelector('#mm-submit');

    const paintDraft = () => {
      draftEl.innerHTML = draft.map((id, i) => pegHtml(id, i === cursor)).join('');
      draftEl.querySelectorAll('.mm-peg').forEach((el, i) => {
        el.style.cursor = 'pointer';
        el.onclick = () => { cursor = i; paintDraft(); };
      });
      submitBtn.disabled = draft.some((x) => !x);
    };
    paintDraft();

    colors.forEach((id) => {
      const c = COLOR_META[id] || { label: id, hex: '#666' };
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'mm-swatch';
      b.style.background = c.hex;
      b.textContent = c.label;
      b.onclick = () => {
        draft[cursor] = id;
        cursor = Math.min(codeLength - 1, cursor + 1);
        paintDraft();
      };
      paletteEl.appendChild(b);
    });

    body.querySelector('#mm-clear').onclick = () => {
      draft = Array(codeLength).fill(null);
      cursor = 0;
      paintDraft();
    };

    submitBtn.onclick = async () => {
      if (draft.some((x) => !x)) return;
      submitBtn.disabled = true;
      try {
        const next = await api('/api/team_minigame/mastermind_guess', {
          method: 'POST',
          body: JSON.stringify({ task_id: taskId, guess: [...draft] }),
        });
        myHistory = next.my_history || myHistory;
        draft = Array(codeLength).fill(null);
        cursor = 0;
        render(next);
      } catch (e) {
        alert(e.message || '提交失敗');
        submitBtn.disabled = false;
      }
    };
  }

  function render(st) {
    if (unmounted || !body) return;

    if (st.status === 'lobby') {
      body.innerHTML = `
        <div class="mm-card">
          <div class="mm-status">大廳 — 全隊都要進入再開始</div>
          ${membersHtml(st)}
          <button type="button" class="mm-btn primary" id="mm-start" ${st.all_online ? '' : 'disabled'}>
            ${st.all_online ? '開始解碼' : '等待全隊…'}
          </button>
          <button type="button" class="mm-btn ghost" id="mm-refresh">重新整理</button>
        </div>`;
      body.querySelector('#mm-start')?.addEventListener('click', async () => {
        try {
          render(await api('/api/team_minigame/start', {
            method: 'POST',
            body: JSON.stringify({ task_id: taskId }),
          }));
        } catch (e) {
          alert(e.message || '無法開始');
        }
      });
      body.querySelector('#mm-refresh')?.addEventListener('click', () => tick());
      return;
    }

    if (st.status === 'won') {
      body.innerHTML = `
        <div class="mm-card" style="text-align:center">
          <div style="font-size:2rem">🎉</div>
          <h2 style="color:#34d399">全隊解碼成功！</h2>
          <p class="mm-status">所有隊員都在 10 次內破解密碼</p>
        </div>`;
      if (options.onComplete && !completedFired) {
        completedFired = true;
        options.onComplete({
          taskId,
          gameId: 'mastermind',
          result: 'win',
          teamSession: true,
        });
      }
      stopPoll();
      return;
    }

    if (st.status === 'lost') {
      body.innerHTML = `
        <div class="mm-card" style="text-align:center">
          <h2 style="color:#f87171">解碼失敗</h2>
          <p class="mm-status">有隊員用盡 10 次仍未破解。請全隊重新挑戰。</p>
          ${membersHtml(st)}
          <button type="button" class="mm-btn primary" id="mm-retry">重新召集</button>
        </div>`;
      body.querySelector('#mm-retry')?.addEventListener('click', async () => {
        await api('/api/team_minigame/reset', {
          method: 'POST',
          body: JSON.stringify({ task_id: taskId }),
        });
        await join();
      });
      return;
    }

    renderPlay(st);
  }

  async function tick() {
    if (unmounted) return;
    try {
      const st = await api(`/api/team_minigame/status?task_id=${encodeURIComponent(taskId)}`);
      // Don't rebuild draft UI every poll while typing unless status/history changed
      if (st.status === 'playing' && body.querySelector('#mm-draft') && !st.my_won && !st.my_lost) {
        // light update members only
        myHistory = st.my_history || myHistory;
        // re-render fully to keep team chips fresh
      }
      render(st);
    } catch (_) {}
  }

  async function join() {
    const st = await api('/api/team_minigame/join', {
      method: 'POST',
      body: JSON.stringify({ task_id: taskId }),
    });
    render(st);
    stopPoll();
    pollTimer = setInterval(tick, 900);
  }

  body.innerHTML = `<div class="mm-status">連接全隊房間…</div>`;
  join().catch((e) => {
    body.innerHTML = `<div class="mm-status" style="color:#f87171">${e.message || '加入失敗'}</div>`;
  });
}

export function unmount(rootEl) {
  unmounted = true;
  stopPoll();
  if (rootEl) rootEl.innerHTML = '';
}
