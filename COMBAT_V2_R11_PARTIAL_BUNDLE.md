# COMBAT_V2_R11_PARTIAL_BUNDLE（局部審計 · 營會現場風險）

> **用途**：Gemini **【審計模式】** — 只貼本檔，唔貼 `COMBAT_V2_AUDIT_BUNDLE.md` 全文  
> **日期**：2026-07-01  
> **Baseline**：假設已讀 **COMBAT_V2_AUDIT_BUNDLE v11**（SSOT 在 repo，首次 onboarding 用 v11 全文）  
> **生成**：`python3 scripts/build_combat_v2_r11_partial_bundle.py`

---

## 0. 給 Gemini 的指令（R11 — 局部 Audit）

**輸出格式**：【Critical】→【High/Medium】→【Low】→ **健康度總評 X/10**  
**威脅模型**：玩家可開 DevTools；GM override 需 `gm_session_valid`；假設 client 不可信。

### Scope A — GM 現場嵌入式特權面板
- `victory_view.js` `showFailed` + 三重點擊解鎖
- `routes/gm.py` `gm_override_trauma_ending_api`
- 焦點：`team_id` fallback、`COMBAT_RESET`、同瀏覽器 GM session、403 阻斷

### Scope B — 超時自動防禦（戶外 poll）
- `index.js` `triggerTimeoutAutomaticDefense` + `pollTick` phase_expired 路徑
- 焦點：double-submit、poll 延遲、與 `SUBMITTING` 狀態互斥

### Scope C — Co-op 併發 resolve
- `models/combat.py` `_claim_player_phase_resolution` + `maybe_resolve_player_phase`
- 焦點：CAS 鎖、stale resolving、兩人同秒 submit

### 已知缺口（審計時標註即可，唔阻 deploy）
- 無 T15 E2E（真 GM session override 流程）
- `combat_v1` rollback 目錄不存在；`COMBAT_V2=0` 僅顯示聯繫 GM
- `models/combat.py` ~2000 行 — Step 3/4 拆分屬營會後技術債

### 測試基線（R11）
```bash
npm run test:combat                              # 15/15
./venv/bin/python3 scripts/test_combat_flow.py   # 264/264
./venv/bin/python3 scripts/test_db_hardening.py  # 8/8
npm run test:e2e:v2                              # T8–T14
```

> 其他 Partial 見 `COMBAT_V2_PARTIAL_INDEX.md`（R12-A～D）

---

## 1. Scope A — GM 現場救援



===== FILE: static/js/combat/views/victory_view.js =====

/**
 * @file static/js/combat/views/victory_view.js
 * @description 戰鬥結局（勝利/失敗/致命崩潰）全屏渲染器，已解耦舊版 Section 依賴
 */

import {
  isValidProtagonistRouteKey,
  PROTAGONIST_ROUTE_KEY_HINT,
} from '../constants.js';
import { DOM_IDS } from '../selectors.js';
import { showToast } from '../toast.js';

