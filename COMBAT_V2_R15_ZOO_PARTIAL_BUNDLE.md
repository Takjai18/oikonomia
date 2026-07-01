# COMBAT_V2_R15_ZOO_PARTIAL_BUNDLE（局部審計 · Zoo 能力規格對齊）

> **目的**：審計 **Greenfield v1.1 Zoo 權威規格** — 糾正「神智 >70 才能發動」舊誤；驗證前後端一致  
> **日期**：2026-07-02 · **commit**：`137dfa9`  
> **Baseline**：假設已讀 `COMBAT_V2_AUDIT_BUNDLE.md` v15 或 `combat_greenfield_final.md` §1.1  
> **生成**：`python3 scripts/build_combat_v2_partial_bundles.py`

---

## 0. 給 Gemini 的指令

**權威規格（唔再報為 bug）**：
- **任何神智值均可發動 Zoo**（僅 `allow_zoo === false` 禁止）
- 神智加成（只影響 Zoo 傷害，不 gate 按鈕）：
  - ≤70 → ×1.0
  - >70 → ×1.3 · >80 → ×1.4 · >90 → ×1.5

**焦點問題**：
1. FSM `ACTION_USE_ZOO` guard 是否**只**檢查 `allow_zoo` / `submitted`，唔檢查神智？
2. `action_view.js` Zoo 按鈕是否僅在 `!allowZoo` 時 disable（唔因神智 <70）？
3. 前後端 `zoo_bonus_multiplier` 邊界是否一致（嚴格 `>70/>80/>90`）？
4. `routes/combat.py` 是否無 sanity gate 拒絕 `use_zoo`？
5. 邊界：神智恰好 70 / 80 / 90 應為哪個 tier？

**輸出**：【Critical】→【High/Medium】→【Low】→ 健康度 X/10

---

## 1. Greenfield 規格摘錄

- **Zoo 能力**（Greenfield 權威規格）：
  - **任何神智值均可發動 Zoo**——唔係「神智 >70 先用得」；僅當遭遇 `combat_settings.allow_zoo === false` 時禁止
  - Zoo 行動同樣經後端擲骰（0–3）並計入傷害結算；低神智仍有**暴走**風險（見下方暴走規則）
  - **神智加成乘數**（只喺選擇 Zoo 行動時套用，唔影響攻擊／防禦；神智 ≤70 仍可發動，但無加成）：
    | 神智 | Zoo 傷害乘數 |
    |------|-------------|
    | ≤70 | ×1.0 |
    | >70 | ×1.3 |
    | >80 | ×1.4 |
    | >90 | ×1.5 |
  - UI：**唔應**因神智不足而 disable Zoo 按鈕；神智 ≤70 顯示「可發動、無加成（×1.0）」；>70 顯示當前 tier 乘數

---

## 2. 後端乘數與結算

# models/combat.py (L422–L431)

def zoo_bonus_multiplier(sanity):
    sanity = int(sanity or 0)
    if sanity > 90:
        return 1.5
    if sanity > 80:
        return 1.4
    if sanity > 70:
        return 1.3
    return 1.0

# models/combat.py (L519–L531)

def choose_protagonist_auto_action(participant, combat_settings=None):
    combat_settings = combat_settings or {}
    sanity = int(participant.get("sanity") or 50)
    dice = roll_combat_dice()
    if sanity < 30:
        return {"action_type": "defend", "dice_result": dice}
    if sanity > 70 and combat_settings.get("allow_zoo", True):
        return {"action_type": "use_zoo", "dice_result": dice}
    if sanity < 40 and dice == 0:
        return {"action_type": "pass", "dice_result": dice}
    return {"action_type": "attack", "dice_result": dice}


