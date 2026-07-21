#!/usr/bin/env python3
"""PR-6: Remove legacy combat inline script/HTML from templates/index.html."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "templates" / "index.html"

COMBAT_MODULE_HTML = """                <!-- COMBAT V2 — Greenfield mount (PR-6) -->
                <div id="combat-module-container" class="w-full min-h-screen bg-zinc-950 text-white">
                    {% if combat_v2_enabled %}
                        {% include 'combat_screen.html' %}
                    {% else %}
                        <div id="combat-v1-deprecated-fallback" class="p-6 text-center text-zinc-500">
                            <p>戰鬥系統正在升級中，請聯繫 GM 開啟 COMBAT_V2 特性標記。</p>
                        </div>
                    {% endif %}
                </div>
"""

COMBAT_LOBBY_BRIDGE_JS = r"""    // ── Combat lobby bridge (PR-6: legacy inline combat script removed) ──
    let pendingEncounterId = null;
    let currentCombatId = null;

    window.AppRouter = {
        navigateTo(route) {
            console.log(`[Router] 路由跳轉至: ${route}`);
            if (route === 'dashboard' || route === 'combat-hub') {
                const lobby = document.getElementById('combat-lobby');
                if (lobby) lobby.classList.remove('hidden');
                document.getElementById('combat-root-v2')?.classList.add('hidden');
            }
        },
    };

    function appendCacheBust(url) {
        const sep = url.includes('?') ? '&' : '?';
        return `${url}${sep}_cb=${Date.now()}`;
    }

    const FETCH_NO_CACHE_HEADERS = {
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0',
        'X-Requested-With': 'XMLHttpRequest',
    };

    function fetchNoCache(url, options = {}) {
        return fetch(appendCacheBust(url), {
            credentials: 'same-origin',
            ...options,
            headers: { ...FETCH_NO_CACHE_HEADERS, ...(options.headers || {}) },
        });
    }

    async function onLegacyEncounterTrigger(data) {
        if (window.combatV2?.isEnabled?.()) {
            const lobby = document.getElementById('combat-lobby');
            if (lobby) lobby.classList.add('hidden');
            if (data.combat_id) currentCombatId = data.combat_id;
            await window.combatV2.onCombatStarted(data);
        }
    }

    function exitCombatScreen() {
        if (window.combatV2?.isEnabled?.()) {
            window.combatV2.exitToLobby();
            return;
        }
        setVisible(document.getElementById('combat-result-panel'), false);
        setVisible(document.getElementById('combat-precheck-modal'), false);
        setVisible(document.getElementById('combat-near-death-overlay'), false);
        setVisible(document.getElementById('combat-lobby'), true);
        document.getElementById('combat-root-v2')?.classList.add('hidden');
        currentCombatId = null;
        pendingEncounterId = null;
        loadEncounters();
    }

    async function loadCombatPage(combatId) {
        if (combatId) currentCombatId = combatId;
        setVisible(document.getElementById('combat-lobby'), true);
        setVisible(document.getElementById('combat-result-panel'), false);
        setVisible(document.getElementById('combat-precheck-modal'), false);
        setVisible(document.getElementById('combat-near-death-overlay'), false);
        document.getElementById('combat-root-v2')?.classList.add('hidden');
        const fresh = await refreshSquadFromServer();
        if (fresh) {
            initPlayerAvatar();
            updateDashboard(fresh);
        }
        await loadEncounters();
        if (combatId && window.combatV2?.isEnabled?.()) {
            setVisible(document.getElementById('combat-lobby'), false);
            await window.combatV2.onCombatStarted({ combat_id: combatId });
        }
    }

    async function loadEncounters() {
        const container = document.getElementById('encounter-list');
        if (!container) return;
        container.innerHTML = '<div class="text-zinc-400">載入 Encounter...</div>';

        try {
            const res = await fetch('/encounters', { credentials: 'same-origin' });
            const data = await res.json();
            if (!data.success) {
                container.innerHTML = '<div class="text-red-400">載入失敗</div>';
                return;
            }

            container.innerHTML = '';
            if (data.progress_hint) {
                const hint = document.createElement('div');
                hint.className = 'text-xs text-zinc-400 cartoon-box p-3 mb-3 leading-relaxed';
                hint.textContent = data.progress_hint;
                container.appendChild(hint);
            }

            if (!data.encounters || data.encounters.length === 0) {
                const empty = document.createElement('div');
                empty.className = 'text-zinc-400 cartoon-box p-6 text-center';
                empty.textContent = '暫無可用遭遇戰';
                container.appendChild(empty);
                return;
            }

            data.encounters.forEach(enc => {
                const card = document.createElement('div');
                card.className = 'cartoon-box p-5';
                const badges = [];
                if (enc.is_practice || enc.replayable) {
                    badges.push('<span class="text-xs px-2 py-1 bg-sky-900/50 text-sky-300 rounded-full shrink-0">可重複練習</span>');
                } else if (enc.completed) {
                    badges.push('<span class="text-xs px-2 py-1 bg-emerald-900/50 text-emerald-400 rounded-full shrink-0">已完成</span>');
                }
                const canStart = enc.replayable || !enc.completed;
                const btnLabel = enc.replayable && enc.completed ? '再練一次' : '開始 Encounter';
                const btn = canStart
                    ? `<button onclick="startEncounter('${enc.encounter_id}')" class="mt-3 px-4 py-2 theme-btn-primary rounded-xl text-sm font-medium">${btnLabel}</button>`
                    : '';
                const hpHint = enc.enemy_hp
                    ? `<div class="text-xs text-zinc-500 mt-1">敵人 HP：${Number(enc.enemy_hp).toLocaleString('zh-Hant')}</div>`
                    : '';
                card.innerHTML = `
                    <div class="flex items-start justify-between gap-2 mb-2 flex-wrap">
                        <div class="font-bold text-lg">${enc.title || enc.encounter_id}</div>
                        <div class="flex flex-wrap gap-1">${badges.join('')}</div>
                    </div>
                    <div class="text-xs text-zinc-500 mb-2">${enc.location_hint || ''}</div>
                    <p class="text-sm text-zinc-300">${enc.description || ''}</p>
                    ${enc.enemy_name ? `<div class="text-xs text-red-400/80 mt-2">敵人：${enc.enemy_name}</div>` : ''}
                    ${hpHint}
                    ${btn}
                `;
                container.appendChild(card);
            });

            if (data.active_combat) {
                const hint = document.createElement('div');
                hint.className = 'text-sm text-amber-400 cartoon-box p-4 cursor-pointer';
                hint.innerHTML = '⚔️ 進行中的戰鬥 — <span class="underline">點擊繼續</span>';
                const resumeCombatId = data.active_combat_id;
                hint.onclick = async () => {
                    if (resumeCombatId) currentCombatId = resumeCombatId;
                    showSection('combat', { skipCombatLobbyLoad: true });
                    if (window.combatV2?.isEnabled?.()) {
                        setVisible(document.getElementById('combat-lobby'), false);
                        await window.combatV2.onCombatStarted({ combat_id: resumeCombatId || currentCombatId });
                    } else {
                        showToast('請聯繫 GM 開啟 COMBAT_V2', 'error');
                    }
                };
                container.prepend(hint);
            }
        } catch (e) {
            container.innerHTML = '<div class="text-red-400">載入失敗</div>';
        }
    }

    async function startEncounter(encounterId) {
        const agreed = await showConfirmModal({
            title: '開始遭遇戰',
            message: '確定開始此 Encounter？',
        });
        if (!agreed) return;
        pendingEncounterId = encounterId;
        const res = await fetch('/combat/start', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ encounter_id: encounterId }),
        });
        const data = await res.json();
        if (!data.success) {
            showToast(data.error || '無法開始', 'error');
            return;
        }
        currentCombatId = data.combat_id;
        showSection('combat', { skipCombatLobbyLoad: true });
        if (data.can_skip && data.status === 'precheck') {
            setVisible(document.getElementById('combat-lobby'), false);
            document.getElementById('precheck-modal-title').textContent = data.encounter?.title || '前置判定';
            document.getElementById('combat-precheck-text').textContent =
                data.precheck_text || '你們有足夠洞察力看穿這是情緒勒索的扭曲模式。';
            setVisible(document.getElementById('combat-precheck-modal'), true);
            return;
        }
        if (window.combatV2?.isEnabled?.()) {
            setVisible(document.getElementById('combat-lobby'), false);
            await window.combatV2.onCombatStarted(data);
            return;
        }
        showToast('請聯繫 GM 開啟 COMBAT_V2', 'error');
    }

    async function confirmPrecheck(choice) {
        const res = await fetch('/combat/start', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                encounter_id: pendingEncounterId,
                confirm: choice,
            }),
        });
        const data = await res.json();
        if (!data.success) {
            showToast(data.error || '操作失敗', 'error');
            return;
        }
        setVisible(document.getElementById('combat-precheck-modal'), false);
        if (data.skipped) {
            showCombatResult({ outcome: 'victory', narrative: data.narrative, reflection_prompt: data.reflection_prompt });
            const statusRes = await fetchNoCache('/status');
            updateDashboard(await statusRes.json());
            return;
        }
        currentCombatId = data.combat_id;
        if (window.combatV2?.isEnabled?.()) {
            setVisible(document.getElementById('combat-lobby'), false);
            await window.combatV2.onCombatStarted(data);
            return;
        }
        showToast('請聯繫 GM 開啟 COMBAT_V2', 'error');
    }

    function showCombatResult(data) {
        setVisible(document.getElementById('combat-near-death-overlay'), false);
        setVisible(document.getElementById('combat-precheck-modal'), false);
        setVisible(document.getElementById('combat-lobby'), false);
        document.getElementById('combat-root-v2')?.classList.add('hidden');
        setVisible(document.getElementById('combat-result-panel'), true);
        const badEnding = data.trauma_bad_ending || data.ending_condition === 'bad_ending';
        const victory = data.outcome === 'victory';
        const titleEl = document.getElementById('combat-result-title');
        if (badEnding) {
            titleEl.textContent = '🌑 陰影結局';
            titleEl.className = 'text-xl font-bold mb-3 text-violet-300';
        } else {
            titleEl.textContent = victory ? '🎉 戰鬥勝利' : '💀 戰鬥失敗';
            titleEl.className = 'text-xl font-bold mb-3';
        }
        const traumaBadge = document.getElementById('combat-result-trauma-badge');
        if (badEnding) {
            const total = data.protagonist_trauma_total ?? data.ending?.protagonist_trauma_total ?? '?';
            traumaBadge.textContent = `主角心理創傷過深（累計 ${total} 次）——即使贏了這一仗，也無法迎來真正的救贖。`;
            setVisible(traumaBadge, true);
        } else {
            setVisible(traumaBadge, false);
        }
        document.getElementById('combat-result-narrative').textContent = data.narrative || '';
        const reflection = badEnding ? null : data.reflection_prompt;
        const reflectionBox = document.getElementById('combat-reflection');
        if (reflection) {
            setVisible(reflectionBox, true);
            document.getElementById('combat-reflection-title').textContent = reflection.title || '界線反思';
            document.getElementById('combat-reflection-theology').textContent = reflection.theological_tie || '';
            document.getElementById('combat-reflection-questions').innerHTML =
                (reflection.questions || []).map((q, i) =>
                    `<li class="pl-3 border-l-2 border-amber-600/50"><span class="text-amber-500/80 text-xs">Q${i + 1}</span><br>${q}</li>`
                ).join('');
        } else {
            setVisible(reflectionBox, false);
        }
    }

    async function rescueNearDeath() {
        const agreed = await showConfirmModal({
            title: '禱告救援',
            message: '為瀕死隊友發起禱告救援？（每次縮短 5 分鐘）',
            confirmLabel: '發起禱告',
        });
        if (!agreed) return;
        const res = await fetch('/combat/rescue_near_death', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ combat_id: currentCombatId, rescue_type: 'prayer' }),
        });
        const data = await res.json();
        if (!data.success) {
            showToast(data.error || '救援失敗', 'error');
            return;
        }
        if (data.rescued) setVisible(document.getElementById('combat-near-death-overlay'), false);
        showToast(data.message || '禱告已送出', 'success');
    }
