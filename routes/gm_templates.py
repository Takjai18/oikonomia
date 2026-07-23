"""GM dashboard HTML templates (Jinja2 strings)."""

GM_UI_SNIPPET = """
    <div id="gm-toast" class="hidden fixed top-4 left-1/2 -translate-x-1/2 z-[200] px-5 py-3 rounded-2xl text-sm font-medium shadow-lg max-w-sm text-center"></div>
    <div id="gm-input-modal" class="hidden fixed inset-0 bg-black/80 z-[210] items-center justify-center">
        <div class="bg-zinc-900 border border-zinc-700 rounded-3xl p-6 w-full max-w-sm mx-4">
            <div id="gm-input-title" class="text-lg font-semibold mb-3"></div>
            <input id="gm-input-field" type="text" class="w-full bg-zinc-800 border border-zinc-700 rounded-2xl px-4 py-3 mb-4 text-center">
            <div class="flex gap-3">
                <button type="button" id="gm-input-cancel" class="flex-1 py-2.5 bg-zinc-700 hover:bg-zinc-600 rounded-2xl">取消</button>
                <button type="button" id="gm-input-ok" class="flex-1 py-2.5 bg-amber-500 hover:bg-amber-600 text-zinc-950 font-semibold rounded-2xl">確認</button>
            </div>
        </div>
    </div>
    <script>
    function showGmToast(message, type, 'error') {
        const el = document.getElementById('gm-toast');
        if (!el) return;
        const isError = type === 'error';
        el.textContent = message;
        el.className = 'fixed top-4 left-1/2 -translate-x-1/2 z-[200] px-5 py-3 rounded-2xl text-sm font-medium shadow-lg max-w-sm text-center ' +
            (isError ? 'bg-red-900/95 text-red-100 border border-red-700' : 'bg-emerald-900/95 text-emerald-100 border border-emerald-700');
        el.classList.remove('hidden');
        clearTimeout(el._hideTimer);
        el._hideTimer = setTimeout(() => el.classList.add('hidden'), 4000);
    }
    function showGmInputModal({ title, defaultValue = '', placeholder = '' }) {
        return new Promise((resolve) => {
            const overlay = document.getElementById('gm-input-modal');
            const titleEl = document.getElementById('gm-input-title');
            const field = document.getElementById('gm-input-field');
            const cancelBtn = document.getElementById('gm-input-cancel');
            const okBtn = document.getElementById('gm-input-ok');
            if (!overlay || !field) { resolve(null); return; }
            titleEl.textContent = title;
            field.value = defaultValue;
            field.placeholder = placeholder;
            overlay.classList.remove('hidden');
            overlay.classList.add('flex');
            field.focus();
            const cleanup = (value) => {
                overlay.classList.add('hidden');
                overlay.classList.remove('flex');
                resolve(value);
            };
            cancelBtn.onclick = () => cleanup(null);
            okBtn.onclick = () => cleanup(field.value);
            field.onkeydown = (e) => {
                if (e.key === 'Enter') cleanup(field.value);
                if (e.key === 'Escape') cleanup(null);
            };
        });
    }
    </script>
"""

GM_LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>GM Login • Oikonomia</title>
    <script>
      (function() {
        const originalWarn = console.warn;
        console.warn = (...args) => {
          const message = args.join(' ');
          if (message.includes('tailwindcss.com should not be used in production')) return;
          originalWarn.apply(console, args);
        };
      })();
    </script>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
      setTimeout(() => {
        const style = document.createElement('style');
        style.innerHTML = `
      body::before { display: none !important; }
    `;
        document.head.appendChild(style);

        const originalWarn = console.warn;
        console.warn = (...args) => {
          const message = args.join(' ');
          if (message.includes('tailwindcss.com should not be used in production')) {
            return;
          }
          originalWarn.apply(console, args);
        };
      }, 100);
    </script>
</head>
<body class="bg-zinc-950 text-white flex items-center justify-center min-h-screen">
""" + GM_UI_SNIPPET + """
    <div class="w-full max-w-sm">
        <div class="text-center mb-8">
            <h1 class="text-3xl font-bold">GM 後台</h1>
            <p class="text-zinc-400 mt-2">請輸入管理員 PIN</p>
        </div>
        
        <form id="gm-login-form" class="space-y-4">
            <input type="password" id="pin" placeholder="輸入 GM PIN" 
                   class="w-full bg-zinc-900 border border-zinc-700 focus:border-amber-500 rounded-2xl px-6 py-4 text-xl text-center">
            <button type="submit" 
                    class="w-full bg-amber-500 hover:bg-amber-600 text-zinc-950 font-semibold py-4 rounded-2xl">
                登入 GM 後台
            </button>
        </form>
    </div>

    <script>
        document.getElementById('gm-login-form').addEventListener('submit', async function(e) {
            e.preventDefault();
            const pin = document.getElementById('pin').value;
            
            const res = await fetch('/gm/login', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: new URLSearchParams({pin: pin})
            });
            
            const data = await res.json();
            if (data.success) {
                window.location.href = '/gm/dashboard';
            } else {
                showGmToast(data.error || '登入失敗', 'error', 'error');
            }
        });
    </script>