export function createVictoryView(rootEl) {
  const panel = rootEl.querySelector(`#${DOM_IDS.VICTORY_PANEL}`);
  const failedPanel = rootEl.querySelector(`#${DOM_IDS.FAILED_PANEL}`);

  function escapeHtml(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  async function resolveAuthoritativeTeamId(app) {
    const hint = String(
      app.ctx.hud?.me?.team_id || app.ctx.hud?.team_id || '',
    ).trim().toUpperCase();
    const inputFn = typeof window.showInputModal === 'function' ? window.showInputModal : null;
    const confirmFn = typeof window.showConfirmModal === 'function' ? window.showConfirmModal : null;
    if (!inputFn || !confirmFn) {
      showToast('無法開啟 GM 核對視窗，請登入後台手動處理', 'error');
      return null;
    }

    const raw = await inputFn({
      title: 'GM 現場救援 — 小隊編號核對',
      placeholder: '例如 TEAM-02',
      defaultValue: hint,
      maxLength: 32,
    });
    const clean = String(raw || '').trim().toUpperCase();
    if (!clean) {
      showToast('操作已取消，未執行任何修改。', 'warn');
      return null;
    }

    const agreed = await confirmFn({
      title: '最終確認',
      message: `確定要對小隊【${clean}】執行高特權覆蓋？請務必核對現場玩家識別證。`,
      confirmLabel: '確認執行',
      danger: true,
    });
    if (!agreed) return null;
    return clean;
  }

  async function resolveProtagonistKeyForOverride(app) {
    const route = String(app.ctx.hud?.route || '').trim().toLowerCase();
    if (isValidProtagonistRouteKey(route)) return route;
    const promptFn = typeof window.showInputModal === 'function' ? window.showInputModal : null;
    if (!promptFn) {
      showToast('無法取得主角路線，請 GM 後台手動處理', 'error');
      return null;
    }
    const raw = await promptFn({
      title: '請輸入欲重置的主角代號',
      placeholder: PROTAGONIST_ROUTE_KEY_HINT,
      maxLength: 10,
    });
    const key = String(raw || '').trim().toLowerCase();
    if (!isValidProtagonistRouteKey(key)) {
      showToast(`主角代號無效，請輸入 ${PROTAGONIST_ROUTE_KEY_HINT}`, 'error');
      return null;
    }
    return key;
  }

  return {
    showVictory(data) {
      if (!panel) return;
      const narrative = data?.narrative || '你們成功看穿了這場衝突背後的情緒勒索與邊界扭曲。';

      panel.className = 'fixed inset-0 z-[85] flex items-center justify-center bg-zinc-950/90 p-4 backdrop-blur-sm';
      panel.innerHTML = `
        <div class="bg-zinc-900 border border-emerald-500/30 rounded-3xl p-6 max-w-md w-full text-center shadow-2xl">
          <div class="text-6xl mb-3">🎉</div>
          <h2 class="text-2xl font-black text-emerald-400 tracking-wider mb-2">戰鬥勝利</h2>
          <p class="text-sm text-zinc-300 mb-6 leading-relaxed bg-zinc-950/40 p-4 rounded-2xl border border-zinc-800">${escapeHtml(narrative)}</p>
          <button type="button" id="combat-v2-victory-exit"
                  class="min-h-11 w-full rounded-2xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold tracking-widest active:scale-[0.98] transition-all shadow-lg shadow-emerald-950">
            ⛺ 離開戰場並安全返回
          </button>
        </div>`;

      panel.querySelector('#combat-v2-victory-exit')?.addEventListener('click', () => {
        window.combatV2?.exitToLobby?.();
      });
    },

    showDefeat(data) {
      if (!panel) return;
      const narrative = data?.narrative || '心理界線宣告失守，全隊陷入混亂。';

      panel.className = 'fixed inset-0 z-[85] flex items-center justify-center bg-zinc-950/90 p-4 backdrop-blur-sm';
      panel.innerHTML = `
        <div class="bg-zinc-900 border border-red-500/30 rounded-3xl p-6 max-w-md w-full text-center shadow-2xl">
          <div class="text-6xl mb-3">💀</div>
          <h2 class="text-2xl font-black text-red-400 tracking-wider mb-2">戰鬥失敗</h2>
          <p class="text-sm text-zinc-300 mb-6 leading-relaxed bg-zinc-950/40 p-4 rounded-2xl border border-zinc-800">${escapeHtml(narrative)}</p>
          <button type="button" id="combat-v2-defeat-exit"
                  class="min-h-11 w-full rounded-2xl bg-zinc-800 hover:bg-zinc-700 text-zinc-300 font-bold tracking-widest active:scale-[0.98] transition-all">
            ⛺ 撤退回遭遇大廳
          </button>
        </div>`;

      panel.querySelector('#combat-v2-defeat-exit')?.addEventListener('click', () => {
        window.combatV2?.exitToLobby?.();
      });
    },

    showFailed(members) {
      document.getElementById('combat-near-death-overlay')?.classList.add('hidden');

      if (!failedPanel) return;
      const list = (members || []).map((m) => `<li class="text-red-300 font-mono">${escapeHtml(m)}</li>`).join('');

      failedPanel.className = 'fixed inset-0 z-[95] flex items-center justify-center bg-black/95 p-4';
      failedPanel.innerHTML = `
        <div class="bg-zinc-900 border-2 border-red-600 rounded-3xl p-6 max-w-md w-full shadow-2xl shadow-red-950">
          <div class="flex items-center gap-3 border-b border-zinc-800 pb-3 mb-4">
            <span class="text-3xl">⚠️</span>
            <div>
              <h2 class="text-lg font-black text-red-500">絕對規則阻斷：全隊瀕死</h2>
              <p class="text-[10px] text-zinc-500 font-mono">INV-D PREEMPTIVE INTERRUPT TRIGGERED</p>
            </div>
          </div>
          <p class="text-sm text-zinc-400 mb-2 leading-relaxed">
            系統偵測到以下關鍵角色生命值歸零，戰鬥已即時強制終止：
          </p>
          <ul class="text-sm bg-zinc-950/60 border border-zinc-800/80 p-3 rounded-xl mb-4 list-disc pl-5 space-y-1">${list}</ul>

          <div id="gm-embedded-override-panel" class="mb-4 p-3 bg-zinc-950 rounded-xl border border-zinc-800 hidden">
            <div class="text-[10px] text-amber-500 font-bold mb-1.5 tracking-wider">🛠️ 工作人員特權干預</div>
            <div class="grid grid-cols-2 gap-2">
              <button type="button" id="gm-btn-clear-ending" class="py-1.5 px-2 bg-emerald-950/60 hover:bg-emerald-900 text-emerald-400 rounded-lg text-[11px] font-mono border border-emerald-900/50">
                ✨ 解除結局鎖定
              </button>
              <button type="button" id="gm-btn-clear-trauma" class="py-1.5 px-2 bg-purple-950/60 hover:bg-purple-900 text-purple-400 rounded-lg text-[11px] font-mono border border-purple-900/50">
                🧠 創傷主表清零
              </button>
            </div>
          </div>

          <div class="grid gap-2">
            <button type="button" id="combat-v2-failed-lobby"
                    class="min-h-11 rounded-2xl bg-zinc-800 hover:bg-zinc-700 text-white text-sm font-medium transition-colors">
              ⛺ 強制返回大廳 (暫時脫離)
            </button>
            <button type="button" id="combat-v2-failed-gm"
                    class="min-h-11 rounded-2xl bg-red-950/40 hover:bg-red-900/40 border border-red-900/60 text-red-400 text-xs font-bold tracking-widest transition-colors">
              📢 離線呼叫 GM 工作人員
            </button>
          </div>
        </div>`;

      let clickCount = 0;
      failedPanel.querySelector('h2')?.addEventListener('click', () => {
        clickCount += 1;
        if (clickCount >= 3) {
          failedPanel.querySelector('#gm-embedded-override-panel')?.classList.remove('hidden');
        }
      });

      failedPanel.querySelector('#combat-v2-failed-lobby')?.addEventListener('click', () => {
        window.combatV2?.exitToLobby?.();
      });

      failedPanel.querySelector('#combat-v2-failed-gm')?.addEventListener('click', async () => {
        const btn = failedPanel.querySelector('#combat-v2-failed-gm');
        if (btn) {
          btn.disabled = true;
          btn.textContent = '⏳ 訊號發送中...';
        }
        await window.combatV2?.summonGm?.();
        if (btn) btn.textContent = '📢 已發送救援請求';
      });

      failedPanel.querySelector('#gm-btn-clear-ending')?.addEventListener('click', async () => {
        const app = document.getElementById('combat-root-v2')?.__combat_app_instance__;
        if (!app) return;
        const teamId = await resolveAuthoritativeTeamId(app);
        if (!teamId) return;
        void app.executeGmOverride({ teamId, targetEndingType: 'clear' });
      });

      failedPanel.querySelector('#gm-btn-clear-trauma')?.addEventListener('click', async () => {
        const app = document.getElementById('combat-root-v2')?.__combat_app_instance__;
        if (!app) return;
        const teamId = await resolveAuthoritativeTeamId(app);
        if (!teamId) return;
        const protagonistKey = await resolveProtagonistKeyForOverride(app);
        if (!protagonistKey) return;
        void app.executeGmOverride({ teamId, protagonistKey, targetTrauma: 0 });
      });
    },

    hideAll() {
      if (panel) {
        panel.className = 'hidden';
        panel.innerHTML = '';
      }
      if (failedPanel) {
        failedPanel.className = 'hidden';
        failedPanel.innerHTML = '';
      }
    },
  };
}


===== EXCERPT: static/js/combat/index.js — executeGmOverride =====

# static/js/combat/index.js (L686–L704)

  async executeGmOverride(opts) {
    try {
      showToast('正在發射特權變更指令…', 'info');
      const data = await CombatApi.overrideTraumaEnding(opts);
      if (data.success) {
        showToast(data.message || '特權歷史重組成功！', 'info');

        if (opts.targetEndingType === 'clear') {
          this.dispatch('COMBAT_RESET', { combatId: this.ctx.combatId });
        } else if (this.ctx.combatId) {
          const snapshot = await CombatApi.status(this.ctx.combatId);
          this.pollTick(snapshot);
        }
      } else {
        showToast(data.error || '指令被後端網關拒絕', 'error');
      }
    } catch (err) {
      showToast(err.message || 'GM 特權通訊失敗', 'error');
    }


===== EXCERPT: static/js/combat/api_client.js — overrideTraumaEnding =====

# static/js/combat/api_client.js (L65–L94)

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


===== EXCERPT: routes/gm.py — gm_override_trauma_ending_api =====

# routes/gm.py (L770–L922)

def gm_override_trauma_ending_api():
    """
    [GM 特權網關] 權威人工覆蓋：手動扭轉隊伍創傷數值與結局鎖定狀態。
    寫入專項特權審計日誌，並向全營廣播界線重組事件。
    """
    if not gm_session_valid(session):
        clear_gm_session(session)
        return jsonify({
            "success": False,
            "error": "拒絕存取：缺少 GM 權限憑證",
        }), 403

    body = request.json if request.is_json else {}
    team_id = normalize_team_id(body.get("team_id") or "")
    protagonist_key = (body.get("protagonist_key") or "").strip().lower()

    if not team_id:
        return jsonify({"success": False, "error": "缺少 team_id"}), 400

    target_trauma = body.get("target_trauma")
    target_ending_type = (body.get("target_ending_type") or "").strip().lower() or None

    if target_trauma is not None:
        if protagonist_key not in ("iggy", "marah"):
            return jsonify({
                "success": False,
                "error": "調整創傷必須指定有效的主角 key ('iggy'|'marah')",
            }), 400
        try:
            target_trauma = max(0, int(target_trauma))
        except (TypeError, ValueError):
            return jsonify({"success": False, "error": "無效的創傷數值"}), 400

    if target_ending_type and target_ending_type not in (
        "clear", "bad_ending", "normal_ending",
    ):
        return jsonify({"success": False, "error": "無效的 target_ending_type"}), 400

    if target_trauma is None and not target_ending_type:
        return jsonify({"success": False, "error": "缺少有效的覆蓋變更指令"}), 400

    now = datetime.now().isoformat()
    raw_operator = (session.get("gm_operator") or session.get("squad_id") or "").strip()
    gm_operator = re.sub(r"[^a-zA-Z0-9_\-]", "", raw_operator)
    if not gm_operator:
        current_app.logger.error(
            "CRITICAL PRIVILEGE VIOLATION: Anonymous or malformed GM operator "
            "bypass attempted from IP %s at %s (raw=%r)",
            request.remote_addr,
            now,
            raw_operator,
        )
        return jsonify({
            "success": False,
            "error": "資安審計攔截：未能識別當前工作人員身分，操作已遭封鎖",
        }), 403

    def _override_tx(conn):
        c = conn.cursor()

        team_exists = c.execute(
            "SELECT 1 FROM teams WHERE team_id = ?",
            (team_id,),
        ).fetchone()
        if not team_exists:
            return False, "找不到指定的隊伍編號"

        log_parts = []

        if target_trauma is not None:
            old_row = c.execute(
                """SELECT trauma_count FROM protagonist_states
                   WHERE team_id = ? AND protagonist = ?""",
                (team_id, protagonist_key),
            ).fetchone()
            old_trauma = int(old_row[0] or 0) if old_row else 0

            c.execute(
                """INSERT INTO protagonist_states
                   (team_id, protagonist, hp, max_hp, sanity, trauma_count, is_active, last_updated)
                   VALUES (?, ?, 100, 100, 100, ?, 1, ?)
                   ON CONFLICT(team_id, protagonist) DO UPDATE SET
                       trauma_count = excluded.trauma_count,
                       last_updated = excluded.last_updated""",
                (team_id, protagonist_key, target_trauma, now),
            )

            c.execute(
                """INSERT INTO protagonist_trauma_log
                   (team_id, protagonist, delta, reason, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    team_id,
                    protagonist_key,
                    target_trauma - old_trauma,
                    f"GM_OVERRIDE_BY_{gm_operator}",
                    now,
                ),
            )
            log_parts.append(
                f"🧠 {protagonist_key} 創傷強制變更: {old_trauma} -> {target_trauma}",
            )

        if target_ending_type:
            if target_ending_type == "clear":
                c.execute(
                    "UPDATE teams SET ending_type = NULL, ending_locked_at = NULL WHERE team_id = ?",
                    (team_id,),
                )
                log_parts.append("🌑 結局鎖定狀態徹底解除重置")
            elif target_ending_type == "bad_ending":
                c.execute(
                    """UPDATE teams SET ending_type = 'bad_ending', ending_locked_at = ?
                       WHERE team_id = ?""",
                    (now, team_id),
                )
                log_parts.append("🌑 強制鎖定為陰影結局 (bad_ending)")
            elif target_ending_type == "normal_ending":
                c.execute(
                    """UPDATE teams SET ending_type = 'normal_ending', ending_locked_at = ?
                       WHERE team_id = ?""",
                    (now, team_id),
                )
                log_parts.append("☀️ 強制鎖定為常規結局 (normal_ending)")

        summary_log = "; ".join(log_parts)
        return True, summary_log

    def _run():
        with immediate_transaction(settings.db_path) as conn:
            return _override_tx(conn)

    success, audit_msg = with_db_retry(_run)

    if not success:
        return jsonify({"success": False, "error": audit_msg}), 400

    create_global_event(
        title=f"🛠️ GM 人工干預：隊伍 [{team_id}] 歷史重組",
        description=(
            f"工作人員 {gm_operator} 啟動特權網關調整該隊邊界：{audit_msg}。"
        ),
        effect_type="announcement",
        effect_value=0,
        created_by=gm_operator,
    )

    return jsonify({
        "success": True,
        "message": f"覆蓋指令發放成功：{audit_msg}",
        "team_id": team_id,
        "timestamp": now,
    })


## 2. Scope B — 超時自動防禦

# static/js/combat/index.js (L383–L393)

  triggerTimeoutAutomaticDefense() {
    if (this.hasTriggeredTimeoutDefense) return;

    const myCurrentAction = this.ctx.hud?.me?.action_type;
    if (myCurrentAction === 'failed_escape') {
      console.warn(
        '[FSM] Player is in failed_escape recovery — automatic defense suppressed.',
      );
      this.hasTriggeredTimeoutDefense = true;
      return;
    }
# static/js/combat/index.js (L481–L491)

  pollTick(snapshot) {
    if (!snapshot || snapshot.success === false) return;

    if (this.submittingActive) {
      if (this.debug) console.log('[CombatV2] poll muted during in-flight submit');
      if (snapshot.enemy || snapshot.my_state || snapshot.member_states) {
        this.ctx.hud = extractHud(snapshot);
        this.views.hud?.update(this.ctx, { hpOnly: true });
      }
      return;
    }


## 3. Scope C — Co-op 併發 resolve

# models/combat.py (L710–L724)

def _claim_player_phase_resolution(combat_id):
    with immediate_transaction() as conn:
        row = conn.execute(
            "SELECT status FROM combats WHERE id = ?",
            (combat_id,),
        ).fetchone()
        if not row or row[0] != "player_phase":
            return False
        cur = conn.execute(
            "UPDATE combats SET status = ? WHERE id = ? AND status = 'player_phase'",
            (COMBAT_STATUS_RESOLVING, combat_id),
        )
        return cur.rowcount > 0


# models/combat.py (L966–L1016)

def maybe_resolve_player_phase(combat_id, combat_settings=None, cached_participants=None):
    """
    Authoritative resolve gate for routes: re-read DB snapshot, resolve at most once.
    Readiness is validated inside _claim_ready_player_phase_resolution (CAS + TX).
    Returns (combat, winner).
    """
    _recover_stale_resolving_combat(combat_id)
    combat = get_combat(combat_id)
    if not combat:
        return None, None

    initial_phase = int(combat.get("current_phase") or 0)
    status = combat.get("status")
    if status == "ended":
        return combat, combat.get("winner")
    if status == COMBAT_STATUS_RESOLVING:
        return _wait_after_peer_resolve(combat_id, initial_phase)
    if status != "player_phase":
        return combat, None

    encounter = load_encounter(combat.get("encounter_id") or "")
    settings = combat_settings or (encounter or {}).get("combat_settings", {})

    if cached_participants is None:
        cached_participants = get_combat_participants(combat) or []
    claimed, snapshot = _claim_ready_player_phase_resolution(
        combat_id, settings, cached_participants=cached_participants,
    )
    if not claimed:
        combat = get_combat(combat_id) or snapshot
        if combat and int(combat.get("current_phase") or 0) > initial_phase:
            return combat, combat.get("winner") if combat.get("status") == "ended" else None
        if combat and combat.get("status") == COMBAT_STATUS_RESOLVING:
            return _wait_after_peer_resolve(combat_id, initial_phase)
        return combat, None

    snap_phase = int((snapshot or {}).get("current_phase") or initial_phase)
    if snap_phase != initial_phase:
        _release_player_phase_resolution(combat_id)
        return get_combat(combat_id), None

    try:
        combat, winner = _resolve_player_phase_body(combat_id)
    except Exception:
        _release_player_phase_resolution(combat_id)
        raise
    if combat and combat.get("status") == COMBAT_STATUS_RESOLVING and winner is None:
        return _wait_after_peer_resolve(combat_id, initial_phase)
    return combat, winner




## 4. E2E 參考 — T14 特權阻斷

# tests/combat_v2.spec.js (L498–L560)

    const toast = page.locator('[data-testid="combat-toast"]');
    await expect(toast).toBeVisible();
    await expect(toast).toContainText('只有隊長特權才能啟動主角代打模式');
    await expect(page.locator('#combat-v2-attack-btn')).toBeEnabled();
  });

  test('T14: rogue player GM override endpoint hard-blocked', async ({ page }) => {
    await page.route('**/gm/api/override_trauma_ending', async (route) => {
      await route.fulfill({
        status: 403,
        contentType: 'application/json',
        body: JSON.stringify({
          success: false,
          error: '拒絕存取：缺少 GM 權限憑證',
        }),
      });
    });

    const triggerHack = await page.evaluate(async (payload) => {
      try {
        const res = await fetch('/gm/api/override_trauma_ending', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        return { status: res.status, data: await res.json() };
      } catch (e) {
        return { status: 500, error: e.message };
      }
    }, { team_id: 'TEAM-01', target_ending_type: 'clear' });

    expect(triggerHack.status).toBe(403);
    expect(triggerHack.data.success).toBe(false);
  });
});


---
*End of COMBAT_V2_R11_PARTIAL_BUNDLE · 2026-07-01*
