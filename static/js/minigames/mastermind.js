/**
 * Mastermind — crack a secret code with color pegs.
 * Config:
 *   codeLength (3–6, default 4)
 *   colors (array of { id, label, hex }, default 6)
 *   maxGuesses (default 10)
 *   answer (optional fixed code as array of color ids)
 *   themeTitle / themeHint (optional UI copy)
 */
let mounted = false;

const DEFAULT_COLORS = [
  { id: 'R', label: '紅', hex: '#e74c3c' },
  { id: 'B', label: '藍', hex: '#3498db' },
  { id: 'G', label: '綠', hex: '#27ae60' },
  { id: 'Y', label: '黃', hex: '#f1c40f' },
  { id: 'P', label: '紫', hex: '#9b59b6' },
  { id: 'O', label: '橙', hex: '#e67e22' },
];

function pickCode(colors, length, fixed) {
  if (Array.isArray(fixed) && fixed.length === length) {
    const ids = new Set(colors.map((c) => c.id));
    if (fixed.every((x) => ids.has(x))) return [...fixed];
  }
  const out = [];
  for (let i = 0; i < length; i++) {
    out.push(colors[Math.floor(Math.random() * colors.length)].id);
  }
  return out;
}

/** black = correct color+position, white = correct color wrong position */
function scoreGuess(secret, guess) {
  const n = secret.length;
  const usedS = Array(n).fill(false);
  const usedG = Array(n).fill(false);
  let black = 0;
  let white = 0;
  for (let i = 0; i < n; i++) {
    if (guess[i] === secret[i]) {
      black += 1;
      usedS[i] = true;
      usedG[i] = true;
    }
  }
  for (let i = 0; i < n; i++) {
    if (usedG[i]) continue;
    for (let j = 0; j < n; j++) {
      if (usedS[j]) continue;
      if (guess[i] === secret[j]) {
        white += 1;
        usedS[j] = true;
        break;
      }
    }
  }
  return { black, white };
}

