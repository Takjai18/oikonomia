/**
 * @file Combat tutorial overlay — multi-step text box before first action.
 */

import { DOM_IDS } from '../selectors.js';

export function createTutorialView(rootEl) {
  let modal = rootEl.querySelector(`#${DOM_IDS.TUTORIAL_MODAL}`);
  let titleEl = rootEl.querySelector(`#${DOM_IDS.TUTORIAL_TITLE}`);
  let bodyEl = rootEl.querySelector(`#${DOM_IDS.TUTORIAL_BODY}`);
  let progressEl = rootEl.querySelector(`#${DOM_IDS.TUTORIAL_PROGRESS}`);
  let nextBtn = rootEl.querySelector(`#${DOM_IDS.TUTORIAL_NEXT}`);
  let skipBtn = rootEl.querySelector(`#${DOM_IDS.TUTORIAL_SKIP}`);

  let steps = [];
  let index = 0;
  let onDone = null;
  let typingTimer = null;
  let typingDone = true;

  function ensureEls() {
    modal = rootEl.querySelector(`#${DOM_IDS.TUTORIAL_MODAL}`) || modal;
    titleEl = rootEl.querySelector(`#${DOM_IDS.TUTORIAL_TITLE}`) || titleEl;
    bodyEl = rootEl.querySelector(`#${DOM_IDS.TUTORIAL_BODY}`) || bodyEl;
    progressEl = rootEl.querySelector(`#${DOM_IDS.TUTORIAL_PROGRESS}`) || progressEl;
    nextBtn = rootEl.querySelector(`#${DOM_IDS.TUTORIAL_NEXT}`) || nextBtn;
    skipBtn = rootEl.querySelector(`#${DOM_IDS.TUTORIAL_SKIP}`) || skipBtn;
  }

  function clearTyping() {
    if (typingTimer) {
      clearInterval(typingTimer);
      typingTimer = null;
    }
    typingDone = true;
  }

  function typeBody(text, done) {
    clearTyping();
    if (!bodyEl) {
      if (done) done();
      return;
    }
    const content = text || '';
    // Prefer instant for long steps; light typewriter only if short & user has typewriter on.
    const disableTw = (() => {
      try {
        const s = JSON.parse(localStorage.getItem('game_settings') || '{}');
        if (s.disableTypewriter === undefined || s.disableTypewriter === null) return true;
        return !!s.disableTypewriter;
      } catch (_) {
        return true;
      }
    })();
    if (disableTw || content.length > 120) {
      bodyEl.textContent = content;
      typingDone = true;
      if (done) done();
      return;
    }
    typingDone = false;
    bodyEl.textContent = '';
    let i = 0;
    typingTimer = setInterval(() => {
      if (i < content.length) {
        bodyEl.textContent += content.charAt(i);
        i += 1;
      } else {
        clearTyping();
        if (done) done();
      }
    }, 28);
  }

  function renderStep() {
    ensureEls();
    const step = steps[index] || {};
    if (titleEl) titleEl.textContent = step.title || '戰鬥教學';
    if (progressEl) {
      progressEl.textContent = `${index + 1} / ${steps.length}`;
    }
    if (nextBtn) {
      nextBtn.textContent = index >= steps.length - 1 ? '開始戰鬥' : '下一步';
      nextBtn.disabled = false;
    }
    typeBody(step.body || '');
  }

  function finish() {
    clearTyping();
    hide();
    const cb = onDone;
    onDone = null;
    if (typeof cb === 'function') cb();
  }

  function next() {
    if (!typingDone && bodyEl) {
      // Tap once to finish typing
      clearTyping();
      const step = steps[index] || {};
      bodyEl.textContent = step.body || '';
      typingDone = true;
      return;
    }
    if (index >= steps.length - 1) {
      finish();
      return;
    }
    index += 1;
    renderStep();
  }

  function hide() {
    clearTyping();
    ensureEls();
    if (modal) {
      modal.classList.add('hidden');
      modal.classList.remove('flex');
    }
  }

  function show(stepList, doneCallback) {
    ensureEls();
    steps = Array.isArray(stepList) ? stepList.filter((s) => s && (s.body || s.title)) : [];
    if (!steps.length) {
      if (typeof doneCallback === 'function') doneCallback();
      return;
    }
    index = 0;
    onDone = doneCallback;
    if (modal) {
      modal.classList.remove('hidden');
      modal.classList.add('flex');
    }
    // Mount on body so fixed overlay is not clipped by combat shell.
    if (modal && modal.ownerDocument?.body && modal.parentElement !== modal.ownerDocument.body) {
      modal.ownerDocument.body.appendChild(modal);
    }
    renderStep();
  }

  nextBtn?.addEventListener('click', () => next());
  skipBtn?.addEventListener('click', () => finish());
  bodyEl?.addEventListener('click', () => {
    if (!typingDone) next();
  });

  return {
    show,
    hide,
    isVisible() {
      ensureEls();
      return !!(modal && !modal.classList.contains('hidden'));
    },
  };
}
