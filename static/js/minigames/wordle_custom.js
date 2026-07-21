
let timeoutIds = [];

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
    // 註：此 answers 僅為 demo 預設。生產環境應由 options.config 注入營會專屬短詞表
    const config = { 
        answers: ["界線", "神智", "韌性", "裂縫", "Oikonomia", "Iggy", "Judas"], 
        maxGuesses: 6,
        ...options.config 
    };
    
    let hash = 0;
    if (options.taskId) {
        for (let i = 0; i < options.taskId.length; i++) {
            hash = options.taskId.charCodeAt(i) + ((hash << 5) - hash);
        }
    }
    const targetWord = config.answers[Math.abs(hash) % config.answers.length].toUpperCase();
    const wordLength = targetWord.length;
    
    let guesses = [];
    let isGameOver = false;

    rootEl.innerHTML = `
        <style>
            .wd-container { font-family: sans-serif; max-width: 400px; margin: 0 auto; padding: 15px; text-align: center; }
            .wd-header { font-size: 20px; font-weight: bold; margin-bottom: 20px; color: #2c3e50; }
            .wd-grid { display: grid; gap: 5px; margin-bottom: 20px; justify-content: center; }
            .wd-row { display: grid; gap: 5px; grid-template-columns: repeat(${wordLength}, 1fr); }
            .wd-cell { width: 45px; height: 45px; border: 2px solid #bdc3c7; display: flex; justify-content: center; align-items: center; font-size: 24px; font-weight: bold; text-transform: uppercase; color: #333; }
            .wd-cell.correct { background: #6aaa64; color: white; border-color: #6aaa64; }
            .wd-cell.present { background: #c9b458; color: white; border-color: #c9b458; }
            .wd-cell.absent { background: #787c7e; color: white; border-color: #787c7e; }
            .wd-input-area { display: flex; gap: 10px; justify-content: center; margin-bottom: 20px; }
            .wd-input { flex: 1; padding: 12px; font-size: 18px; border: 2px solid #bdc3c7; border-radius: 8px; text-transform: uppercase; max-width: 200px; }
            .wd-btn { padding: 12px 20px; font-size: 18px; background: #3498db; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; }
            .wd-btn:disabled { background: #95a5a6; cursor: not-allowed; }
            .wd-toast { position: fixed; top: 20px; left: 50%; transform: translateX(-50%); background: rgba(0,0,0,0.8); color: white; padding: 10px 20px; border-radius: 20px; display: none; z-index: 100; pointer-events: none; }
        </style>
        <div class="wd-container">
            <div class="wd-header">密碼破解 (${wordLength} 個字元)</div>
            <div class="wd-grid" id="wd-grid"></div>
            <div class="wd-input-area" id="wd-controls">
                <input type="text" class="wd-input" id="wd-input" maxlength="${wordLength}" placeholder="輸入密碼..." autocomplete="off">
                <button class="wd-btn" id="wd-submit">猜測</button>
            </div>
            <div id="wd-toast" class="wd-toast"></div>
        </div>
    `;

    const gridEl = rootEl.querySelector('#wd-grid');
    const inputEl = rootEl.querySelector('#wd-input');
    const submitBtn = rootEl.querySelector('#wd-submit');

    const showToast = (msg, duration=2000) => {
        const t = rootEl.querySelector('#wd-toast');
        if(!t) return;
        t.textContent = msg;
        t.style.display = 'block';
        registerTimeout(() => { if(t) t.style.display = 'none'; }, duration);
    };

    const renderGrid = () => {
        gridEl.innerHTML = '';
        for (let i = 0; i < config.maxGuesses; i++) {
            const rowEl = document.createElement('div');
            rowEl.className = 'wd-row';
            
            const guess = guesses[i] || "";
            let statuses = Array(wordLength).fill('');

            if (guess) {
                let targetChars = targetWord.split('');
                let guessChars = guess.split('');
                
                for (let j = 0; j < wordLength; j++) {
                    if (guessChars[j] === targetChars[j]) {
                        statuses[j] = 'correct';
                        targetChars[j] = null; 
                        guessChars[j] = null;
                    }
                }
                for (let j = 0; j < wordLength; j++) {
                    if (guessChars[j] && targetChars.includes(guessChars[j])) {
                        statuses[j] = 'present';
                        targetChars[targetChars.indexOf(guessChars[j])] = null;
                    } else if (guessChars[j]) {
                        statuses[j] = 'absent';
                    }
                }
            }

            for (let j = 0; j < wordLength; j++) {
                const cell = document.createElement('div');
                cell.className = `wd-cell ${statuses[j]}`;
                cell.textContent = guess[j] || "";
                rowEl.appendChild(cell);
            }
            gridEl.appendChild(rowEl);
        }
    };

    const handleGuess = () => {
        if (isGameOver) return;
        const val = inputEl.value.trim().toUpperCase();
        
        if (val.length !== wordLength) {
            showToast(`請輸入 ${wordLength} 個字元`);
            return;
        }

        guesses.push(val);
        inputEl.value = '';
        renderGrid();

        if (val === targetWord) {
            isGameOver = true;
            inputEl.disabled = true;
            submitBtn.disabled = true;
            showToast("✅ 密碼正確！", 2000);
            registerTimeout(() => {
                if (options.onComplete) options.onComplete({ taskId: options.taskId, gameId: 'wordle_custom', result: 'win', guesses: guesses.length });
            }, 1500);
        } else if (guesses.length >= config.maxGuesses) {
            isGameOver = true;
            showToast(`任務失敗，正確密碼是: ${targetWord}`, 3000);
            submitBtn.textContent = "重試";
            submitBtn.onclick = () => {
                clearAllTimers();
                mount(rootEl, options);
            };
        }
    };

    submitBtn.onclick = handleGuess;
    inputEl.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleGuess();
    });

    renderGrid();
}

export function unmount(rootEl) {
    clearAllTimers();
    rootEl.innerHTML = '';
}