"""


def remove_legacy_stat_helpers(lines):
    out = []
    skip = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("        function updateCombatPlayerStats(stats) {"):
            skip = True
            i += 1
            continue
        if skip:
            if line.startswith("        function renderCombatTeamRow(data) {"):
                while i < len(lines):
                    if lines[i].strip() == "}" and lines[i].startswith("        }") and not lines[i].startswith("            }"):
                        i += 1
                        break
                    i += 1
                skip = False
                continue
            i += 1
            continue
        out.append(line)
        i += 1
    return out


def main():
    text = INDEX.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    # 1. Replace legacy combat-screen HTML (lines 869–1086, includes duplicate combat_screen include)
    lines[868:1086] = [COMBAT_MODULE_HTML]

    # 2. Remove combat_flow.js script tag (was ~line 1205, shifts after step 1)
    text = "".join(lines)
    text = text.replace('    <script src="/static/js/combat_flow.js"></script>\n', "")

    lines = text.splitlines(keepends=True)

    # 3. Remove legacy combat JS block (let combatPollTimer … rescueNearDeath)
    start_marker = "        let combatPollTimer = null;\n"
    end_marker = "        let currentStory = null;\n"
    start_idx = None
    end_idx = None
    for i, line in enumerate(lines):
        if line == start_marker and start_idx is None:
            start_idx = i
        if line == end_marker and start_idx is not None:
            end_idx = i
            break
    if start_idx is None or end_idx is None:
        raise SystemExit("Could not locate legacy combat JS block markers")
    lines[start_idx:end_idx] = [COMBAT_LOBBY_BRIDGE_JS + "\n"]

    # 4. Remove legacy stat helpers + renderCombatTeamRow
    lines = remove_legacy_stat_helpers(lines)

    # 5. Remove legacy combat modals
    text = "".join(lines)
    modal_start = text.find("    <!-- 單人行動結果 Modal（多人提交後） -->")
    modal_end = text.find("    <!-- 劇情介面 -->")
    if modal_start != -1 and modal_end != -1:
        text = text[:modal_start] + text[modal_end:]

    # 6. Update finishSessionRestore
    old_restore = """                if (data?.current_combat_id) {
                    setTimeout(() => {
                        if (typeof loadCombatPage === 'function') {
                            loadCombatPage(data.current_combat_id);
                        }
                    }, 400);
                }"""
    new_restore = """                if (data?.current_combat_id) {
                    setTimeout(async () => {
                        showSection('combat', { skipCombatLobbyLoad: true });
                        if (window.combatV2?.isEnabled?.()) {
                            const lobby = document.getElementById('combat-lobby');
                            if (lobby) lobby.classList.add('hidden');
                            currentCombatId = data.current_combat_id;
                            await window.combatV2.onCombatStarted({ combat_id: data.current_combat_id });
                        } else if (typeof loadCombatPage === 'function') {
                            await loadCombatPage(data.current_combat_id);
                        }
                    }, 400);
                }"""
    if old_restore in text:
        text = text.replace(old_restore, new_restore)
    else:
        print("WARN: finishSessionRestore block not found")

    INDEX.write_text(text, encoding="utf-8")
    print(f"PR-6 index.html cleanup done ({INDEX})")


if __name__ == "__main__":
    main()