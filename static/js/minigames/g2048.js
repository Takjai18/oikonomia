
let timeoutIds = [];
let keydownHandler = null;
let touchStartHandler = null;
let touchEndHandler = null;

const registerTimeout = (fn, delay) => {
    const id = setTimeout(fn, delay);
    timeoutIds.push(id);
    return id;
};

const clearAllTimers = () => {
    timeoutIds.forEach(clearTimeout);
    timeoutIds = [];
};

export function mount(rootEl, options) {
    const config = { winTile: 256, ...options.config };
    let board = Array(16).fill(0);
    let score = 0;
    let hasWon = false;
    let isGameOver = false;

    let touchStartX = 0;
    let touchStartY = 0;

    rootEl.innerHTML = `
        <style>
            .g-container { font-family: sans-serif; max-width: 400px; margin: 0 auto; padding: 15px; text-align: center; background: #faf8ef; color: #776e65; border-radius: 12px; }
            .g-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
            .g-title { font-size: 28px; font-weight: bold; margin: 0; }
            .g-score-box { background: #bbada0; color: white; padding: 5px 15px; border-radius: 6px; font-weight: bold; }
            .g-board { background: #bbada0; padding: 10px; border-radius: 10px; display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; aspect-ratio: 1/1; position: relative; touch-action: none; }
            .g-cell { background: rgba(238, 228, 218, 0.35); border-radius: 6px; display: flex; justify-content: center; align-items: center; font-size: 24px; font-weight: bold; color: #776e65; }
            .tile-2 { background: #eee4da; } .tile-4 { background: #ede0c8; } .tile-8 { background: #f2b179; color: #f9f6f2; } .tile-16 { background: #f59563; color: #f9f6f2; } .tile-32 { background: #f67c5f; color: #f9f6f2; } .tile-64 { background: #f65e3b; color: #f9f6f2; } .tile-128, .tile-256, .tile-512, .tile-1024, .tile-2048 { background: #edcf72; color: #f9f6f2; font-size: 20px; box-shadow: 0 0 10px rgba(243,215,116,0.5); }
            .g-overlay { position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: rgba(238, 228, 218, 0.73); z-index: 10; display: none; flex-direction: column; justify-content: center; align-items: center; border-radius: 10px; }
            .g-msg { font-size: 30px; font-weight: bold; margin-bottom: 20px; color: #776e65; }
            .g-btn { background: #8f7a66; color: white; border: none; padding: 10px 20px; font-size: 18px; font-weight: bold; border-radius: 6px; cursor: pointer; }
            .g-btn:active { background: #73604f; }
        </style>
        <div class="g-container">
            <div class="g-header">
                <h2 class="g-title">2048</h2>
                <div class="g-score-box">分數: <span id="g-score">0</span><br><small>目標: ${config.winTile}</small></div>
            </div>
            <div class="g-board" id="g-board">
                ${Array.from({ length: 16 }, () => `<div class="g-cell"></div>`).join('')}
                <div class="g-overlay" id="g-overlay">
                    <div class="g-msg" id="g-msg-text">Game Over</div>
                    <button class="g-btn" id="g-retry">重新開始</button>
                    <button class="g-btn" id="g-submit" style="display:none; background:#27ae60; margin-top:10px;">提交任務</button>
                </div>
            </div>
        </div>
    `;

    const boardEl = rootEl.querySelector('#g-board');
    
    const spawnTile = () => {
        const emptyIndices = [];
        board.forEach((val, i) => { if (val === 0) emptyIndices.push(i); });
        if (emptyIndices.length > 0) {
            const idx = emptyIndices[Math.floor(Math.random() * emptyIndices.length)];
            board[idx] = Math.random() < 0.9 ? 2 : 4;
        }
    };

    const renderBoard = () => {
        const cells = boardEl.querySelectorAll('.g-cell');
        board.forEach((val, i) => {
            cells[i].className = 'g-cell';
            cells[i].textContent = val > 0 ? val : '';
            if (val > 0) cells[i].classList.add(`tile-${val}`);
        });
        rootEl.querySelector('#g-score').textContent = score;
    };

    const move = (direction) => {
        if (hasWon || isGameOver) return;
        let moved = false;
        
        const slide = (row) => {
            let arr = row.filter(val => val);
            let missing = 4 - arr.length;
            let zeros = Array(missing).fill(0);
            return arr.concat(zeros);
        };
        
        const combine = (row) => {
            for (let i = 0; i < 3; i++) {
                if (row[i] !== 0 && row[i] === row[i + 1]) {
                    row[i] *= 2;
                    score += row[i];
                    row[i + 1] = 0;
                }
            }
            return row;
        };

        let tempBoard = [...board];

        for (let i = 0; i < 4; i++) {
            let row = [];
            if (direction === 'LEFT' || direction === 'RIGHT') {
                row = tempBoard.slice(i * 4, i * 4 + 4);
                if (direction === 'RIGHT') row.reverse();
            } else {
                row = [tempBoard[i], tempBoard[i+4], tempBoard[i+8], tempBoard[i+12]];
                if (direction === 'DOWN') row.reverse();
            }
            
            row = slide(row);
            row = combine(row);
            row = slide(row);
            
            if (direction === 'RIGHT' || direction === 'DOWN') row.reverse();

            if (direction === 'LEFT' || direction === 'RIGHT') {
                for (let j = 0; j < 4; j++) tempBoard[i * 4 + j] = row[j];
            } else {
                for (let j = 0; j < 4; j++) tempBoard[i + j * 4] = row[j];
            }
        }

        if (board.join(',') !== tempBoard.join(',')) {
            board = tempBoard;
            spawnTile();
            renderBoard();
            moved = true;
            checkState();
        }
    };

    const checkState = () => {
        let maxTile = Math.max(...board);
        if (maxTile >= config.winTile && !hasWon) {
            hasWon = true;
            showOverlay("任務完成！", true, maxTile);
        } else if (!board.includes(0)) {
            let canMove = false;
            for (let i = 0; i < 4; i++) {
                for (let j = 0; j < 4; j++) {
                    const current = board[i * 4 + j];
                    if (j < 3 && current === board[i * 4 + j + 1]) canMove = true;
                    if (i < 3 && current === board[(i + 1) * 4 + j]) canMove = true;
                }
            }
            if (!canMove && !hasWon) {
                isGameOver = true;
                showOverlay("遊戲結束", false, maxTile);
            }
        }
    };

    const showOverlay = (msg, isWin, maxTile) => {
        const overlay = rootEl.querySelector('#g-overlay');
        rootEl.querySelector('#g-msg-text').textContent = msg;
        overlay.style.display = 'flex';
        
        const submitBtn = rootEl.querySelector('#g-submit');
        const retryBtn = rootEl.querySelector('#g-retry');
        
        if (isWin) {
            retryBtn.style.display = 'none';
            submitBtn.style.display = 'block';
            submitBtn.onclick = () => {
                submitBtn.disabled = true;
                submitBtn.textContent = "提交中...";
                if (options.onComplete) {
                    // Send maxTile for backend validation, instead of score
                    options.onComplete({ taskId: options.taskId, gameId: 'g2048', result: 'win', score, maxTile });
                }
            };
        } else {
            retryBtn.style.display = 'block';
            submitBtn.style.display = 'none';
        }
    };

    keydownHandler = (e) => {
        if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key)) e.preventDefault();
        if (e.key === 'ArrowLeft') move('LEFT');
        if (e.key === 'ArrowRight') move('RIGHT');
        if (e.key === 'ArrowUp') move('UP');
        if (e.key === 'ArrowDown') move('DOWN');
    };
    window.addEventListener('keydown', keydownHandler);

    touchStartHandler = (e) => {
        touchStartX = e.touches[0].clientX;
        touchStartY = e.touches[0].clientY;
    };
    touchEndHandler = (e) => {
        if (!touchStartX || !touchStartY) return;
        const dx = e.changedTouches[0].clientX - touchStartX;
        const dy = e.changedTouches[0].clientY - touchStartY;
        const absDx = Math.abs(dx);
        const absDy = Math.abs(dy);

        if (Math.max(absDx, absDy) > 30) {
            if (absDx > absDy) {
                move(dx > 0 ? 'RIGHT' : 'LEFT');
            } else {
                move(dy > 0 ? 'DOWN' : 'UP');
            }
        }
        touchStartX = 0; touchStartY = 0;
    };
    boardEl.addEventListener('touchstart', touchStartHandler, { passive: false });
    boardEl.addEventListener('touchend', touchEndHandler, { passive: false });

    rootEl.querySelector('#g-retry').onclick = () => {
        board = Array(16).fill(0);
        score = 0;
        hasWon = false;
        isGameOver = false;
        rootEl.querySelector('#g-overlay').style.display = 'none';
        spawnTile();
        spawnTile();
        renderBoard();
    };

    spawnTile();
    spawnTile();
    renderBoard();
}

export function unmount(rootEl) {
    clearAllTimers();
    if (keydownHandler) window.removeEventListener('keydown', keydownHandler);
    rootEl.innerHTML = '';
}
