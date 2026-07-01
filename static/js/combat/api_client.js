/** @file Combat API + resilient polling (AbortController, Visibility, backoff) */

const DEFAULT_POLL_IDLE_MS = 1200;
const DEFAULT_POLL_WAITING_MS = 800;

/** Align with templates/index.html fetchNoCache (`_cb=`). */
function appendCacheBust(url) {
  const sep = url.includes('?') ? '&' : '?';
  return `${url}${sep}_cb=${Date.now()}`;
}

async function fetchJson(url, options = {}) {
  const res = await fetch(appendCacheBust(url), {
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      'X-Requested-With': 'XMLHttpRequest',
      ...(options.headers || {}),
    },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.error || data.message || `HTTP ${res.status}`);
    err.status = res.status;
    err.payload = data;
    throw err;
  }
  return data;
}

export const CombatApi = {
  async start(encounterId, body = {}) {
    return fetchJson('/combat/start', {
      method: 'POST',
      body: JSON.stringify({ encounter_id: encounterId, ...body }),
    });
  },

  async submit({ combatId, actionType, itemId, asProtagonist }) {
    return fetchJson('/combat/submit_action', {
      method: 'POST',
      body: JSON.stringify({
        combat_id: combatId,
        action_type: actionType,
        item_id: itemId,
        as_protagonist: asProtagonist,
      }),
    });
  },

  async status(combatId, signal) {
    const q = combatId ? `?combat_id=${combatId}` : '';
    return fetchJson(`/combat/status${q}`, { signal });
  },

  async summonGm(combatId) {
    return fetchJson('/combat/summon_gm', {
      method: 'POST',
      body: JSON.stringify({ combat_id: combatId }),
    });
  },

  /** P2 Backlog: GM 特權遠端覆蓋網路調用 */
  async overrideTraumaEnding({ teamId, protagonistKey, targetTrauma, targetEndingType }) {
    return fetchJson('/gm/api/override_trauma_ending', {
      method: 'POST',
      body: JSON.stringify({
        team_id: teamId,
        protagonist_key: protagonistKey,
        target_trauma: targetTrauma,
        target_ending_type: targetEndingType,
      }),
    });
  },
};

/**
 * Resilient polling manager per combat_greenfield_final.md §5.2
 */
export class ResilientPollingManager {
  /**
   * @param {{ onTick: (data: object) => void, onError?: (err: Error) => void }} handlers
   */
  constructor(handlers) {
    this.handlers = handlers;
    this.combatId = null;
    this.timerId = null;
    this.abortController = null;
    this.stopped = true;
    this.backoffMs = 0;
    this.maxBackoffMs = 16000;
    this.phase = 'IDLE';
    this._onVisibility = this._onVisibility.bind(this);
    document.addEventListener('visibilitychange', this._onVisibility);
  }

  destroy() {
    this.stop();
    document.removeEventListener('visibilitychange', this._onVisibility);
  }

  setPhase(phase) {
    this.phase = phase;
  }

  intervalForPhase(phase, snapshot) {
    if (phase === 'WAITING_FOR_PLAYERS' || snapshot?.waiting_for_teammates) {
      return DEFAULT_POLL_WAITING_MS;
    }
    return DEFAULT_POLL_IDLE_MS;
  }

  start(combatId) {
    this.combatId = combatId;
    this.stopped = false;
    this.backoffMs = 0;
    this._schedule(0);
  }

  stop() {
    this.stopped = true;
    clearTimeout(this.timerId);
    this.timerId = null;
    this._abortInflight();
  }

  pause() {
    clearTimeout(this.timerId);
    this.timerId = null;
  }

  resume() {
    if (!this.stopped && this.combatId) this._schedule(0);
  }

  async tick() {
    if (this.stopped || !this.combatId) return;
    if (document.hidden) return;

    this._abortInflight();
    this.abortController = new AbortController();

    try {
      const data = await CombatApi.status(this.combatId, this.abortController.signal);
      this.backoffMs = 0;
      this.handlers.onTick(data);
    } catch (err) {
      if (err.name === 'AbortError') return;
      this.backoffMs = Math.min(
        this.maxBackoffMs,
        this.backoffMs ? this.backoffMs * 2 : 1000,
      );
      this.handlers.onError?.(err);
    } finally {
      if (!this.stopped) {
        const wait = this.intervalForPhase(this.phase) + this.backoffMs;
        this._schedule(wait);
      }
    }
  }

  _schedule(ms) {
    clearTimeout(this.timerId);
    this.timerId = setTimeout(() => this.tick(), ms);
  }

  _abortInflight() {
    if (this.abortController) {
      this.abortController.abort();
      this.abortController = null;
    }
  }

  _onVisibility() {
    if (!document.hidden && !this.stopped) {
      this._schedule(0);
    }
  }
}