# routes/combat.py (L410–L430)

            if datetime.now() < datetime.fromisoformat(actor_state["near_death_until"]):
                label = "AI 主角" if as_protagonist else "你"
                return jsonify({
                    "success": False,
                    "error": f"{label}已陷入瀕死，無法執行任何行動",
                }), 400
        except ValueError:
            pass

    if action_type == "use_zoo" and not settings.get("allow_zoo", True):
        return jsonify({"success": False, "error": "此戰鬥不允許 Zoo 能力"}), 400
    if as_protagonist and action_type == "use_item":
        return jsonify({"success": False, "error": "主角不可使用玩家物品"}), 400

    current_phase = int(combat.get("current_phase") or 0)
    if combat_action_already_submitted(combat_id, acting_id, current_phase):
        return jsonify({"success": False, "error": "本回合行動已提交"}), 400

    upsert_combat_action(
        combat_id,
        acting_id,
# models/combat.py (L1390–L1420)

                combat = append_combat_log(
                    combat,
                    f"{display} 消耗了 [{used_item_name}]！效果已生效",
                    log_type="item_use",
                )

        if action_type == "use_zoo":
            zoo_mult = zoo_bonus_multiplier(sanity)
            multiplier *= zoo_mult
            if zoo_mult > 1.0:
                combat = append_combat_log(
                    combat,
                    f"{display} 發動 Zoo 能力（×{zoo_mult}）",
                    log_type="zoo",
                )

        if action_type in ATTACK_ACTION_TYPES:
            stat_info = describe_attack_stat(player)
            dmg = calculate_attack_damage(
                player, enemy_resilience, multiplier=multiplier, item_bonus=item_bonus,
            )
            total_damage_to_enemy += dmg
            action_label = "Zoo 能力" if action_type == "use_zoo" else "攻擊"
            pro_tag = "（主角·自動）" if (
                player.get("is_protagonist")
                and player_squad_id not in (combat.get("phase_actions") or {})
            ) else ""
            combat = append_combat_log(
                combat,
                f"{display} {action_label}對{enemy_name}造成 {dmg} 點傷害"
                f"（{stat_info['label']} {stat_info['value']} · 骰 {dice}）{pro_tag}",
# models/combat.py (L1900–L1915)

            effect = item.get("effect_type")
            if effect == "power_up":
                item_bonus = abs(int(item.get("effect_value") or 0))
            elif effect in ("hp_up", "sanity_up"):
                return 0, meta

    if action_type in ATTACK_ACTION_TYPES or action_type == "use_item":
        if action_type == "use_zoo":
            multiplier *= zoo_bonus_multiplier(sanity)
        stat_info = describe_attack_stat(player)
        meta["attack_stat"] = stat_info["stat"]
        meta["attack_stat_value"] = stat_info["value"]
        meta["attack_stat_label"] = stat_info["label"]
        dmg = calculate_attack_damage(
            player, enemy_resilience, multiplier=multiplier, item_bonus=item_bonus,
        )

## 3. 前端 FSM + UI

# static/js/combat/state_machine.js (L457–L469)

    ACTION_USE_ZOO: {
      guard: (ctx) => {
        if (ctx.hud?.me?.submitted) return false;
        return ctx.hud?.allow_zoo !== false;
      },
      reduce: (ctx, meta) => ({
        ...ctx,
        phase: Phase.DICE_ROLLING,
        dice: { action: 'use_zoo', value: meta.dice, cosmetic: true },
        error: null,
      }),
      effects: () => [{ type: 'SHOW_DICE_ROLLING' }],
    },
/**
 * @file static/js/combat/views/action_view.js
 * @description 戰鬥主行動控制面板 — P2-2 Zoo / P2-3 主角代打
 */

import { Phase, TERMINAL_PHASES } from '../state_machine.js';
import { DOM_IDS } from '../selectors.js';

function zooBonusMultiplier(sanity) {
  if (sanity > 90) return 1.5;
  if (sanity > 80) return 1.4;
  if (sanity > 70) return 1.3;
  return 1.0;
}

function berserkChancePct(sanity) {
  if (sanity < 10) return 90;
  if (sanity < 20) return 50;
  if (sanity < 40) return 20;
  return 0;
}

const BUSY_PHASES = [
  Phase.DICE_ROLLING,
  Phase.DICE_CONFIRM,
  Phase.SUBMITTING,
  Phase.SETTLEMENT,
  Phase.WAITING_FOR_PLAYERS,
  Phase.ESCAPE_ATTEMPT,
];

export function createActionView(rootEl, handlers = {}) {
  const attackBtn = rootEl.querySelector(`#${DOM_IDS.ATTACK_BTN}`);
  const defendBtn = rootEl.querySelector(`#${DOM_IDS.DEFEND_BTN}`);
  const escapeBtn = rootEl.querySelector(`#${DOM_IDS.ESCAPE_BTN}`);
  const zooBtn = rootEl.querySelector(`#${DOM_IDS.ZOO_BTN}`);
  const itemBtn = rootEl.querySelector(`#${DOM_IDS.ITEM_BTN}`);
  const zooTip = rootEl.querySelector(`#${DOM_IDS.ZOO_TIP}`);
  const protagonistBar = rootEl.querySelector(`#${DOM_IDS.PROTAGONIST_BAR}`);
  const protagonistLabel = rootEl.querySelector(`#${DOM_IDS.PROTAGONIST_LABEL}`);
  const actionBtns = [attackBtn, defendBtn, escapeBtn, zooBtn, itemBtn];

  attackBtn?.addEventListener('click', () => { void handlers.onAttack?.(); });
  defendBtn?.addEventListener('click', () => { void handlers.onDefend?.(); });
  escapeBtn?.addEventListener('click', () => { void handlers.onEscape?.(); });
  zooBtn?.addEventListener('click', () => { void handlers.onZoo?.(); });
  itemBtn?.addEventListener('click', () => handlers.onItemClick?.());

  function setDisabled(disabled) {
    actionBtns.forEach((btn) => {
      if (btn) btn.disabled = disabled;
    });
  }

  function updateZooTip(ctx) {
    if (!zooTip) return;
    const me = ctx.hud?.me;
    if (!me || TERMINAL_PHASES.includes(ctx.phase)) {
      zooTip.className = 'hidden';
      zooTip.innerHTML = '';
      return;
    }

    const sanity = parseInt(me.sanity ?? 0, 10);
    const allowZoo = ctx.hud?.allow_zoo !== false;
    const zooMult = zooBonusMultiplier(sanity);
    const bChance = berserkChancePct(sanity);

    if (!allowZoo) {
      zooTip.className = 'hidden';
      zooTip.innerHTML = '';
      return;
    }

    if (bChance > 0) {
      zooTip.className = 'text-[10px] text-red-400 font-mono animate-pulse bg-red-950/20 border border-red-900/30 p-1.5 rounded-xl mx-3';
      zooTip.innerHTML = `⚠️ 神智偏低 (${sanity})：發動行動有 <b>${bChance}%</b> 暴走機率，可能無法對敵造成傷害！`;
    } else if (zooMult > 1.0) {
      zooTip.className = 'text-[10px] text-purple-400 font-mono bg-purple-950/20 border border-purple-900/30 p-1.5 rounded-xl mx-3';
      zooTip.innerHTML = `✨ Zoo 就緒：神智 ${sanity}，發動 Zoo 可獲 <b>×${zooMult}</b> 算力增益`;
    } else {
      zooTip.className = 'text-[10px] text-zinc-500 font-mono bg-zinc-900/40 border border-zinc-800 p-1.5 rounded-xl mx-3';
      zooTip.innerHTML = `Zoo 可發動（神智 ${sanity}）；神智 >70 才有加成（目前 ×1.0）`;
    }
  }

  function updateProtagonistBar(ctx) {
    if (!protagonistBar) return;
    const ctrlId = ctx.hud?.controllable_protagonist_id;
    const isLeader = !!ctx.hud?.me?.is_team_leader;
    const show = !!ctrlId && isLeader && !TERMINAL_PHASES.includes(ctx.phase);
    if (show) {
      protagonistBar.classList.remove('hidden');
      const members = ctx.hud?.members || {};
      const pro = members[ctrlId];
      const name = pro?.display_name || '主角';
      if (protagonistLabel) protagonistLabel.textContent = `代替 ${name} 行動`;
    } else {
      protagonistBar.classList.add('hidden');
    }
  }

  return {
    update(ctx) {
      const absorbing = TERMINAL_PHASES.includes(ctx.phase);
      const busy = BUSY_PHASES.includes(ctx.phase);
      const submitted = !!ctx.hud?.me?.submitted;
      const allowZoo = ctx.hud?.allow_zoo !== false;

      setDisabled(absorbing || busy || submitted);
      if (zooBtn) {
        zooBtn.disabled = absorbing || busy || submitted || !allowZoo;
        zooBtn.title = allowZoo ? '' : '此遭遇不允許 Zoo 能力';
      }

      updateZooTip(ctx);
      updateProtagonistBar(ctx);
    },
  };
}

## 4. 單元測試

# tests/combat_state_machine.test.js (L330–L355)

    assert.ok(effects.some((e) => e.type === 'SHOW_FAILED'));
  });

  it('IDLE + ACTION_USE_ZOO → DICE_ROLLING (P2-2)', () => {
    const ctx = {
      ...createInitialContext('c1'),
      hud: { me: { submitted: false, sanity: 80 }, allow_zoo: true },
    };
    const { ctx: next } = transition(ctx, 'ACTION_USE_ZOO', { action: 'use_zoo', dice: 2 });
    assert.equal(next.phase, Phase.DICE_ROLLING);
    assert.equal(next.dice.action, 'use_zoo');
  });

  it('IDLE + ACTION_USE_ZOO allowed below sanity 70 (no bonus tier)', () => {
    const ctx = {
      ...createInitialContext('c1'),
      hud: { me: { submitted: false, sanity: 55 }, allow_zoo: true },
    };
    assert.equal(canDispatch(ctx, 'ACTION_USE_ZOO', { action: 'use_zoo', dice: 1 }), true);
    const { ctx: next } = transition(ctx, 'ACTION_USE_ZOO', { action: 'use_zoo', dice: 1 });
    assert.equal(next.phase, Phase.DICE_ROLLING);
  });
});

describe('Settlement normalization', () => {
  it('uses round_settlement when damage > 0', () => {

---
*End of R15 Zoo · 2026-07-02 · `137dfa9`*
