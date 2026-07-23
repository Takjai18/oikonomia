/**
 * Memory match — flip pairs under time pressure.
 * Config: pairs (4–12), timeLimitSec, previewSec (optional flash of all cards)
 */
let timerId = null;
let lockBoard = false;
let firstCard = null;
let matched = 0;
let timeLeft = 0;

const EMOJI_POOL = [
  '🔥', '❄️', '🐐', '🦅', '🗡️', '🛡️', '💎', '🗝️',
  '🌲', '⛰️', '🩸', '🌙', '⚡', '🪞', '📜', '🎭',
];

export function mount(rootEl, options) {
  cleanup();
  const config = {
    pairs: 8,
    timeLimitSec: 75,
    previewSec: 0,
    ...(options.config || {}),
  };
  const pairs = Math.max(4, Math.min(12, parseInt(config.pairs, 10) || 8));
  timeLeft = Math.max(30, parseInt(config.timeLimitSec, 10) || 75);
  matched = 0;
  lockBoard = false;
  firstCard = null;

  const icons = EMOJI_POOL.slice(0, pairs);
  let deck = [...icons, ...icons];
  // Fisher–Yates
  for (let i = deck.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [deck[i], deck[j]] = [deck[j], deck[i]];
  }

  const cols = pairs <= 6 ? 3 : 4;
  rootEl.innerHTML = `
    <style>
      .mm-wrap { max-width: 420px; margin: 0 auto; font-family: system-ui, sans-serif; }
      .mm-hud { display:flex; justify-content:space-between; font-weight:700; margin-bottom:10px; color:#e4e4e7; }
      .mm-grid { display:grid; grid-template-columns: repeat(${cols}, 1fr); gap:8px; }
      .mm-card {
        aspect-ratio: 1; border-radius: 12px; border: 2px solid #3f3f46;
        background: #27272a; color: transparent; font-size: 1.6rem;
        display:flex; align-items:center; justify-content:center;
        cursor:pointer; user-select:none; transition: transform .12s, background .12s;
      }
      .mm-card.flipped, .mm-card.matched {
        background: #18181b; color: #fafafa; border-color: #a1a1aa;
      }
      .mm-card.matched { border-color: #34d399; background: #052e1a; }
      .mm-card:active { transform: scale(0.96); }
      .mm-msg { text-align:center; margin-top:12px; color:#a1a1aa; font-size:13px; }
      .mm-btn {
        display:block; width:100%; margin-top:12px; padding:12px;
        border:none; border-radius:12px; background:#d97706; color:#18181b;
        font-weight:700; font-size:16px; cursor:pointer;
      }
    </style>
    <div class="mm-wrap">
      <div class="mm-hud">
        <span id="mm-time">時間 ${timeLeft}s</span>
        <span id="mm-score">配對 0 / ${pairs}</span>
      </div>
      <div class="mm-grid" id="mm-grid"></div>
      <p class="mm-msg">記住位置，翻開相同符號的兩張牌。錯了會扣時間。</p>
    </div>
  `;

  const grid = rootEl.querySelector('#mm-grid');
  deck.forEach((icon, idx) => {
    const card = document.createElement('button');
    card.type = 'button';
    card.className = 'mm-card';
    card.dataset.icon = icon;
    card.dataset.idx = String(idx);
    card.setAttribute('aria-label', '牌');
    card.textContent = '?';
    card.addEventListener('click', () => onFlip(card));
    grid.appendChild(card);
  });

  const previewSec = Math.max(0, parseInt(config.previewSec, 10) || 0);
  if (previewSec > 0) {
    lockBoard = true;
    rootEl.querySelectorAll('.mm-card').forEach((c) => {
      c.classList.add('flipped');
      c.textContent = c.dataset.icon;
    });
    setTimeout(() => {
      rootEl.querySelectorAll('.mm-card').forEach((c) => {
        if (!c.classList.contains('matched')) {
          c.classList.remove('flipped');
          c.textContent = '?';
        }
      });
      lockBoard = false;
    }, previewSec * 1000);
  }

  timerId = setInterval(() => {
    timeLeft -= 1;
    const el = rootEl.querySelector('#mm-time');
    if (el) el.textContent = `時間 ${timeLeft}s`;
    if (timeLeft <= 0) endGame(false);
  }, 1000);

  function onFlip(card) {
    if (lockBoard || timeLeft <= 0) return;
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
      const score = rootEl.querySelector('#mm-score');
      if (score) score.textContent = `配對 ${matched} / ${pairs}`;
      firstCard = null;
      lockBoard = false;
      if (matched >= pairs) endGame(true);
    } else {
      timeLeft = Math.max(0, timeLeft - 3);
      const el = rootEl.querySelector('#mm-time');
      if (el) el.textContent = `時間 ${timeLeft}s`;
      setTimeout(() => {
        a.classList.remove('flipped');
        b.classList.remove('flipped');
        a.textContent = '?';
        b.textContent = '?';
        firstCard = null;
        lockBoard = false;
        if (timeLeft <= 0) endGame(false);
      }, 550);
    }
  }

  function endGame(win) {
    cleanup();
    if (win) {
      rootEl.innerHTML = `
        <div class="mm-wrap" style="text-align:center;padding:24px;color:#e4e4e7">
          <h2 style="color:#34d399">記憶成功！</h2>
          <p>你在巷弄裡對上了 Iggy 的蹤跡。</p>
        </div>`;
      setTimeout(() => {
        if (options.onComplete) {
          options.onComplete({
            taskId: options.taskId,
            gameId: 'memory_match',
            result: 'win',
          });
        }
      }, 700);
    } else {
      rootEl.innerHTML = `
        <div class="mm-wrap" style="text-align:center;padding:24px;color:#e4e4e7">
          <h2 style="color:#f87171">時間到</h2>
          <p>只配對了 ${matched} / ${pairs} 組。</p>
          <button type="button" class="mm-btn" id="mm-retry">重新挑戰</button>
        </div>`;
      rootEl.querySelector('#mm-retry')?.addEventListener('click', () => {
        mount(rootEl, options);
      });
    }
  }
}

function cleanup() {
  if (timerId) {
    clearInterval(timerId);
    timerId = null;
  }
  lockBoard = false;
  firstCard = null;
}

export function unmount(rootEl) {
  cleanup();
  if (rootEl) rootEl.innerHTML = '';
}