</body>
</html>
"""

GM_DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>GM Dashboard • Oikonomia</title>
    <script>
      (function() {
        const originalWarn = console.warn;
        console.warn = (...args) => {
          const message = args.join(' ');
          if (message.includes('tailwindcss.com should not be used in production')) return;
          originalWarn.apply(console, args);
        };
      })();
    </script>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
      setTimeout(() => {
        const style = document.createElement('style');
        style.innerHTML = `
      body::before { display: none !important; }
    `;
        document.head.appendChild(style);

        const originalWarn = console.warn;
        console.warn = (...args) => {
          const message = args.join(' ');
          if (message.includes('tailwindcss.com should not be used in production')) {
            return;
          }
          originalWarn.apply(console, args);
        };
      }, 100);
    </script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <style>
        .hidden { display: none !important; }
        .gm-tab { background: #27272a; color: #a1a1aa; }
        .gm-tab.active { background: #f59e0b; color: #09090b; }
        .route-card {
            border: 3px solid #2C3E50;
            border-radius: 12px;
            cursor: pointer;
            transition: transform 0.1s ease, box-shadow 0.1s ease;
            box-shadow: 4px 4px 0px rgba(44, 62, 80, 0.5);
        }
        .route-card:hover { transform: translate(-2px, -2px); box-shadow: 6px 6px 0px rgba(44, 62, 80, 0.5); }
        .route-iggy { background: linear-gradient(135deg, #7f1d1d 0%, #991b1b 100%); }
        .route-marah { background: linear-gradient(135deg, #1e3a5f 0%, #1e40af 100%); }
    </style>
</head>
<body class="bg-zinc-950 text-white p-8">
""" + GM_UI_SNIPPET + """
    <div class="max-w-6xl mx-auto">
        <div class="flex justify-between items-center mb-8">
            <div>
                <h1 class="text-3xl font-bold">GM Dashboard</h1>
                <p class="text-zinc-400 text-sm mt-1">即時監控所有玩家狀態</p>
            </div>
            <div class="flex items-center gap-x-3">
                <div class="text-xs px-3 py-1.5 bg-zinc-800 rounded-2xl text-zinc-400 flex items-center gap-x-2">
                    <i class="fa-solid fa-sync"></i>
                    <span>手動刷新</span>
                </div>
                <button onclick="location.reload()" 
                        class="px-5 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-2xl text-sm flex items-center gap-x-2">
                    <i class="fa-solid fa-redo"></i>
                    <span>手動刷新</span>
                </button>
                <a href="/" class="px-5 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-2xl text-sm">返回玩家端</a>
            </div>
        </div>

        <!-- Tab 切換 -->
        <div class="flex gap-x-2 mb-6 px-1">
            <button onclick="switchGMTab('squads')" id="tab-squads"
                    class="gm-tab active px-6 py-2 rounded-2xl text-sm font-medium">玩家狀態</button>
            <button onclick="switchGMTab('teams')" id="tab-teams"
                    class="gm-tab px-6 py-2 rounded-2xl text-sm font-medium">Team 管理</button>
            <button onclick="switchGMTab('overview')" id="tab-overview"
                    class="gm-tab px-6 py-2 rounded-2xl text-sm font-medium">進度總覽</button>
            <button onclick="switchGMTab('combat')" id="tab-combat"
                    class="gm-tab px-6 py-2 rounded-2xl text-sm font-medium">戰鬥監控</button>
        </div>

        <div id="gm-squads-tab">
        <div class="bg-zinc-900 rounded-3xl p-6">
            <div class="flex justify-between items-center mb-4">
                <h2 class="text-xl font-semibold">所有玩家即時狀態</h2>
                <div class="text-xs text-zinc-500">最後更新：{{ last_update }}</div>
            </div>
            
            <table class="w-full">
                <thead>
                    <tr class="border-b border-zinc-700 text-left text-sm text-zinc-400">
                        <th class="py-3 pl-2 w-12"></th>
                        <th class="py-3">玩家名稱</th>
                        <th class="py-3">路線</th>
                        <th class="py-3">生命值</th>
                        <th class="py-3">神智</th>
                        <th class="py-3">力量/韌性</th>
                        <th class="py-3">提交次數</th>
                        <th class="py-3">操作</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-zinc-800">
                    {% for squad in squads %}
                    <tr class="hover:bg-zinc-800/60">
                        <td class="py-4 pl-2">
                            <img src="/static/avatars/{{ squad.avatar or 'default.png' }}"
                                 class="w-10 h-10 rounded-full object-cover border border-zinc-600">
                        </td>
                        <td class="py-4 font-mono font-semibold text-amber-400">
                            <a href="/gm/squad/{{ squad.squad_id }}" class="hover:underline">
                                {{ squad.display_name or squad.squad_id }}
                            </a>
                        </td>
                        <td class="py-4 text-sm">{{ squad.route_label }}</td>
                        <td class="py-4">
                            <div class="flex items-center gap-x-3">
                                <span class="font-mono w-8">{{ squad.hp }}</span>
                                <div class="w-28 h-2 bg-zinc-700 rounded-full">
                                    <div class="h-2 bg-red-500 rounded-full" style="width: {{ squad.hp }}%"></div>
                                </div>
                            </div>
                        </td>
                        <td class="py-4">
                            <div class="flex items-center gap-x-3">
                                <span class="font-mono w-8">{{ squad.sanity }}</span>
                                <div class="w-28 h-2 bg-zinc-700 rounded-full">
                                    <div class="h-2 bg-amber-500 rounded-full" style="width: {{ squad.sanity }}%"></div>
                                </div>
                            </div>
                        </td>
                        <td class="py-4 font-mono text-xs">{{ squad.power }}/{{ squad.resilience }}</td>
                        <td class="py-4">
                            <span class="px-3 py-1 bg-zinc-700 rounded-full text-xs">{{ squad.submission_count }} 次</span>
                            
                        </td>
                        <td class="py-4">
                            {% if squad.submission_count > 0 %}
                            <button onclick="viewPlayerLogs('{{ squad.squad_id }}')"
                                    class="px-3 py-1 text-xs bg-zinc-700 hover:bg-zinc-600 rounded-full mr-2">
                                任務 Log
                            </button>
                            <a href="/gm/squad/{{ squad.squad_id }}" 
                               class="px-3 py-1 text-xs bg-amber-500 hover:bg-amber-600 text-zinc-950 rounded-full">
                                詳情
                            </a>
                            {% else %}
                            <span class="text-xs text-zinc-500">—</span>
                            {% endif %}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <!-- Global Event -->
        <div class="bg-zinc-900 rounded-3xl p-6 mt-6">
            <h2 class="text-xl font-semibold mb-4">觸發 Global Event</h2>
            
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                
                <!-- 全營神智調整 -->
                <div class="bg-zinc-800 rounded-2xl p-5">
                    <div class="font-medium mb-3">全營神智調整</div>
                    <div class="flex gap-x-2">
                        <input type="number" id="sanity-value" value="-5" 
                               class="flex-1 bg-zinc-900 border border-zinc-700 rounded-2xl px-4 py-2 text-sm">
                        <button onclick="triggerGlobalEvent('adjust_sanity')" 
                                class="px-6 py-2 bg-amber-600 hover:bg-amber-700 rounded-2xl text-sm">
                            執行
                        </button>
                    </div>
                    <div class="text-xs text-zinc-400 mt-2">正數 = 增加，負數 = 減少</div>
                </div>

                <!-- 劇情事件 -->
                <div class="bg-zinc-800 rounded-2xl p-5">
                    <div class="font-medium mb-3">劇情事件</div>
                    <div class="flex flex-wrap gap-2">
                        <button onclick="triggerGlobalEvent('judas_strengthen')" 
                                class="px-4 py-2 bg-red-600 hover:bg-red-700 rounded-2xl text-sm">
                            Judas 加強
                        </button>
                        <button onclick="triggerGlobalEvent('iggy_collapse')" 
                                class="px-4 py-2 bg-red-600 hover:bg-red-700 rounded-2xl text-sm">
                            Iggy 崩潰
                        </button>
                    </div>
                </div>

                <!-- 自訂全球事件 -->
                <div class="bg-zinc-800 rounded-2xl p-5 md:col-span-2">
                    <div class="font-medium mb-3">自訂全球事件</div>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
                        <input type="text" id="custom-event-title" placeholder="事件標題（例如：裂縫擴大）"
                               class="bg-zinc-900 border border-zinc-700 rounded-2xl px-4 py-2 text-sm">
                        <select id="custom-event-effect-type"
                                class="bg-zinc-900 border border-zinc-700 rounded-2xl px-4 py-2 text-sm">
                            <option value="">只記錄，不套用效果</option>
                            <option value="sanity_down">全營神智下降</option>
                            <option value="sanity_up">全營神智上升</option>
                            <option value="power_up">全營力量上升</option>

                            <option value="resilience_up">全營韌性上升</option>
                            <option value="global_debuff">全球減益（只記錄）</option>
                        </select>
                    </div>
                    <textarea id="custom-event-description" rows="2" placeholder="事件描述（可選）"
                              class="w-full bg-zinc-900 border border-zinc-700 rounded-2xl px-4 py-2 text-sm mb-3"></textarea>
                    <div class="flex gap-x-3 items-center">
                        <input type="number" id="custom-event-effect-value" value="5" placeholder="效果數值"
                               class="w-32 bg-zinc-900 border border-zinc-700 rounded-2xl px-4 py-2 text-sm">
                        <button onclick="createCustomGlobalEvent()"
                                class="px-6 py-2 bg-emerald-600 hover:bg-emerald-700 rounded-2xl text-sm">
                            建立全球事件
                        </button>
                    </div>
                    <div class="text-xs text-zinc-400 mt-2">事件會顯示喺玩家日誌頁最底部嘅「全球事件記錄」</div>
                </div>

            </div>
        </div>

        <!-- Global Announcement -->
        <div class="bg-zinc-900 rounded-3xl p-6 mt-6">
            <h2 class="text-xl font-semibold mb-4">發送 Global Announcement</h2>
            
            <div class="flex gap-x-3">
                <input type="text" id="announcement-input" placeholder="輸入要發送嘅訊息..." 
                       class="flex-1 bg-zinc-800 border border-zinc-700 rounded-2xl px-5 py-3">
                <button onclick="sendAnnouncement()" 
                        class="px-8 py-3 bg-blue-600 hover:bg-blue-700 rounded-2xl font-medium">
                    發送
                </button>
            </div>
        </div>

        <!-- Global Events Audit Log -->
        <div class="bg-zinc-900 border border-zinc-700 rounded-3xl p-6 mt-6">
            <div class="flex items-center justify-between mb-4 gap-2 flex-wrap">
                <h3 class="font-bold text-lg flex items-center gap-x-2 text-red-400">
                    <i class="fa-solid fa-history"></i>
                    <span>🌍 全球事件與工作人員操作日誌</span>
                </h3>
                <div class="flex items-center gap-2">
                    <button type="button" onclick="clearGmAlertEvents()"
                            class="text-xs px-3 py-1.5 bg-amber-900/40 hover:bg-amber-800/50 border border-amber-700/50 text-amber-200 rounded-xl transition-colors"
                            title="清除所有戰場救援訊號（不影響正式公告）">
                        清除救援訊號
                    </button>
                    <button type="button" onclick="refreshGmGlobalEventsLog()"
                            class="text-xs px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 border border-zinc-600 rounded-xl transition-colors">
                        🔄 刷新日誌
                    </button>
                </div>
            </div>
            <p class="text-[11px] text-zinc-500 mb-3">
                戰場「請求 GM 介入」只顯示喺此日誌（玩家通告／全球事件記錄睇唔到）。
                可逐則「消除」，或一次清走全部救援訊號。
            </p>
            <div id="gm-global-events-container" class="space-y-2.5 max-h-[350px] overflow-y-auto pr-1">
                <div class="text-zinc-500 text-sm py-4 text-center">點擊刷新載入事件日誌...</div>
            </div>
        </div>

        <!-- Danger Zone -->
        <div class="mt-8 border border-red-500/30 rounded-3xl p-6">
            <div class="flex items-center gap-x-2 mb-4">
                <i class="fa-solid fa-exclamation-triangle text-red-400"></i>
                <h2 class="text-lg font-semibold text-red-400">Danger Zone</h2>
            </div>
            
            <div class="flex items-center justify-between mb-4 pb-4 border-b border-red-500/20">
                <div>
                    <div class="font-medium">清空所有玩家上傳圖片</div>
                    <div class="text-xs text-zinc-400">刪除 uploads 資料夾內嘅圖片檔案，並清空提交記錄中的圖片欄位（可減少 Storage）</div>
                </div>
                <button onclick="showClearImagesModal()"
                        class="px-6 py-2 bg-red-600 hover:bg-red-700 rounded-2xl text-sm font-medium">
                    清空圖片
                </button>
            </div>

            <div class="flex items-center justify-between">
                <div>
                    <div class="font-medium">重置整個遊戲</div>
                    <div class="text-xs text-zinc-400">會刪除所有玩家ID（FRAG-XX）、Team 同提交記錄，一切由零開始</div>
                </div>
                <button onclick="showResetModal()" 
                        class="px-6 py-2 bg-red-600 hover:bg-red-700 rounded-2xl text-sm font-medium">
                    重置遊戲
                </button>
            </div>
        </div>
        </div>

        <div id="gm-teams-tab" class="hidden">
        <!-- Team 管理 (加強版) -->
        <div class="bg-zinc-900 rounded-3xl p-6">
            <div class="flex items-center justify-between mb-4">
                <h2 class="text-xl font-semibold">Team 管理</h2>
                <button onclick="loadGMTeams()" 
                        class="px-4 py-1.5 bg-zinc-700 hover:bg-zinc-600 rounded-2xl text-sm flex items-center gap-x-2">
                    <i class="fa-solid fa-sync"></i>
                    <span>刷新</span>
                </button>
            </div>

            <!-- 建立新 Team -->
            <div class="bg-zinc-800 rounded-2xl p-5 mb-4">
                <div class="font-medium mb-3">建立新 Team</div>
                <div class="flex gap-x-3">
                    <input type="text" id="new-team-name" placeholder="輸入隊名（例如：界線守護者）" 
                           class="flex-1 bg-zinc-900 border border-zinc-700 rounded-2xl px-4 py-2 text-sm">
                    <button onclick="gmCreateTeam()" 
                            class="px-6 py-2 bg-emerald-600 hover:bg-emerald-700 rounded-2xl text-sm font-medium">
                        建立新隊
                    </button>
                </div>
            </div>

            <!-- Teams 列表 -->
            <div id="gm-teams-list" class="space-y-4"></div>
        </div>
        </div>

        <div id="gm-overview-tab" class="hidden">
        <div class="bg-zinc-900 rounded-3xl p-6">
            <div class="flex items-center justify-between mb-4">
                <h2 class="text-xl font-semibold">隊伍 / 玩家進度總覽</h2>
                <button onclick="loadTeamsOverview()"
                        class="px-4 py-1.5 bg-zinc-700 hover:bg-zinc-600 rounded-2xl text-sm flex items-center gap-x-2">
                    <i class="fa-solid fa-sync"></i>
                    <span>刷新</span>
                </button>
            </div>
            <div id="gm-overview-content" class="text-zinc-400 text-center py-8">載入中...</div>
        </div>
        </div>

        <div id="gm-combat-tab" class="hidden">
        <div class="bg-zinc-900 rounded-3xl p-6 mb-4">
            <div class="flex flex-wrap items-center justify-between gap-4">
                <div>
                    <h2 class="text-xl font-semibold">戰鬥系統 V2</h2>
                    <p id="combat-v2-status-text" class="text-sm text-zinc-400 mt-1">載入中…</p>
                </div>
                <button type="button" id="combat-v2-toggle-btn"
                        onclick="toggleCombatV2()"
                        class="px-5 py-2.5 rounded-2xl text-sm font-semibold bg-amber-500 hover:bg-amber-600 text-zinc-950">
                    切換狀態
                </button>
            </div>
        </div>
        <div class="bg-zinc-900 rounded-3xl p-6">
            <div class="flex items-center justify-between mb-4">
                <h2 class="text-xl font-semibold">進行中戰鬥</h2>
                <button onclick="loadActiveCombats()"
                        class="px-4 py-1.5 bg-zinc-700 hover:bg-zinc-600 rounded-2xl text-sm flex items-center gap-x-2">
                    <i class="fa-solid fa-sync"></i>
                    <span>刷新</span>
                </button>
            </div>
            <div id="gm-combat-content" class="text-zinc-400 text-center py-8">載入中...</div>
        </div>

        <div class="bg-zinc-900 border border-emerald-900/50 rounded-3xl p-6 mt-4">
            <div class="flex items-center justify-between gap-2 mb-1">
                <h2 class="text-lg font-semibold text-emerald-300">開通模式（Debug）</h2>
                <button type="button" onclick="loadGmUnlockMode()"
                        class="text-xs px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 border border-zinc-600 rounded-xl">
                    🔄 重新載入
                </button>
            </div>
            <p class="text-xs text-zinc-500 mb-4 leading-relaxed">
                選一位玩家開啟後，該玩家<strong>無視劇情／任務前置</strong>，探索可看見全部主線任務，遭遇列表可打全部戰鬥（含已完成劇情戰）。
                正式營會請關閉。玩家需<strong>重新整理</strong>探索／遭遇頁才會生效。
            </p>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                    <label class="text-[11px] text-zinc-500 block mb-1">玩家</label>
                    <select id="gm-unlock-squad"
                            class="w-full bg-zinc-800 border border-zinc-700 rounded-2xl px-4 py-2.5 text-sm font-mono">
                        <option value="">載入中…</option>
                    </select>
                </div>
                <div class="flex flex-col justify-end gap-2">
                    <button type="button" onclick="gmSetUnlockMode(true)"
                            class="w-full px-4 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-zinc-950 font-semibold rounded-2xl text-sm">
                        開啟開通模式
                    </button>
                    <button type="button" onclick="gmSetUnlockMode(false)"
                            class="w-full px-4 py-2.5 bg-zinc-700 hover:bg-zinc-600 rounded-2xl text-sm">
                        關閉開通模式
                    </button>
                </div>
            </div>
            <div id="gm-unlock-hint" class="text-[11px] text-zinc-500 mt-3 min-h-[1.25rem]"></div>
        </div>

        <div class="bg-zinc-900 border border-amber-900/40 rounded-3xl p-6 mt-4">
            <div class="flex items-center justify-between gap-2 mb-1">
                <h2 class="text-lg font-semibold text-amber-300">重置遭遇（測試用）</h2>
                <button type="button" onclick="loadGmResetEncounterOptions()"
                        class="text-xs px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 border border-zinc-600 rounded-xl">
                    🔄 重新載入名單
                </button>
            </div>
            <p class="text-xs text-zinc-500 mb-4 leading-relaxed">
                布布等 <strong>不可重打</strong> 劇情戰打完後會鎖住。由下拉<strong>選擇隊伍</strong>同<strong>遭遇</strong>重置即可再測。
                預設會清木材 QR／背包／任務（否則掃 QR 會因為「已擁有物品」而開唔到戰）。
            </p>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                    <label class="text-[11px] text-zinc-500 block mb-1">隊伍</label>
                    <select id="gm-reset-enc-team"
                            class="w-full bg-zinc-800 border border-zinc-700 rounded-2xl px-4 py-2.5 text-sm font-mono">
                        <option value="">載入中…</option>
                    </select>
                </div>
                <div>
                    <label class="text-[11px] text-zinc-500 block mb-1">遭遇</label>
                    <select id="gm-reset-enc-id"
                            class="w-full bg-zinc-800 border border-zinc-700 rounded-2xl px-4 py-2.5 text-sm">
                        <option value="enc_iggy_act1_bubo">Act 1 布布（enc_iggy_act1_bubo）</option>
                    </select>
                </div>
            </div>
            <div id="gm-reset-enc-hint" class="text-[11px] text-zinc-500 mt-2 min-h-[1.25rem]"></div>
            <label class="flex items-center gap-2 mt-3 text-sm text-zinc-300 cursor-pointer select-none">
                <input type="checkbox" id="gm-reset-enc-clear-qr" class="rounded border-zinc-600" checked>
                連同清除木材 QR／背包木材／act1_wood 任務（布布重測必勾）
            </label>
            <button type="button" onclick="gmResetEncounter()"
                    class="mt-4 w-full sm:w-auto px-6 py-2.5 bg-amber-600 hover:bg-amber-500 text-zinc-950 font-semibold rounded-2xl text-sm">
                重置所選遭遇
            </button>
        </div>
        </div>

        <script>
        function gmEscapeHtml(s) {
            return String(s ?? '')
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;');
        }

        let gmResetOptionsCache = null;
        let gmUnlockPlayersCache = null;

        async function loadGmUnlockMode() {
            const sel = document.getElementById('gm-unlock-squad');
            const hint = document.getElementById('gm-unlock-hint');
            if (!sel) return;
            sel.innerHTML = '<option value="">載入中…</option>';
            try {
                const res = await fetch('/gm/api/unlock_mode', { credentials: 'same-origin' });
                const data = await res.json();
                if (!data.success) {
                    sel.innerHTML = '<option value="">載入失敗</option>';
                    showGmToast(data.error || '載入失敗', 'error');
                    return;
                }
                gmUnlockPlayersCache = data.players || [];
                sel.innerHTML = gmUnlockPlayersCache.length
                    ? gmUnlockPlayersCache.map((p) => {
                        const mark = p.unlock_mode ? ' 🔓開通中' : '';
                        const label = (p.display_name || p.squad_id) + mark;
                        return `<option value="${gmEscapeHtml(p.squad_id)}">${gmEscapeHtml(label)}</option>`;
                    }).join('')
                    : '<option value="">（未有玩家）</option>';
                const on = (data.unlocked_squad_ids || []).length;
                if (hint) {
                    hint.textContent = on
                        ? `目前 ${on} 人開通中：${(data.unlocked_squad_ids || []).join('、')}`
                        : '目前無人開啟開通模式';
                }
            } catch (e) {
                sel.innerHTML = '<option value="">網路錯誤</option>';
            }
        }

        async function gmSetUnlockMode(enabled) {
            const squadId = (document.getElementById('gm-unlock-squad')?.value || '').trim();
            if (!squadId) {
                showGmToast('請選擇玩家', 'error');
                return;
            }
            try {
                const res = await fetch('/gm/api/unlock_mode', {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ squad_id: squadId, enabled: !!enabled }),
                });
                const data = await res.json();
                if (data.success) {
                    showGmToast(data.message || '已更新', 'success');
                    loadGmUnlockMode();
                } else {
                    showGmToast(data.error || '失敗', 'error');
                }
            } catch (e) {
                showGmToast('網路錯誤', 'error');
            }
        }

        async function loadGmResetEncounterOptions() {
            const teamSel = document.getElementById('gm-reset-enc-team');
            const encSel = document.getElementById('gm-reset-enc-id');
            const hint = document.getElementById('gm-reset-enc-hint');
            if (!teamSel || !encSel) return;
            teamSel.innerHTML = '<option value="">載入中…</option>';
            try {
                const res = await fetch('/gm/api/reset_encounter_options', { credentials: 'same-origin' });
                const data = await res.json();
                if (!data.success) {
                    teamSel.innerHTML = '<option value="">載入失敗</option>';
                    showGmToast(data.error || '載入名單失敗', 'error');
                    return;
                }
                gmResetOptionsCache = data;
                const teams = data.teams || [];
                teamSel.innerHTML = teams.length
                    ? teams.map((t) => {
                        const done = (data.completions_by_team || {})[t.team_id] || [];
                        const bubo = done.some((c) => c.encounter_id === 'enc_iggy_act1_bubo');
                        const mark = bubo ? ' ✓布布已完成' : '';
                        return `<option value="${gmEscapeHtml(t.team_id)}">${gmEscapeHtml(t.label)}${mark}</option>`;
                    }).join('')
                    : '<option value="">（未有隊伍）</option>';

                const encs = data.encounters || [];
                const preferred = (data.defaults && data.defaults.encounter_id) || 'enc_iggy_act1_bubo';
                encSel.innerHTML = encs.map((e) => {
                    const lock = e.replayable ? '' : ' [不可重打]';
                    return `<option value="${gmEscapeHtml(e.encounter_id)}" ${e.encounter_id === preferred ? 'selected' : ''}>${gmEscapeHtml(e.label)}${lock}</option>`;
                }).join('');

                if (hint) {
                    hint.textContent = teams.length
                        ? `共 ${teams.length} 隊 · 選隊後可看右側遭遇並重置`
                        : '未有隊伍';
                }
                teamSel.onchange = () => updateGmResetEncHint();
                updateGmResetEncHint();
            } catch (e) {
                teamSel.innerHTML = '<option value="">網路錯誤</option>';
            }
        }

        function updateGmResetEncHint() {
            const hint = document.getElementById('gm-reset-enc-hint');
            if (!hint || !gmResetOptionsCache) return;
            const teamId = document.getElementById('gm-reset-enc-team')?.value;
            const done = (gmResetOptionsCache.completions_by_team || {})[teamId] || [];
            if (!teamId) {
                hint.textContent = '';
                return;
            }
            if (!done.length) {
                hint.textContent = `${teamId}：目前冇遭遇完成記錄（可直接重測）`;
                return;
            }
            const names = done.slice(0, 5).map((c) => c.encounter_id).join('、');
            hint.textContent = `${teamId} 已完成：${names}${done.length > 5 ? '…' : ''}`;
        }

        async function gmResetEncounter() {
            const teamId = (document.getElementById('gm-reset-enc-team')?.value || '').trim();
            const encounterId = (document.getElementById('gm-reset-enc-id')?.value || '').trim();
            const clearQr = !!document.getElementById('gm-reset-enc-clear-qr')?.checked;
            if (!teamId || !encounterId) {
                showGmToast('請選擇隊伍同遭遇', 'error');
                return;
            }
            if (!confirm(`確定重置 ${teamId} 的 ${encounterId}？\\n（會結束該隊相關戰鬥並清完成記錄）`)) return;
            try {
                const res = await fetch('/gm/api/reset_encounter', {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        team_id: teamId,
                        encounter_id: encounterId,
                        clear_qr: clearQr,
                    }),
                });
                const data = await res.json();
                if (data.success) {
                    showGmToast(data.message || '已重置', 'success');
                    loadGmResetEncounterOptions();
                } else {
                    showGmToast(data.error || data.message || '重置失敗', 'error');
                }
            } catch (e) {
                showGmToast('網路錯誤', 'error');
            }
        }

        async function refreshGmGlobalEventsLog() {
            const container = document.getElementById('gm-global-events-container');
            if (!container) return;
            container.innerHTML = '<div class="text-zinc-500 text-sm py-4 text-center">載入中...</div>';

            try {
                const res = await fetch('/gm/api/global_events_log', { credentials: 'same-origin' });
                const data = await res.json();
                if (!data.success) {
                    container.innerHTML = `<div class="text-red-400 text-sm py-4 text-center">載入失敗: ${gmEscapeHtml(data.error || '未知錯誤')}</div>`;
                    return;
                }
                if (!data.events || data.events.length === 0) {
                    container.innerHTML = '<div class="text-zinc-500 text-sm py-4 text-center">暫無任何全球事件記錄</div>';
                    return;
                }

                container.innerHTML = data.events.map((ev) => {
                    const isAlert = ev.effect_type === 'gm_alert'
                        || (ev.title || '').includes('救援訊號')
                        || (ev.description || '').includes('請求 GM 介入');
                    const badgeColor = isAlert
                        ? 'bg-red-900/40 text-red-300'
                        : (ev.effect_type === 'announcement'
                            ? 'bg-blue-900/40 text-blue-300'
                            : 'bg-amber-900/40 text-amber-400');
                    const title = gmEscapeHtml(ev.title);
                    const desc = ev.description ? `<p class="text-zinc-400 mt-1 leading-relaxed">${gmEscapeHtml(ev.description)}</p>` : '';
                    const effectType = gmEscapeHtml(ev.effect_type || '指令');
                    const createdBy = gmEscapeHtml(ev.created_by || '系統');
                    const ts = gmEscapeHtml(ev.timestamp);
                    const effectValue = ev.effect_value ?? 0;
                    const eid = Number(ev.id) || 0;
                    return `
                        <div class="text-xs bg-zinc-950/60 border border-zinc-800 rounded-xl p-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                            <div class="min-w-0 flex-1">
                                <div class="flex items-center gap-x-2 flex-wrap gap-y-1">
                                    <span class="font-bold text-zinc-200 text-sm">${title}</span>
                                    <span class="px-1.5 py-0.5 rounded text-[10px] ${badgeColor}">${effectType}</span>
                                    ${isAlert ? '<span class="px-1.5 py-0.5 rounded text-[10px] bg-zinc-800 text-zinc-400">僅 GM</span>' : ''}
                                </div>
                                ${desc}
                                <div class="text-[10px] text-zinc-500 mt-1">執行者: <span class="font-mono text-zinc-400">${createdBy}</span> | 數值: ${effectValue}</div>
                            </div>
                            <div class="flex flex-col items-end gap-1.5 shrink-0">
                                <div class="text-[10px] text-zinc-500 font-mono text-right">${ts}</div>
                                <button type="button" onclick="dismissGmGlobalEvent(${eid})"
                                        class="text-[10px] px-2 py-1 rounded-lg border border-zinc-700 bg-zinc-900 hover:bg-red-950/50 hover:border-red-800 text-zinc-300 hover:text-red-200 transition-colors">
                                    消除
                                </button>
                            </div>
                        </div>
                    `;
                }).join('');
            } catch (err) {
                container.innerHTML = '<div class="text-red-400 text-sm py-4 text-center">網路連線超時，請重試</div>';
            }
        }

        async function dismissGmGlobalEvent(eventId) {
            if (!eventId) return;
            if (!confirm('確定消除此事件／通告？')) return;
            try {
                const res = await fetch('/gm/api/global_events/' + eventId, {
                    method: 'DELETE',
                    credentials: 'same-origin',
                });
                const data = await res.json();
                if (data.success) {
                    showGmToast(data.message || '已消除', 'success');
                    refreshGmGlobalEventsLog();
                } else {
                    showGmToast(data.error || '消除失敗', 'error');
                }
            } catch (err) {
                showGmToast('網路錯誤，消除失敗', 'error');
            }
        }

        async function clearGmAlertEvents() {
            if (!confirm('清除全部「戰場救援訊號」？（正式 GM 公告會保留）')) return;
            try {
                const res = await fetch('/gm/api/global_events/clear_gm_alerts', {
                    method: 'POST',
                    credentials: 'same-origin',
                });
                const data = await res.json();
                if (data.success) {
                    showGmToast(data.message || '已清除救援訊號', 'success');
                    refreshGmGlobalEventsLog();
                } else {
                    showGmToast(data.error || '清除失敗', 'error');
                }
            } catch (err) {
                showGmToast('網路錯誤，清除失敗', 'error');
            }
        }

        function sendAnnouncement() {
            const message = document.getElementById('announcement-input').value.trim();
            if (!message) {
                showGmToast('請輸入訊息', 'error');
                return;
            }

            fetch('/gm/announcement', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: new URLSearchParams({message: message})
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    showGmToast('公告已發送', 'success');
                    document.getElementById('announcement-input').value = '';
                    refreshGmGlobalEventsLog();
                }
            });
        }

        document.addEventListener('DOMContentLoaded', () => {
            setTimeout(refreshGmGlobalEventsLog, 500);
        });
        </script>

        <script>
        function triggerGlobalEvent(eventType) {
            let value = 0;
            if (eventType === 'adjust_sanity') {
                value = parseInt(document.getElementById('sanity-value').value) || 0;
            }

            fetch('/gm/global_event', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: new URLSearchParams({
                    event_type: eventType,
                    value: value
                })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    showGmToast(data.message || '事件已觸發', 'success');
                    refreshGmGlobalEventsLog();
                } else {
                    showGmToast('觸發失敗', 'error');
                }
            });
        }

        async function createCustomGlobalEvent() {
            const title = document.getElementById('custom-event-title').value.trim();
            const description = document.getElementById('custom-event-description').value.trim();
            const effect_type = document.getElementById('custom-event-effect-type').value;
            const effect_value = parseInt(document.getElementById('custom-event-effect-value').value) || 0;

            if (!title) {
                showGmToast('請輸入事件標題', 'error');
                return;
            }

            const res = await fetch('/gm/create_global_event', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ title, description, effect_type: effect_type || null, effect_value })
            });
            const data = await res.json();

            if (data.success) {
                showGmToast(data.message || '全球事件已建立', 'success');
                document.getElementById('custom-event-title').value = '';
                document.getElementById('custom-event-description').value = '';
                document.getElementById('custom-event-effect-type').value = '';
                document.getElementById('custom-event-effect-value').value = '5';
                refreshGmGlobalEventsLog();
            } else {
                showGmToast(data.error || '建立失敗', 'error');
            }
        }

        // ==================== GM Team 管理加強版 ====================
        async function loadGMTeams() {
            const container = document.getElementById('gm-teams-list');
            container.innerHTML = '<div class="text-zinc-400 text-center py-4">載入中...</div>';
            
            const res = await fetch('/gm/teams');
            const data = await res.json();
            
            if (!data.teams || data.teams.length === 0) {
                container.innerHTML = '<div class="text-zinc-400 text-center py-8">尚未有任何 Team</div>';
                return;
            }
            
            container.innerHTML = '';
            
            // 統一排序（同玩家一樣）
            data.teams.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''));
            
            for (const team of data.teams) {
                const div = document.createElement('div');
                div.className = 'bg-zinc-800 rounded-2xl p-5 border border-zinc-700';
                const safeName = (team.team_name || '').replace(/'/g, "\\'");
                
                div.innerHTML = `
                    <div class="flex justify-between items-start mb-3">
                        <div>
                            <div class="font-mono font-bold text-emerald-400">${team.team_id}</div>
                            <div class="text-lg font-semibold flex items-center gap-x-2">
                                ${team.team_name}
                                <button onclick="gmEditTeamName('${team.team_id}', '${safeName}')" 
                                        class="text-xs px-2 py-0.5 bg-zinc-700 hover:bg-zinc-600 rounded">改名</button>
                            </div>
                            <div class="text-xs text-zinc-400 mt-0.5">${team.member_count} 位成員</div>
                        </div>
                        <div>
                            <div class="text-xs px-3 py-1 rounded-full text-center ${team.route === 'iggy' ? 'bg-red-900/60 text-red-400' : team.route === 'marah' ? 'bg-blue-900/60 text-blue-400' : 'bg-zinc-700 text-zinc-400'}">
                                ${team.route === 'iggy' ? '🔥 Iggy 線' : team.route === 'marah' ? '🌊 Marah 線' : '未設定路線'}
                            </div>
                        </div>
                    </div>
                    
                    <div class="flex flex-wrap gap-2 mb-3">
                        <button onclick="gmAssignSquadToTeam('${team.team_id}')" 
                                class="px-3 py-1.5 text-xs bg-amber-600 hover:bg-amber-700 rounded-xl flex items-center gap-x-1">
                            <i class="fa-solid fa-exchange-alt"></i>
                            <span>轉隊 / 分配</span>
                        </button>
                        <button onclick="gmSetRoutePrompt('${team.team_id}')" 
                                class="px-3 py-1.5 text-xs bg-purple-600 hover:bg-purple-700 rounded-xl">設定路線</button>
                        <button onclick="gmViewTeamMembers('${team.team_id}', '${safeName}')" 
                                class="px-3 py-1.5 text-xs bg-zinc-700 hover:bg-zinc-600 rounded-xl">查看成員</button>
                    </div>
                `;
                container.appendChild(div);
            }
        }

        async function gmCreateTeam() {
            const name = document.getElementById('new-team-name').value.trim() || '新小隊';
            const res = await fetch('/gm/create_team', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: new URLSearchParams({team_name: name})
            });
            const data = await res.json();
            if (data.success) {
                showGmToast(`Team ${data.team_id} 已建立`, 'success');
                document.getElementById('new-team-name').value = '';
                loadGMTeams();
            }
        }

        function gmEditTeamName(teamId, currentName) {
            const safeVal = (currentName || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
            const modal = document.createElement('div');
            modal.className = 'fixed inset-0 bg-black/80 flex items-center justify-center z-[100]';
            
            modal.innerHTML = `
                <div class="bg-zinc-900 w-full max-w-md mx-4 rounded-3xl p-6 border border-zinc-700">
                    <div class="text-xl font-bold mb-1">修改隊名</div>
                    <div class="text-sm text-zinc-400 mb-4">Team ID: ${teamId}</div>
                    
                    <input type="text" id="edit-team-name-input" value="${safeVal}" 
                           class="w-full bg-zinc-800 border border-zinc-700 focus:border-amber-500 rounded-2xl px-5 py-3 text-lg mb-6">
                    
                    <div class="flex gap-x-3">
                        <button onclick="this.closest('.fixed').remove()" 
                                class="flex-1 py-3 bg-zinc-700 hover:bg-zinc-600 rounded-2xl text-sm">
                            取消
                        </button>
                        <button onclick="confirmUpdateTeamName('${teamId}', this)" 
                                class="flex-1 py-3 bg-amber-500 hover:bg-amber-600 text-zinc-950 font-semibold rounded-2xl text-sm">
                            確認修改
                        </button>
                    </div>
                </div>
            `;
            
            document.body.appendChild(modal);
            
            setTimeout(() => {
                const input = modal.querySelector('#edit-team-name-input');
                if (input) input.focus();
            }, 100);
        }

        function confirmUpdateTeamName(teamId, buttonElement) {
            const input = document.getElementById('edit-team-name-input');
            const newName = input.value.trim();
            
            if (!newName) {
                showGmToast('隊名不能為空', 'error');
                return;
            }

            buttonElement.disabled = true;
            buttonElement.textContent = '更新中...';

            fetch('/gm/update_team_name', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: new URLSearchParams({
                    team_id: teamId,
                    new_name: newName
                })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    buttonElement.closest('.fixed').remove();
                    showGmToast('隊名已成功更新！', 'success');
                    loadGMTeams();
                } else {
                    showGmToast(data.error || '更新失敗', 'success');
                    buttonElement.disabled = false;
                    buttonElement.textContent = '確認修改';
                }
            })
            .catch(() => {
                showGmToast('發生錯誤，請重試', 'error');
                buttonElement.disabled = false;
                buttonElement.textContent = '確認修改';
            });
        }

        async function gmAssignSquadToTeam(teamId) {
            const modal = document.createElement('div');
            modal.className = 'fixed inset-0 bg-black/80 flex items-center justify-center z-[100]';

            modal.innerHTML = `
                <div class="bg-zinc-900 w-full max-w-md mx-4 rounded-3xl p-6 border border-zinc-700">
                    <div class="text-xl font-bold mb-1">分配 / 轉隊玩家</div>
                    <div class="text-sm text-zinc-400 mb-4">Team ID: ${teamId}</div>

                    <div class="mb-4">
                        <div class="text-sm text-zinc-400 mb-2">選擇玩家：</div>
                        <select id="assign-player-select"
                                class="w-full bg-zinc-800 border border-zinc-700 rounded-2xl px-4 py-3 text-sm">
                            <option value="">載入中...</option>
                        </select>
                    </div>

                    <div class="flex gap-x-3">
                        <button onclick="this.closest('.fixed').remove()"
                                class="flex-1 py-3 bg-zinc-700 hover:bg-zinc-600 rounded-2xl text-sm">
                            取消
                        </button>
                        <button onclick="confirmAssignPlayer('${teamId}', this)"
                                class="flex-1 py-3 bg-amber-500 hover:bg-amber-600 text-zinc-950 font-semibold rounded-2xl text-sm">
                            確認分配
                        </button>
                    </div>
                </div>
            `;

            document.body.appendChild(modal);

            try {
                const res = await fetch(
                    `/gm/assignable_players?team_id=${encodeURIComponent(teamId)}`,
                    { credentials: 'same-origin' }
                );
                const data = await res.json();

                const select = modal.querySelector('#assign-player-select');
                select.innerHTML = '<option value="">-- 請選擇玩家 --</option>';

                if (!res.ok || data.success === false) {
                    select.innerHTML = '<option value="">載入失敗</option>';
                    showGmToast(data.error || '載入玩家列表失敗，請重新登入 GM', 'error');
                    return;
                }

                const players = data.players || [];
                if (players.length === 0) {
                    select.innerHTML = '<option value="">（無可分配玩家 — 可能全部已在隊內）</option>';
                    return;
                }

                players.forEach(player => {
                    const option = document.createElement('option');
                    option.value = player.squad_id;
                    option.textContent = player.label || `${player.display_name} (${player.squad_id})`;
                    select.appendChild(option);
                });
            } catch (e) {
                showGmToast('載入玩家列表失敗', 'error');
                modal.remove();
            }
        }

        async function confirmAssignPlayer(teamId, buttonElement) {
            const modal = buttonElement.closest('.fixed');
            const select = modal.querySelector('#assign-player-select');
            const squadId = select.value;

            if (!squadId) {
                showGmToast('請選擇一個玩家', 'error');
                return;
            }

            buttonElement.disabled = true;
            buttonElement.textContent = '分配中...';

            const res = await fetch('/gm/assign_squad', {
                method: 'POST',
                credentials: 'same-origin',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: new URLSearchParams({
                    squad_id: squadId,
                    team_id: teamId
                })
            });

            const data = await res.json();

            if (data.success) {
                modal.remove();
                showGmToast(data.message || '分配成功！', 'success');
                loadGMTeams();
            } else {
                showGmToast(data.error || '分配失敗', 'success');
                buttonElement.disabled = false;
                buttonElement.textContent = '確認分配';
            }
        }

        function gmSetRoutePrompt(teamId) {
            const modal = document.createElement('div');
            modal.className = 'fixed inset-0 bg-black/80 flex items-center justify-center z-[100]';
            modal.innerHTML = `
                <div class="bg-zinc-900 w-full max-w-md mx-4 rounded-3xl p-6 border border-zinc-700">
                    <div class="text-xl font-bold mb-1">設定 Team 路線</div>
                    <div class="text-sm text-zinc-400 mb-6">Team ID: ${teamId}</div>
                    
                    <div class="grid grid-cols-2 gap-4 mb-6">
                        <div onclick="gmConfirmSetRoute('${teamId}', 'iggy', this)" 
                             class="route-card route-iggy p-6 text-center cursor-pointer">
                            <div class="text-3xl mb-2">🔥</div>
                            <div class="text-xl font-bold">Iggy 路線</div>
                            <div class="text-xs mt-1 opacity-80">界線、力量、面對 Judas</div>
                        </div>
                        
                        <div onclick="gmConfirmSetRoute('${teamId}', 'marah', this)" 
                             class="route-card route-marah p-6 text-center cursor-pointer">
                            <div class="text-3xl mb-2">🌊</div>
                            <div class="text-xl font-bold">Marah 路線</div>
                            <div class="text-xs mt-1 opacity-80">智慧、韌性、深度連結</div>
                        </div>
                    </div>
                    
                    <button onclick="this.closest('.fixed').remove()" 
                            class="w-full py-3 bg-zinc-700 hover:bg-zinc-600 rounded-2xl text-sm">
                        取消
                    </button>
                </div>
            `;
            document.body.appendChild(modal);
        }

        function gmConfirmSetRoute(teamId, route, element) {
            fetch('/gm/set_team_route', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: new URLSearchParams({team_id: teamId, route: route})
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    element.closest('.fixed').remove();
                    showGmToast('路線已成功設定為 ' + (route === 'iggy' ? 'Iggy' : 'Marah', 'success'));
                    loadGMTeams();
                } else {
                    showGmToast('設定失敗', 'success');
                }
            });
        }

        async function gmViewTeamMembers(teamId, teamName) {
            const modal = document.createElement('div');
            modal.className = 'fixed inset-0 bg-black/80 flex items-center justify-center z-[100]';

            modal.innerHTML = `
                <div class="bg-zinc-900 w-full max-w-2xl mx-4 rounded-3xl p-6 border border-zinc-700 max-h-[80vh] overflow-auto">
                    <div class="flex justify-between items-center mb-6">
                        <div>
                            <div class="text-xl font-bold">${teamName}</div>
                            <div class="text-sm text-zinc-400">Team ID: ${teamId}</div>
                        </div>
                        <button onclick="this.closest('.fixed').remove()"
                                class="text-3xl leading-none text-zinc-400 hover:text-white">×</button>
                    </div>
                    <div id="team-members-content">
                        <div class="text-center py-8 text-zinc-400">載入中...</div>
                    </div>
                </div>
            `;

            document.body.appendChild(modal);

            const contentEl = modal.querySelector('#team-members-content');
            try {
                const res = await fetch(`/gm/team_members/${teamId}`);
                const data = await res.json();

                if (!data.members || data.members.length === 0) {
                    contentEl.innerHTML = '<div class="text-center py-6 text-zinc-400">暫無成員</div>';
                    return;
                }

                contentEl.innerHTML = '';
                data.members.forEach(m => {
                    const el = document.createElement('div');
                    el.className = 'bg-zinc-800 border border-zinc-700 rounded-2xl p-4 mb-3';
                    const name = m.display_name || m.squad_id;
                    el.innerHTML = `
                        <div class="flex justify-between items-start mb-2">
                            <div class="flex items-center gap-x-3">
                                <img src="/static/avatars/${m.avatar || 'default.png'}"
                                     class="w-10 h-10 rounded-full object-cover border border-zinc-600 shrink-0">
                                <div>
                                    <div class="font-semibold text-lg">${name}</div>
                                    <div class="text-xs text-zinc-500 font-mono">${m.squad_id}</div>
                                </div>
                            </div>
                            <a href="/gm/squad/${m.squad_id}" class="text-xs px-3 py-1 bg-amber-500/20 text-amber-400 rounded-xl hover:bg-amber-500/30">詳情</a>
                        </div>
                        <div class="grid grid-cols-4 gap-2 text-center text-xs">
                            <div><div class="text-red-400 font-mono">${m.hp}</div><div class="text-zinc-500">生命值</div></div>
                            <div><div class="text-purple-400 font-mono">${m.sanity}</div><div class="text-zinc-500">神智</div></div>
                            <div><div class="text-orange-400 font-mono">${m.power}</div><div class="text-zinc-500">力量</div></div>
                            <div><div class="text-emerald-400 font-mono">${m.resilience}</div><div class="text-zinc-500">韌性</div></div>
                        </div>
                    `;
                    contentEl.appendChild(el);
                });
            } catch (e) {
                contentEl.innerHTML = '<div class="text-red-400 text-center py-6">載入失敗</div>';
            }
        }

        async function downloadTeamImages(teamId) {
            try {
                const res = await fetch(`/gm/download_team_images/${encodeURIComponent(teamId)}`, { credentials: 'same-origin' });
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    showGmToast(data.error || '下載失敗', 'error');
                    return;
                }
                const blob = await res.blob();
                const disposition = res.headers.get('Content-Disposition') || '';
                let filename = `team_${teamId}_images.zip`;
                const match = disposition.match(/filename="?([^";]+)"?/);
                if (match) filename = match[1];
                const url = URL.createObjectURL(blob);
                const link = document.createElement('a');
                link.href = url;
                link.download = filename;
                link.click();
                URL.revokeObjectURL(url);
            } catch (e) {
                showGmToast('下載失敗', 'error');
            }
        }

        async function viewPlayerLogs(squadId) {
            const modal = document.getElementById('player-log-modal');
            const titleEl = document.getElementById('player-log-modal-title');
            const contentEl = document.getElementById('player-log-modal-content');
            modal.classList.remove('hidden');
            modal.classList.add('flex');
            titleEl.textContent = '載入中...';
            contentEl.innerHTML = '<div class="text-zinc-400 text-center py-8">載入中...</div>';

            try {
                const res = await fetch(`/gm/player_logs/${encodeURIComponent(squadId)}`, { credentials: 'same-origin' });
                const data = await res.json();

                if (!res.ok || !data.success) {
                    titleEl.textContent = '載入失敗';
                    contentEl.innerHTML = `<div class="text-red-400 text-center py-8">${data.error || '載入失敗'}</div>`;
                    return;
                }

                const player = data.player || {};
                const teamLabel = player.team_name || player.team_id || '未入隊';
                titleEl.textContent = `${player.display_name || squadId} · ${teamLabel}`;

                const logs = data.logs || [];
                if (logs.length === 0) {
                    contentEl.innerHTML = '<div class="text-zinc-400 text-center py-8">暫無任務記錄</div>';
                    return;
                }

                contentEl.innerHTML = '';
                logs.forEach(log => {
                    const div = document.createElement('div');
                    div.className = 'border border-zinc-700 rounded-2xl p-4 mb-3';
                    div.innerHTML = `
                        <div class="flex flex-wrap justify-between items-start gap-2 mb-2">
                            <div>
                                <div class="font-semibold text-amber-400">${log.task_name}</div>
                                <div class="text-xs text-zinc-500 font-mono">${log.task_id || ''}</div>
                            </div>
                            <span class="text-xs px-2 py-0.5 bg-emerald-900/50 text-emerald-300 rounded-full">${log.status}</span>
                        </div>
                        <div class="text-xs text-zinc-500 mb-2">${log.timestamp || ''}</div>
                        ${log.description ? `<div class="text-zinc-300 text-sm mb-3 whitespace-pre-wrap">${log.description}</div>` : ''}
                        ${(log.photo_url || log.photo_path) ? `
                            <img src="${log.photo_url || '/' + log.photo_path}" class="max-h-48 rounded-xl border border-zinc-700">
                        ` : ''}
                    `;
                    contentEl.appendChild(div);
                });
            } catch (e) {
                titleEl.textContent = '載入失敗';
                contentEl.innerHTML = '<div class="text-red-400 text-center py-8">載入失敗</div>';
            }
        }

        function hidePlayerLogModal() {
            const modal = document.getElementById('player-log-modal');
            modal.classList.remove('flex');
            modal.classList.add('hidden');
        }

        function formatOverviewTime(ts) {
            if (!ts) return '—';
            try {
                const d = new Date(ts);
                if (isNaN(d.getTime())) return ts;
                return d.toLocaleString('zh-HK', { hour12: false });
            } catch (e) {
                return ts;
            }
        }

        async function loadTeamsOverview() {
            const container = document.getElementById('gm-overview-content');
            container.innerHTML = '<div class="text-zinc-400 text-center py-8">載入中...</div>';

            try {
                const res = await fetch('/gm/teams_overview', { credentials: 'same-origin' });
                const data = await res.json();

                if (!res.ok || !data.success) {
                    container.innerHTML = '<div class="text-red-400 text-center py-8">載入失敗</div>';
                    return;
                }

                const teams = data.teams || [];
                const solo = data.solo_players || [];

                if (teams.length === 0 && solo.length === 0) {
                    container.innerHTML = '<div class="text-zinc-400 text-center py-8">暫無隊伍或玩家資料</div>';
                    return;
                }

                let html = '';

                if (teams.length > 0) {
                    html += '<div class="space-y-4">';
                    teams.forEach(team => {
                        const routeClass = team.route === 'iggy'
                            ? 'bg-red-900/40 text-red-300'
                            : team.route === 'marah'
                                ? 'bg-blue-900/40 text-blue-300'
                                : 'bg-zinc-700 text-zinc-300';
                        html += `
                            <div class="bg-zinc-800 border border-zinc-700 rounded-2xl p-5 text-left">
                                <div class="flex flex-wrap justify-between items-start gap-3 mb-4">
                                    <div>
                                        <div class="text-lg font-semibold text-emerald-400">${team.team_name}</div>
                                        <div class="text-xs text-zinc-500 font-mono mt-0.5">${team.team_id}</div>
                                        <div class="text-sm text-zinc-300 mt-1">隊長：${team.leader_name} · ${team.member_count} 位成員</div>
                                    </div>
                                    <span class="text-xs px-3 py-1 rounded-full ${routeClass}">${team.route_label}</span>
                                </div>
                                <div class="grid grid-cols-2 md:grid-cols-4 gap-3 text-center text-xs mb-4">
                                    <div class="bg-zinc-900/60 rounded-xl py-2"><div class="text-red-400 font-mono text-base">${team.avg_hp}</div><div class="text-zinc-500">平均生命值</div></div>
                                    <div class="bg-zinc-900/60 rounded-xl py-2"><div class="text-purple-400 font-mono text-base">${team.avg_sanity}</div><div class="text-zinc-500">平均神智</div></div>
                                    <div class="bg-zinc-900/60 rounded-xl py-2"><div class="text-orange-400 font-mono text-base">${team.avg_power}</div><div class="text-zinc-500">平均力量</div></div>
                                    <div class="bg-zinc-900/60 rounded-xl py-2"><div class="text-emerald-400 font-mono text-base">${team.avg_resilience}</div><div class="text-zinc-500">平均韌性</div></div>
                                </div>
                                <div class="flex flex-wrap gap-x-6 gap-y-1 text-sm text-zinc-400 mb-4">
                                    <span>已完成任務：<strong class="text-amber-400">${team.distinct_tasks}</strong></span>
                                    <span>劇情階段：<strong class="text-zinc-200">Stage ${team.story_stage}</strong></span>
                                    <span>提交次數：<strong class="text-zinc-200">${team.submission_count}</strong></span>
                                    <span>最近提交：<strong class="text-zinc-200">${formatOverviewTime(team.last_submission)}</strong></span>
                                </div>
                                <div class="flex flex-wrap gap-2 mb-4">
                                    <button onclick="downloadTeamImages('${team.team_id}')"
                                            class="px-3 py-1.5 text-xs bg-blue-600 hover:bg-blue-700 rounded-xl flex items-center gap-x-1">
                                        <i class="fa-solid fa-download"></i>
                                        <span>下載該隊圖片 (ZIP)</span>
                                    </button>
                                </div>
                                ${(team.members && team.members.length) ? `
                                    <div class="border-t border-zinc-700 pt-3">
                                        <div class="text-xs text-zinc-500 mb-2">隊員任務記錄</div>
                                        <div class="flex flex-wrap gap-2">
                                            ${team.members.map(m => `
                                                <button onclick="viewPlayerLogs('${m.squad_id}')"
                                                        class="px-2 py-1 text-xs bg-zinc-700 hover:bg-zinc-600 rounded-lg">
                                                    ${m.is_leader ? '👑 ' : ''}${m.display_name}
                                                </button>
                                            `).join('')}
                                        </div>
                                    </div>
                                ` : ''}
                            </div>
                        `;
                    });
                    html += '</div>';
                }

                if (solo.length > 0) {
                    html += `
                        <div class="mt-8">
                            <h3 class="text-lg font-semibold text-left mb-3 text-zinc-300">未加入隊伍的玩家</h3>
                            <div class="overflow-x-auto">
                                <table class="w-full text-sm text-left">
                                    <thead>
                                        <tr class="border-b border-zinc-700 text-zinc-400">
                                            <th class="py-2 pr-4">玩家</th>
                                            <th class="py-2 pr-4">路線</th>
                                            <th class="py-2 pr-4">生命值/神智/力量/韌性</th>
                                            <th class="py-2 pr-4">任務</th>
                                            <th class="py-2 pr-4">階段</th>
                                            <th class="py-2 pr-4">提交</th>
                                            <th class="py-2 pr-4">最近提交</th>
                                            <th class="py-2">操作</th>
                                        </tr>
                                    </thead>
                                    <tbody class="divide-y divide-zinc-800">
                    `;
                    solo.forEach(p => {
                        html += `
                            <tr class="hover:bg-zinc-800/50">
                                <td class="py-3 pr-4">
                                    <a href="/gm/squad/${p.squad_id}" class="text-amber-400 hover:underline">${p.display_name}</a>
                                    <div class="text-xs text-zinc-500 font-mono">${p.squad_id}</div>
                                </td>
                                <td class="py-3 pr-4 text-xs">${p.route_label}</td>
                                <td class="py-3 pr-4 font-mono text-xs">${p.hp}/${p.sanity}/${p.power}/${p.resilience}</td>
                                <td class="py-3 pr-4">${p.distinct_tasks}</td>
                                <td class="py-3 pr-4">Stage ${p.story_stage}</td>
                                <td class="py-3 pr-4">${p.submission_count}</td>
                                <td class="py-3 text-xs text-zinc-400">${formatOverviewTime(p.last_submission)}</td>
                                <td class="py-3">
                                    ${p.submission_count > 0 ? `
                                        <button onclick="viewPlayerLogs('${p.squad_id}')"
                                                class="px-2 py-1 text-xs bg-zinc-700 hover:bg-zinc-600 rounded-lg">任務 Log</button>
                                    ` : '<span class="text-zinc-500">—</span>'}
                                </td>
                            </tr>
                        `;
                    });
                    html += '</tbody></table></div></div>';
                }

                container.innerHTML = html;
            } catch (e) {
                container.innerHTML = '<div class="text-red-400 text-center py-8">載入失敗</div>';
            }
        }

        let combatV2Enabled = true;

        async function loadCombatV2Setting() {
            const statusEl = document.getElementById('combat-v2-status-text');
            const btn = document.getElementById('combat-v2-toggle-btn');
            if (!statusEl || !btn) return;
            try {
                const res = await fetch('/gm/api/combat_v2', { credentials: 'same-origin' });
                const data = await res.json();
                if (!res.ok || !data.success) {
                    statusEl.textContent = '無法讀取戰鬥系統狀態';
                    return;
                }
                combatV2Enabled = !!data.enabled;
                statusEl.textContent = data.message || (combatV2Enabled ? '已開啟' : '已關閉');
                btn.textContent = combatV2Enabled ? '關閉戰鬥系統' : '開啟戰鬥系統';
                btn.className = combatV2Enabled
                    ? 'px-5 py-2.5 rounded-2xl text-sm font-semibold bg-red-600 hover:bg-red-700 text-white'
                    : 'px-5 py-2.5 rounded-2xl text-sm font-semibold bg-emerald-600 hover:bg-emerald-500 text-white';
            } catch (e) {
                statusEl.textContent = '載入失敗';
            }
        }

        async function toggleCombatV2() {
            const next = !combatV2Enabled;
            const action = next ? '開啟' : '關閉';
            if (!confirm(`確定要${action}玩家端戰鬥系統 V2？\\n關閉後玩家進入戰鬥頁會見到維護提示。`)) return;
            try {
                const res = await fetch('/gm/api/combat_v2', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'same-origin',
                    body: JSON.stringify({ enabled: next }),
                });
                const data = await res.json();
                if (!res.ok || !data.success) {
                    showGmToast(data.error || '設定失敗', 'error');
                    return;
                }
                showGmToast(data.message || '已更新', 'success');
                await loadCombatV2Setting();
            } catch (e) {
                showGmToast('設定失敗', 'error');
            }
        }

        async function loadActiveCombats() {
            const container = document.getElementById('gm-combat-content');
            container.innerHTML = '<div class="text-zinc-400 text-center py-8">載入中...</div>';

            try {
                const res = await fetch('/gm/active_combats', { credentials: 'same-origin' });
                const data = await res.json();

                if (!res.ok || !data.success) {
                    container.innerHTML = '<div class="text-red-400 text-center py-8">載入失敗</div>';
                    return;
                }

                const combats = data.combats || [];
                if (combats.length === 0) {
                    container.innerHTML = '<div class="text-zinc-400 text-center py-8">目前沒有進行中的戰鬥</div>';
                    return;
                }

                container.innerHTML = '<div class="space-y-4">' + combats.map(c => `
                    <div class="bg-zinc-800 border border-zinc-700 rounded-2xl p-5 text-left">
                        <div class="flex flex-wrap justify-between items-start gap-3 mb-3">
                            <div>
                                <div class="text-lg font-semibold text-red-400">${c.title || c.encounter_id}</div>
                                <div class="text-xs text-zinc-500 font-mono mt-0.5">Combat #${c.combat_id} · ${c.encounter_id}</div>
                                <div class="text-sm text-zinc-300 mt-1">${c.team_name || '未知隊伍'} (${c.team_id || '—'})</div>
                            </div>
                            <span class="text-xs px-3 py-1 rounded-full bg-amber-900/40 text-amber-300">${c.status}</span>
                        </div>
                        <div class="grid grid-cols-2 md:grid-cols-4 gap-3 text-center text-xs mb-4">
                            <div class="bg-zinc-900/60 rounded-xl py-2"><div class="text-red-400 font-mono text-base">${c.enemy_hp}/${c.enemy_max_hp}</div><div class="text-zinc-500">敵人 HP</div></div>
                            <div class="bg-zinc-900/60 rounded-xl py-2"><div class="text-amber-400 font-mono text-base">Phase ${c.current_phase || 0}</div><div class="text-zinc-500">回合</div></div>
                            <div class="bg-zinc-900/60 rounded-xl py-2"><div class="text-emerald-400 font-mono text-base">${c.submitted_count}/${c.participant_count}</div><div class="text-zinc-500">已提交行動</div></div>
                            <div class="bg-zinc-900/60 rounded-xl py-2"><div class="text-zinc-200 font-mono text-xs">${formatOverviewTime(c.phase_deadline)}</div><div class="text-zinc-500">Phase 截止</div></div>
                        </div>
                        <div class="flex flex-wrap gap-2">
                            ${c.can_resolve ? `
                                <button onclick="gmResolveCombatPhase(${c.combat_id}, '${(c.title || c.encounter_id).replace(/'/g, '')}')"
                                        class="px-4 py-2 text-sm bg-red-600 hover:bg-red-700 rounded-xl flex items-center gap-x-2">
                                    <i class="fa-solid fa-gavel"></i>
                                    <span>強制結算 Phase</span>
                                </button>
                            ` : `
                                <span class="text-xs text-zinc-500 py-2">非 player_phase，無法強制結算</span>
                            `}
                        </div>
                    </div>
                `).join('') + '</div>';
            } catch (e) {
                container.innerHTML = '<div class="text-red-400 text-center py-8">載入失敗</div>';
            }
        }

        async function gmResolveCombatPhase(combatId, title) {
            if (!confirm(`確定要強制結算「${title}」(Combat #${combatId}) 的 Player Phase？\\n未提交行動的隊員將視為未行動。`)) return;

            try {
                const res = await fetch('/gm/combat/resolve_phase', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'same-origin',
                    body: JSON.stringify({ combat_id: combatId }),
                });
                const data = await res.json();

                if (!res.ok || !data.success) {
                    showGmToast(data.error || '結算失敗', 'error');
                    return;
                }

                if (data.outcome === 'victory') {
                    showGmToast('戰鬥結束：隊伍勝利！', 'success');
                } else if (data.outcome === 'defeat') {
                    showGmToast('戰鬥結束：隊伍落敗。', 'success');
                } else {
                    showGmToast(data.message || 'Phase 已強制結算', 'success');
                }
                loadActiveCombats();
            } catch (e) {
                showGmToast('結算失敗：' + e.message, 'error');
            }
        }

        function switchGMTab(tab) {
            const squadsTab = document.getElementById('gm-squads-tab');
            const teamsTab = document.getElementById('gm-teams-tab');
            const overviewTab = document.getElementById('gm-overview-tab');
            const combatTab = document.getElementById('gm-combat-tab');
            const btnSquads = document.getElementById('tab-squads');
            const btnTeams = document.getElementById('tab-teams');
            const btnOverview = document.getElementById('tab-overview');
            const btnCombat = document.getElementById('tab-combat');
            const allTabs = [squadsTab, teamsTab, overviewTab, combatTab];
            const allBtns = [btnSquads, btnTeams, btnOverview, btnCombat];

            allTabs.forEach(el => el.classList.add('hidden'));
            allBtns.forEach(btn => btn.classList.remove('active', 'bg-amber-500', 'text-zinc-950'));

            if (tab === 'teams') {
                teamsTab.classList.remove('hidden');
                btnTeams.classList.add('active', 'bg-amber-500', 'text-zinc-950');
                loadGMTeams();
            } else if (tab === 'overview') {
                overviewTab.classList.remove('hidden');
                btnOverview.classList.add('active', 'bg-amber-500', 'text-zinc-950');
                loadTeamsOverview();
            } else if (tab === 'combat') {
                combatTab.classList.remove('hidden');
                btnCombat.classList.add('active', 'bg-amber-500', 'text-zinc-950');
                loadCombatV2Setting();
                loadActiveCombats();
                if (typeof loadGmUnlockMode === 'function') {
                    loadGmUnlockMode();
                }
                if (typeof loadGmResetEncounterOptions === 'function') {
                    loadGmResetEncounterOptions();
                }
            } else {
                squadsTab.classList.remove('hidden');
                btnSquads.classList.add('active', 'bg-amber-500', 'text-zinc-950');
            }
        }

        setTimeout(() => {
            const btn = document.getElementById('tab-squads');
            if (btn) btn.classList.add('active', 'bg-amber-500', 'text-zinc-950');
        }, 300);
        </script>

        <!-- 玩家任務 Log Modal -->
        <div id="player-log-modal" onclick="if (event.target.id === 'player-log-modal') hidePlayerLogModal()"
             class="hidden fixed inset-0 bg-black/80 items-center justify-center z-[60]">
            <div onclick="event.stopImmediatePropagation()"
                 class="bg-zinc-900 w-full max-w-2xl mx-4 rounded-3xl p-6 border border-zinc-700 max-h-[85vh] flex flex-col">
                <div class="flex justify-between items-start mb-4 shrink-0">
                    <div>
                        <div class="text-lg font-bold" id="player-log-modal-title">任務 Log</div>
                        <div class="text-xs text-zinc-500 mt-0.5">玩家過往提交記錄</div>
                    </div>
                    <button onclick="hidePlayerLogModal()" class="text-3xl leading-none text-zinc-400 hover:text-white">×</button>
                </div>
                <div id="player-log-modal-content" class="overflow-y-auto flex-1"></div>
            </div>
        </div>

        <!-- 清空圖片確認 Modal -->
        <div id="clear-images-modal" onclick="if (event.target.id === 'clear-images-modal') hideClearImagesModal()"
             class="hidden fixed inset-0 bg-black/80 flex items-center justify-center z-[60]">
            <div onclick="event.stopImmediatePropagation()"
                 class="bg-zinc-900 w-full max-w-md mx-4 rounded-3xl p-6 border border-red-500/30">

                <div class="text-red-400 font-semibold text-xl mb-2">⚠️ 確認清空所有上傳圖片</div>
                <div class="text-zinc-300 mb-6">此操作無法復原。請輸入 <span class="font-mono text-amber-400">CLEAR_IMAGES</span> 確認。</div>

                <input type="text" id="clear-images-confirm" placeholder="輸入 CLEAR_IMAGES"
                       class="w-full bg-zinc-800 border border-zinc-700 focus:border-red-500 rounded-2xl px-5 py-3 mb-4">

                <div class="flex gap-x-3">
                    <button onclick="hideClearImagesModal()"
                            class="flex-1 py-3 bg-zinc-700 hover:bg-zinc-600 rounded-2xl">取消</button>
                    <button onclick="confirmClearAllImages()"
                            class="flex-1 py-3 bg-red-600 hover:bg-red-700 rounded-2xl font-medium">確認刪除</button>
                </div>
            </div>
        </div>

        <!-- 重置確認 Modal -->
        <div id="reset-modal" onclick="if (event.target.id === 'reset-modal') hideResetModal()" 
             class="hidden fixed inset-0 bg-black/80 flex items-center justify-center z-[60]">
            <div onclick="event.stopImmediatePropagation()" 
                 class="bg-zinc-900 w-full max-w-md mx-4 rounded-3xl p-6 border border-red-500/30">
                
                <div class="text-red-400 font-semibold text-xl mb-2">⚠️ 確認重置遊戲</div>
                <div class="text-zinc-300 mb-6">此操作無法復原。請輸入重置密碼確認。</div>
                
                <input type="password" id="reset-password" placeholder="輸入重置密碼" 
                       class="w-full bg-zinc-800 border border-zinc-700 focus:border-red-500 rounded-2xl px-5 py-3 mb-4">
                
                <div class="flex gap-x-3">
                    <button onclick="hideResetModal()" 
                            class="flex-1 py-3 bg-zinc-700 hover:bg-zinc-600 rounded-2xl">取消</button>
                    <button onclick="confirmResetGame()" 
                            class="flex-1 py-3 bg-red-600 hover:bg-red-700 rounded-2xl font-medium">確認重置</button>
                </div>
            </div>
        </div>

        <script>
        function showClearImagesModal() {
            document.getElementById('clear-images-modal').classList.remove('hidden');
            document.getElementById('clear-images-modal').classList.add('flex');
            document.getElementById('clear-images-confirm').focus();
        }

        function hideClearImagesModal() {
            document.getElementById('clear-images-modal').classList.remove('flex');
            document.getElementById('clear-images-modal').classList.add('hidden');
            document.getElementById('clear-images-confirm').value = '';
        }

        async function confirmClearAllImages() {
            const confirmText = document.getElementById('clear-images-confirm').value.trim();

            if (confirmText !== 'CLEAR_IMAGES') {
                showGmToast('確認碼錯誤！請輸入 CLEAR_IMAGES', 'error');
                return;
            }

            if (!confirm('確定要刪除所有玩家上傳過的圖片嗎？此操作不可恢復！')) {
                return;
            }

            try {
                const res = await fetch('/gm/clear_all_images', {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ confirm: confirmText })
                });
                const data = await res.json();

                if (data.success) {
                    showGmToast(data.message || '圖片已清空', 'success');
                    hideClearImagesModal();
                } else {
                    showGmToast(data.error || '清空失敗', 'success');
                }
            } catch (e) {
                showGmToast('發生錯誤，請重試', 'error');
            }
        }

        function showResetModal() {
            document.getElementById('reset-modal').classList.remove('hidden');
            document.getElementById('reset-modal').classList.add('flex');
            document.getElementById('reset-password').focus();
        }

        function hideResetModal() {
            document.getElementById('reset-modal').classList.remove('flex');
            document.getElementById('reset-modal').classList.add('hidden');
            document.getElementById('reset-password').value = '';
        }

        function confirmResetGame() {
            const password = document.getElementById('reset-password').value;
            
            fetch('/gm/reset_game', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: new URLSearchParams({password: password})
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    showGmToast(data.message || '遊戲已重置', 'success');
                    window.location.reload();
                } else {
                    showGmToast(data.error || '密碼錯誤或重置失敗', 'success');
                }
            })
            .catch(() => {
                showGmToast('發生錯誤，請重試', 'error');
            });
        }
        </script>
    </div>

</body>
</html>
"""