export function mount(rootEl, options) {
  unmount(rootEl);
  mounted = true;

  const config = {
    codeLength: 4,
    maxGuesses: 10,
    colors: DEFAULT_COLORS,
    answer: null,
    themeTitle: '情報解碼 · Mastermind',
    themeHint: '猜出密碼：黑釘＝顏色與位置正確；白釘＝顏色正確但位置不對。',
    ...(options.config || {}),
  };

  const colors = (Array.isArray(config.colors) && config.colors.length >= 3)
    ? config.colors
    : DEFAULT_COLORS;
  const codeLength = Math.max(3, Math.min(6, parseInt(config.codeLength, 10) || 4));
  const maxGuesses = Math.max(4, Math.min(14, parseInt(config.maxGuesses, 10) || 10));
  const secret = pickCode(colors, codeLength, config.answer);
  const colorById = Object.fromEntries(colors.map((c) => [c.id, c]));

  let draft = Array(codeLength).fill(null);
  let cursor = 0;
  let history = [];
  let over = false;

  rootEl.innerHTML = `
    <style>
      .mmind-wrap { max-width: 420px; margin: 0 auto; font-family: system-ui, sans-serif; color: #e4e4e7; }
      .mmind-title { font-size: 1.1rem; font-weight: 800; color: #fbbf24; margin-bottom: 4px; }
      .mmind-hint { font-size: 12px; color: #a1a1aa; margin-bottom: 12px; line-height: 1.4; }
      .mmind-hud { display:flex; justify-content:space-between; font-weight:700; font-size:13px; margin-bottom:10px; }
      .mmind-row { display:flex; align-items:center; gap:8px; margin-bottom:8px; }
      .mmind-pegs { display:flex; gap:6px; }
      .mmind-peg {
        width: 36px; height: 36px; border-radius: 999px; border: 2px solid #3f3f46;
        background: #18181b; cursor: default;
      }
      .mmind-peg.draft { box-shadow: 0 0 0 2px #f59e0b; }
      .mmind-feedback { display:flex; flex-wrap:wrap; gap:3px; width: 44px; }
      .mmind-pin {
        width: 10px; height: 10px; border-radius: 999px; background: #3f3f46;
      }
      .mmind-pin.black { background: #fafafa; }
      .mmind-pin.white { background: #71717a; border: 1px solid #d4d4d8; }
      .mmind-palette { display:flex; flex-wrap:wrap; gap:8px; justify-content:center; margin: 14px 0 10px; }
      .mmind-swatch {
        width: 42px; height: 42px; border-radius: 12px; border: 2px solid #52525b;
        cursor: pointer; font-size: 11px; font-weight: 700; color: #fff;
        display:flex; align-items:center; justify-content:center;
        text-shadow: 0 1px 2px rgba(0,0,0,.5);
      }
      .mmind-swatch:active { transform: scale(0.95); }
      .mmind-actions { display:grid; grid-template-columns: 1fr 1fr; gap:8px; }
      .mmind-btn {
        min-height: 44px; border:none; border-radius: 12px; font-weight: 800;
        font-size: 15px; cursor: pointer;
      }
      .mmind-btn.submit { background: #d97706; color: #18181b; }
      .mmind-btn.clear { background: #3f3f46; color: #e4e4e7; }
      .mmind-btn:disabled { opacity: 0.45; cursor: not-allowed; }
      .mmind-history { max-height: 220px; overflow-y: auto; margin-bottom: 8px; }
      .mmind-end { text-align:center; padding: 24px 12px; }
      .mmind-end h2 { font-size: 1.4rem; margin-bottom: 8px; }
    </style>
    <div class="mmind-wrap">
      <div class="mmind-title">${config.themeTitle}</div>
      <p class="mmind-hint">${config.themeHint}</p>
      <div class="mmind-hud">
        <span id="mmind-guesses">剩餘 ${maxGuesses} 次</span>
        <span id="mmind-len">${codeLength} 碼</span>
      </div>
      <div class="mmind-history" id="mmind-history"></div>
      <div class="mmind-row" id="mmind-draft-row">
        <div class="mmind-pegs" id="mmind-draft"></div>
        <div class="mmind-feedback"></div>
      </div>
      <div class="mmind-palette" id="mmind-palette"></div>
      <div class="mmind-actions">
        <button type="button" class="mmind-btn clear" id="mmind-clear">清除</button>
        <button type="button" class="mmind-btn submit" id="mmind-submit" disabled>提交猜測</button>
      </div>
    </div>
  `;

  const historyEl = rootEl.querySelector('#mmind-history');
  const draftEl = rootEl.querySelector('#mmind-draft');
  const paletteEl = rootEl.querySelector('#mmind-palette');
  const submitBtn = rootEl.querySelector('#mmind-submit');
  const clearBtn = rootEl.querySelector('#mmind-clear');
  const guessesEl = rootEl.querySelector('#mmind-guesses');

  function pegHtml(colorId, { draftSlot = false, active = false } = {}) {
    const c = colorId ? colorById[colorId] : null;
    const bg = c ? c.hex : '#18181b';
    const cls = draftSlot && active ? 'mmind-peg draft' : 'mmind-peg';
    return `<div class="${cls}" style="background:${bg}" title="${c ? c.label : '空'}"></div>`;
  }

  function renderDraft() {
    if (!draftEl) return;
    draftEl.innerHTML = draft
      .map((id, i) => pegHtml(id, { draftSlot: true, active: i === cursor }))
      .join('');
    draftEl.querySelectorAll('.mmind-peg').forEach((el, i) => {
      el.style.cursor = 'pointer';
      el.onclick = () => {
        if (over) return;
        cursor = i;
        renderDraft();
      };
    });
    if (submitBtn) submitBtn.disabled = over || draft.some((x) => !x);
    if (guessesEl) {
      guessesEl.textContent = `剩餘 ${Math.max(0, maxGuesses - history.length)} 次`;
    }
  }

  function renderHistory() {
    if (!historyEl) return;
    historyEl.innerHTML = history.map((h) => {
      const pegs = h.guess.map((id) => pegHtml(id)).join('');
      const pins = [];
      for (let i = 0; i < h.black; i++) pins.push('<div class="mmind-pin black"></div>');
      for (let i = 0; i < h.white; i++) pins.push('<div class="mmind-pin white"></div>');
      while (pins.length < codeLength) pins.push('<div class="mmind-pin"></div>');
      return `<div class="mmind-row"><div class="mmind-pegs">${pegs}</div><div class="mmind-feedback">${pins.join('')}</div></div>`;
    }).join('');
  }

  colors.forEach((c) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'mmind-swatch';
    b.style.background = c.hex;
    b.textContent = c.label;
    b.onclick = () => {
      if (over) return;
      draft[cursor] = c.id;
      cursor = Math.min(codeLength - 1, cursor + 1);
      renderDraft();
    };
    paletteEl.appendChild(b);
  });

  clearBtn.onclick = () => {
    if (over) return;
    draft = Array(codeLength).fill(null);
    cursor = 0;
    renderDraft();
  };

  submitBtn.onclick = () => {
    if (over || draft.some((x) => !x)) return;
    const guess = [...draft];
    const { black, white } = scoreGuess(secret, guess);
    history.push({ guess, black, white });
    draft = Array(codeLength).fill(null);
    cursor = 0;
    renderHistory();
    renderDraft();

    if (black === codeLength) {
      endWin();
      return;
    }
    if (history.length >= maxGuesses) {
      endLose();
    }
  };

  function endWin() {
    over = true;
    rootEl.innerHTML = `
      <div class="mmind-wrap mmind-end">
        <h2 style="color:#34d399">情報解碼成功！</h2>
        <p style="color:#a1a1aa;font-size:14px;">你成功破解了村莊線人留下的密碼。</p>
      </div>`;
    if (options.onComplete) {
      options.onComplete({
        taskId: options.taskId,
        gameId: 'mastermind',
        result: 'win',
        guesses: history.length,
      });
    }
  }

  function endLose() {
    over = true;
    const reveal = secret.map((id) => colorById[id]?.label || id).join(' · ');
    rootEl.innerHTML = `
      <div class="mmind-wrap mmind-end">
        <h2 style="color:#f87171">解碼失敗</h2>
        <p style="color:#a1a1aa;font-size:13px;margin-bottom:12px;">正確密碼：${reveal}</p>
        <button type="button" class="mmind-btn submit" id="mmind-retry" style="width:100%">重新挑戰</button>
      </div>`;
    rootEl.querySelector('#mmind-retry')?.addEventListener('click', () => {
      mount(rootEl, options);
    });
  }

  renderDraft();
  renderHistory();
}

export function unmount(rootEl) {
  mounted = false;
  if (rootEl) rootEl.innerHTML = '';
}