GM_SQUAD_DETAIL_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{{ squad.display_name or squad.squad_id }} 詳情 • GM</title>
    <script>
      (function() {
        const originalWarn = console.warn;
        console.warn = (...args) => {
          const message = args.join(' ');
          if (message.includes('tailwindcss.com should not be used in production')) return;
          originalWarn.apply(console, args);
        };
      })();
    </script>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
      setTimeout(() => {
        const style = document.createElement('style');
        style.innerHTML = `
      body::before { display: none !important; }
    `;
        document.head.appendChild(style);

        const originalWarn = console.warn;
        console.warn = (...args) => {
          const message = args.join(' ');
          if (message.includes('tailwindcss.com should not be used in production')) {
            return;
          }
          originalWarn.apply(console, args);
        };
      }, 100);
    </script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
</head>
<body class="bg-zinc-950 text-white p-8">
    <div class="max-w-5xl mx-auto">
        <div class="mb-8">
            <a href="/gm/dashboard" class="text-amber-400 hover:underline flex items-center gap-x-2 mb-2">
                <i class="fa-solid fa-arrow-left"></i>
                <span>返回 GM Dashboard</span>
            </a>
            
            <div class="flex items-end gap-x-4">
                <img src="/static/avatars/{{ squad.avatar or 'default.png' }}"
                     class="w-16 h-16 rounded-full object-cover border-2 border-zinc-600">
                <div class="flex items-end gap-x-3">
                    <h1 class="text-3xl font-bold">{{ squad.display_name or squad.squad_id }}</h1>
                </div>
            </div>
            
            <div class="text-sm text-zinc-400 mt-1">玩家詳情與提交記錄</div>
        </div>

        <div class="bg-zinc-900 rounded-3xl p-6 mb-8">
            <h2 class="text-lg font-semibold mb-4">玩家目前狀態</h2>
            
            <div class="grid grid-cols-2 md:grid-cols-4 gap-x-6 gap-y-4 text-sm">
                <div>
                    <span class="text-zinc-400">顯示名稱</span><br>
                    <span class="font-semibold text-lg">{{ squad.display_name or squad.squad_id }}</span>
                </div>
                <div>
                    <span class="text-zinc-400">所屬 Team</span><br>
                    <span class="font-mono text-emerald-400">{{ squad.team_id or '未加入任何隊' }}</span>
                </div>
                <div>
                    <span class="text-zinc-400">路線</span><br>
                    <span class="font-mono">{{ squad.route_label }}</span>
                </div>
                <div>
                    <span class="text-zinc-400">Resource</span><br>
                    <span id="gm-stat-resources" class="font-mono text-purple-400">{{ squad.resources }}</span>
                </div>
                <div>
                    <span class="text-zinc-400">PIN 狀態</span><br>
                    <span class="font-mono {{ 'text-emerald-400' if squad.has_pin else 'text-zinc-500' }}">
                        {{ '已設定' if squad.has_pin else '未設定' }}
                    </span>
                </div>
                
                <div class="col-span-2 md:col-span-4 grid grid-cols-2 md:grid-cols-4 gap-x-6 gap-y-3 mt-2 pt-4 border-t border-zinc-700">
                    <div>生命值: <span id="gm-stat-hp" class="font-mono text-red-400">{{ squad.hp }}{% if squad.max_hp and squad.max_hp > 100 %} / {{ squad.max_hp }}{% endif %}</span></div>
                    <div>神智: <span id="gm-stat-sanity" class="font-mono text-purple-400">{{ squad.sanity }}</span></div>
                    <div>力量: <span id="gm-stat-power" class="font-mono text-orange-400">{{ squad.power }}</span></div>
                    <div>韌性: <span id="gm-stat-resilience" class="font-mono text-emerald-400">{{ squad.resilience }}</span></div>
                </div>
            </div>
        </div>

        <button onclick="gmResetPlayerPin('{{ squad.squad_id }}', '{{ squad.display_name or squad.squad_id }}')"
                class="mb-8 px-4 py-2 bg-red-600 hover:bg-red-700 rounded-2xl text-sm">
            重置玩家 PIN
        </button>

        <!-- 手動調整數值 -->
        <div class="bg-zinc-900 rounded-3xl p-6 mt-6">
            <h2 class="text-lg font-semibold mb-4">手動調整數值</h2>
            
            <form id="adjust-form" class="grid grid-cols-1 md:grid-cols-4 gap-4">
                <input type="hidden" name="squad_id" value="{{ squad.squad_id }}">
                
                <div>
                    <label class="text-xs text-zinc-400 block mb-1">生命值</label>
                    <div class="flex gap-x-2">
                        <input type="number" name="value" id="hp-value" value="{{ squad.hp }}" 
                               class="w-full bg-zinc-800 border border-zinc-700 rounded-2xl px-4 py-2 text-sm">
                        <button type="button" onclick="adjustValue('hp')" 
                                class="px-4 py-2 bg-red-600 hover:bg-red-700 rounded-2xl text-sm">更新</button>
                    </div>
                </div>
                
                <div>
                    <label class="text-xs text-zinc-400 block mb-1">神智</label>
                    <div class="flex gap-x-2">
                        <input type="number" name="value" id="sanity-value" value="{{ squad.sanity }}" 
                               class="w-full bg-zinc-800 border border-zinc-700 rounded-2xl px-4 py-2 text-sm">
                        <button type="button" onclick="adjustValue('sanity')" 
                                class="px-4 py-2 bg-amber-600 hover:bg-amber-700 rounded-2xl text-sm">更新</button>
                    </div>
                </div>
                
                <div>
                    <label class="text-xs text-zinc-400 block mb-1">力量</label>
                    <div class="flex gap-x-2">
                        <input type="number" id="power-value" value="{{ squad.power }}" 
                               class="w-full bg-zinc-800 border border-zinc-700 rounded-2xl px-4 py-2 text-sm">
                        <button type="button" onclick="adjustValue('power')" 
                                class="px-4 py-2 bg-orange-600 hover:bg-orange-700 rounded-2xl text-sm">更新</button>
                    </div>
                </div>
                <div>
                    <label class="text-xs text-zinc-400 block mb-1">韌性</label>
                    <div class="flex gap-x-2">
                        <input type="number" id="resilience-value" value="{{ squad.resilience }}" 
                               class="w-full bg-zinc-800 border border-zinc-700 rounded-2xl px-4 py-2 text-sm">
                        <button type="button" onclick="adjustValue('resilience')" 
                                class="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 rounded-2xl text-sm">更新</button>
                    </div>
                </div>
                <div>
                    <label class="text-xs text-zinc-400 block mb-1">Resource</label>
                    <div class="flex gap-x-2">
                        <input type="number" id="resource-value" value="{{ squad.resources }}" 
                               class="w-full bg-zinc-800 border border-zinc-700 rounded-2xl px-4 py-2 text-sm">
                        <button type="button" onclick="adjustValue('resources')" 
                                class="px-4 py-2 bg-purple-600 hover:bg-purple-700 rounded-2xl text-sm">更新</button>
                    </div>
                </div>
            </form>
        </div>

        <script>
        async function gmResetPlayerPin(squadId, displayName) {
            if (!confirm(`確定要重置 ${displayName || squadId} 的 PIN 嗎？`)) return;

            const newPin = await showGmInputModal({ title: '輸入新 PIN（留空則自動生成 4 位數字）' });
            if (newPin === null) return;

            fetch('/gm/reset_pin', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: new URLSearchParams({
                    squad_id: squadId,
                    new_pin: newPin || ''
                })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    showGmToast(`${displayName || squadId} 的新 PIN 是：${data.new_pin}\\n請告知玩家！`, 'error');
                    location.reload();
                } else {
                    showGmToast(data.error || '重置失敗', 'success');
                }
            });
        }

        function formatGmHpDisplay(hp, maxHp) {
            const current = Number(hp) || 0;
            const cap = Math.max(100, Number(maxHp) || 100, current);
            return cap > 100 ? `${current} / ${cap}` : String(current);
        }

        function updateGmStatDisplay(squad) {
            if (!squad) return;
            const map = {
                hp: formatGmHpDisplay(squad.hp, squad.max_hp),
                sanity: squad.sanity,
                power: squad.power,
                resilience: squad.resilience,
                resources: squad.resources,
            };
            Object.entries(map).forEach(([key, val]) => {
                const el = document.getElementById('gm-stat-' + key);
                if (el) el.textContent = val ?? '—';
            });
            const inputs = {
                hp: 'hp-value',
                sanity: 'sanity-value',
                power: 'power-value',
                resilience: 'resilience-value',
                resources: 'resource-value',
            };
            Object.entries(inputs).forEach(([key, id]) => {
                const input = document.getElementById(id);
                if (input && squad[key] !== undefined && squad[key] !== null) {
                    input.value = squad[key];
                }
            });
        }

        function adjustValue(field) {
            let valueInput;
            const ids = {hp:'hp-value', sanity:'sanity-value', power:'power-value', resilience:'resilience-value', resources:'resource-value'};
            valueInput = document.getElementById(ids[field]);

            const value = valueInput.value;
            const squadId = '{{ squad.squad_id }}';

            fetch('/gm/adjust', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: new URLSearchParams({
                    squad_id: squadId,
                    field: field,
                    value: value
                })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    updateGmStatDisplay(data.squad);
                    showGmToast((data.message || field + ' 已更新'), 'success');
                } else {
                    showGmToast('更新失敗: ' + data.error, 'success');
                }
            });
        }
        </script>

        <div class="bg-zinc-900 rounded-3xl p-6">
            <h2 class="text-lg font-semibold mb-4">提交記錄（{{ submissions|length }} 筆）</h2>
            
            {% if submissions %}
                <div class="space-y-6">
                    {% for sub in submissions %}
                    <div class="border border-zinc-700 rounded-2xl p-5">
                        <div class="flex justify-between text-sm mb-2">
                            <div>
                                <span class="text-amber-400 font-mono">{{ sub.task_id }}</span>
                            </div>
                            <div class="text-zinc-400 text-xs">{{ sub.timestamp }}</div>
                        </div>
                        
                        {% if sub.content %}
                        <div class="text-zinc-300 mb-3">{{ sub.content }}</div>
                        {% endif %}
                        
                        {% if sub.photo_url or sub.photo_path %}
                        <div>
                            <div class="text-xs text-zinc-400 mb-1">上傳相片：</div>
                            <img src="{{ sub.photo_url or '/' + sub.photo_path }}" class="max-h-64 rounded-xl border border-zinc-700">
                        </div>
                        {% endif %}
                    </div>
                    {% endfor %}
                </div>
            {% else %}
                <div class="text-zinc-400 py-8 text-center">此小隊尚未有任何提交記錄。</div>
            {% endif %}
        </div>
    </div>
</body>
</html>
"""
