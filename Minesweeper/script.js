/* ==========================================================
   扫雷 (Minesweeper) — Full Game Engine
   Features: Chord, Gold Bet, Lightning Chain, Combo,
             Death Replay, Nuke, Question Mark Flag,
             Victory Animation
   ========================================================== */

/* ---- Difficulty Presets ---- */
const PRESETS = {
    easy:   { rows: 9,  cols: 9,  mines: 10 },
    medium: { rows: 16, cols: 16, mines: 40 },
    hard:   { rows: 16, cols: 30, mines: 99 },
};

/* ---- DOM references ---- */
const boardEl = document.getElementById('board');
const difficultyEl = document.getElementById('difficulty');
const newGameBtn = document.getElementById('newGameBtn');
const nukeBtn = document.getElementById('nukeBtn');
const nukeCountdown = document.getElementById('nukeCountdown');
const mineCountEl = document.getElementById('mineCount');
const timerEl = document.getElementById('timer');
const messageEl = document.getElementById('message');
const comboDisplay = document.getElementById('comboDisplay');
const shieldIcon = document.getElementById('shieldIcon');
const deathModal = document.getElementById('deathModal');
const deathBody = document.getElementById('deathBody');
const closeDeathBtn = document.getElementById('closeDeathBtn');
const lightningOverlay = document.getElementById('lightningOverlay');

/* ---- Game State ---- */
let grid = [];
let rows, cols, totalMines;
let gameOver = false;
let firstClick = true;
let flagCount = 0;
let timerInterval = null;
let seconds = 0;

// Shield (金币护盾)
let hasShield = false;

// Combo
let comboCount = 0;
let comboTimer = null;

// Nuke
let nukeAvailable = 10;

// 金币格位置
let goldCell = null;

// 最后一次踩雷的格子
let lastDeathCell = null;

/* ==========================================================
   Cell Object
   ========================================================== */
function createCell(r, c) {
    return {
        row: r, col: c,
        mine: false,
        gold: false,
        revealed: false,
        flagged: false,
        questionMark: false,
        adjacentMines: 0,
        el: null,
    };
}

/* ==========================================================
   Board Setup
   ========================================================== */
function initBoard() {
    cleanupConfetti();
    const preset = PRESETS[difficultyEl.value];
    rows = preset.rows;
    cols = preset.cols;
    totalMines = preset.mines;
    hasShield = false;
    comboCount = 0;
    nukeAvailable = 10;
    goldCell = null;
    lastDeathCell = null;
    clearTimeout(comboTimer);
    comboDisplay.textContent = '';
    comboDisplay.classList.remove('visible', 'fire-1', 'fire-2', 'fire-3');
    shieldIcon.textContent = '';
    nukeCountdown.textContent = '';

    grid = [];
    for (let r = 0; r < rows; r++) {
        grid[r] = [];
        for (let c = 0; c < cols; c++) {
            grid[r][c] = createCell(r, c);
        }
    }

    boardEl.style.gridTemplateColumns = `repeat(${cols}, 1fr)`;
    boardEl.innerHTML = '';
    messageEl.textContent = '';

    for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
            const cell = grid[r][c];
            const div = document.createElement('div');
            div.className = 'cell hidden';
            div.dataset.r = r;
            div.dataset.c = c;
            div.addEventListener('click', () => handleClick(r, c));
            div.addEventListener('contextmenu', (e) => { e.preventDefault(); handleRightClick(r, c); });
            boardEl.appendChild(div);
            cell.el = div;
        }
    }

    gameOver = false;
    firstClick = true;
    flagCount = 0;
    seconds = 0;
    clearInterval(timerInterval);
    timerInterval = null;
    timerEl.textContent = '⏱ 000';
    updateMineDisplay();
    updateNukeButton();
}

/* ---- Place mines (after first click) ---- */
function placeMines(safeR, safeC) {
    const safeSet = new Set();
    for (let dr = -1; dr <= 1; dr++) {
        for (let dc = -1; dc <= 1; dc++) {
            const nr = safeR + dr, nc = safeC + dc;
            if (nr >= 0 && nr < rows && nc >= 0 && nc < cols) safeSet.add(`${nr},${nc}`);
        }
    }

    let placed = 0;
    while (placed < totalMines) {
        const r = Math.floor(Math.random() * rows);
        const c = Math.floor(Math.random() * cols);
        if (!grid[r][c].mine && !safeSet.has(`${r},${c}`)) {
            grid[r][c].mine = true;
            placed++;
        }
    }
    if (placed < totalMines) {
        while (placed < totalMines) {
            const r = Math.floor(Math.random() * rows);
            const c = Math.floor(Math.random() * cols);
            if (!grid[r][c].mine) { grid[r][c].mine = true; placed++; }
        }
    }

    for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
            if (grid[r][c].mine) continue;
            let count = 0;
            forEachNeighbor(r, c, (nr, nc) => { if (grid[nr][nc].mine) count++; });
            grid[r][c].adjacentMines = count;
        }
    }
}

function placeGold() {
    const candidates = [];
    for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
            if (!grid[r][c].mine) candidates.push(grid[r][c]);
        }
    }
    if (candidates.length > 0) {
        const pick = candidates[Math.floor(Math.random() * candidates.length)];
        pick.gold = true;
        goldCell = pick;
    }
}

function forEachNeighbor(r, c, fn) {
    for (let dr = -1; dr <= 1; dr++) {
        for (let dc = -1; dc <= 1; dc++) {
            if (dr === 0 && dc === 0) continue;
            const nr = r + dr, nc = c + dc;
            if (nr >= 0 && nr < rows && nc >= 0 && nc < cols) fn(nr, nc);
        }
    }
}

/* ==========================================================
   Display Helpers
   ========================================================== */
function updateMineDisplay() {
    const remaining = totalMines - flagCount;
    mineCountEl.textContent = `💣 ${remaining}`;
}

function updateNukeButton() {
    if (nukeAvailable > 0) {
        nukeBtn.disabled = false;
        nukeCountdown.textContent = `×${nukeAvailable}`;
    } else {
        nukeBtn.disabled = true;
        nukeCountdown.textContent = '';
    }
}

function renderCell(cell) {
    const { el } = cell;
    if (cell.revealed) {
        el.classList.remove('hidden', 'flagged', 'question-mark');
        el.classList.add('revealed');
        if (cell.mine) {
            el.textContent = '💣';
        } else if (cell.gold) {
            el.textContent = '🪙';
            el.style.background = '#3a3a1a';
        } else if (cell.adjacentMines > 0) {
            el.textContent = cell.adjacentMines;
            el.classList.add(`n${cell.adjacentMines}`);
        } else {
            el.textContent = '';
        }
    } else if (cell.flagged) {
        el.classList.add('flagged');
        el.classList.remove('revealed', 'question-mark');
        el.textContent = '🚩';
    } else if (cell.questionMark) {
        el.classList.add('question-mark');
        el.classList.remove('revealed', 'flagged');
        el.textContent = '❓';
    } else {
        el.classList.remove('revealed', 'flagged', 'question-mark', 'mine-exploded', 'nuked');
        el.classList.add('hidden');
        el.style.background = '';
        el.textContent = '';
        for (let i = 1; i <= 8; i++) el.classList.remove(`n${i}`);
    }
}

/* ==========================================================
   Game Actions
   ========================================================== */
function handleClick(r, c) {
    if (gameOver) return;
    const cell = grid[r][c];

    if (cell.revealed && cell.adjacentMines > 0) {
        chordClick(cell);
        if (checkWin()) endGame(true);
        return;
    }
    if (cell.revealed || cell.flagged || cell.questionMark) return;

    if (firstClick) {
        placeMines(r, c);
        placeGold();
        firstClick = false;
        startTimer();
    }

    reveal(cell);
    if (checkWin()) endGame(true);
}

function chordClick(cell) {
    let flagsAround = 0;
    forEachNeighbor(cell.row, cell.col, (nr, nc) => {
        if (grid[nr][nc].flagged) flagsAround++;
    });
    if (flagsAround !== cell.adjacentMines) return;

    forEachNeighbor(cell.row, cell.col, (nr, nc) => {
        const neighbor = grid[nr][nc];
        if (neighbor.revealed || neighbor.flagged) return;
        reveal(neighbor);
    });
}

function handleRightClick(r, c) {
    if (gameOver) return;
    const cell = grid[r][c];
    if (cell.revealed) return;

    if (!cell.flagged && !cell.questionMark) {
        cell.flagged = true;
        cell.questionMark = false;
        flagCount++;
    } else if (cell.flagged) {
        cell.flagged = false;
        cell.questionMark = true;
        flagCount--;
    } else {
        cell.questionMark = false;
    }
    renderCell(cell);
    updateMineDisplay();
}

function reveal(cell) {
    if (cell.revealed || cell.flagged || cell.questionMark) return;

    cell.revealed = true;
    renderCell(cell);

    if (cell.gold) {
        hasShield = true;
        shieldIcon.textContent = '\ud83d\udee1\ufe0f \u62a4\u76fe';
        messageEl.textContent = '\ud83e\udd99 \u627e\u5230\u91d1\u5e01\uff01\u83b7\u5f97\u4e00\u6b21\u514d\u96f7\u62a4\u76fe\uff01';
        setTimeout(function() { if (!gameOver) messageEl.textContent = ''; }, 2000);
    }

    if (cell.mine) {
        if (hasShield) {
            hasShield = false;
            shieldIcon.textContent = '';
            cell.revealed = false;
            cell.el.classList.add('mine-exploded');
            cell.el.textContent = '\ud83d\udca5';
            setTimeout(function() {
                cell.revealed = true;
                cell.el.classList.remove('mine-exploded');
                renderCell(cell);
                cell.el.classList.add('revealed');
                cell.el.textContent = '\ud83d\udca3';
            }, 400);
            messageEl.textContent = '\ud83d\udee1\ufe0f \u62a4\u76fe\u89e6\u53d1\uff01\u66ff\u4f60\u6321\u4e86\u4e00\u6b21\uff01';
            setTimeout(function() { if (!gameOver) messageEl.textContent = ''; }, 1500);
            revealNeighborsIfBlank(cell);
            return;
        }

        cell.el.classList.add('mine-exploded');
        lastDeathCell = cell;
        endGame(false);
        return;
    }

    comboIncrement();

    if (cell.adjacentMines === 0) {
        triggerLightning(cell.row, cell.col);
        document.querySelector('#app').classList.add('shake');
        setTimeout(function() { document.querySelector('#app').classList.remove('shake'); }, 150);
    }

    if (cell.adjacentMines === 0) {
        forEachNeighbor(cell.row, cell.col, function(nr, nc) {
            reveal(grid[nr][nc]);
        });
    }
}
function revealNeighborsIfBlank(cell) {
    if (cell.adjacentMines === 0) {
        forEachNeighbor(cell.row, cell.col, (nr, nc) => {
            reveal(grid[nr][nc]);
        });
    }
}

/* ==========================================================
   Combo System
   ========================================================== */
function comboIncrement() {
    comboCount++;
    clearTimeout(comboTimer);
    comboDisplay.textContent = `🔥 ${comboCount} COMBO`;
    comboDisplay.classList.add('visible');
    if (comboCount >= 15) comboDisplay.classList.add('fire-3');
    else if (comboCount >= 8) comboDisplay.classList.add('fire-2');
    else if (comboCount >= 4) comboDisplay.classList.add('fire-1');

    comboTimer = setTimeout(() => {
        comboCount = 0;
        comboDisplay.textContent = '';
        comboDisplay.classList.remove('visible', 'fire-1', 'fire-2', 'fire-3');
    }, 2000);
}

/* ==========================================================
   Lightning Effect
   ========================================================== */
function triggerLightning(r, c) {
    lightningOverlay.classList.remove('flash');
    void lightningOverlay.offsetWidth;
    lightningOverlay.classList.add('flash');
    setTimeout(() => lightningOverlay.classList.remove('flash'), 300);
}

/* ==========================================================
   Nuke
   ========================================================== */
function useNuke() {
    if (gameOver || nukeAvailable <= 0) return;
    if (firstClick) return;

    nukeAvailable--;
    updateNukeButton();

    const targets = new Set();
    for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
            const cell = grid[r][c];
            if (cell.revealed && !cell.mine) {
                forEachNeighbor(r, c, (nr, nc) => {
                    const n = grid[nr][nc];
                    if (!n.revealed && !n.flagged) targets.add(nr + ',' + nc);
                });
            }
        }
    }

    if (targets.size === 0) {
        messageEl.textContent = '\u2622\ufe0f \u5468\u56f4\u6ca1\u6709\u53ef\u6e05\u9664\u7684\u683c\u5b50';
        setTimeout(function() { if (!gameOver) messageEl.textContent = ''; }, 1500);
        nukeAvailable++;
        updateNukeButton();
        return;
    }

    const targetArr = Array.from(targets).map(function(s) { return s.split(',').map(Number); });
    for (var i = 0; i < targetArr.length; i++) {
        var r = targetArr[i][0], c = targetArr[i][1];
        grid[r][c].el.classList.add('nuked');
    }

    messageEl.textContent = '\u2622\ufe0f \u6838\u5f39\u53d1\u5c04\uff01';
    document.querySelector('#app').classList.add('shake');
    setTimeout(function() { document.querySelector('#app').classList.remove('shake'); }, 200);

    setTimeout(function() {
        for (var i = 0; i < targetArr.length; i++) {
            var r = targetArr[i][0], c = targetArr[i][1];
            var cell = grid[r][c];
            cell.el.classList.remove('nuked');
            if (cell.mine) {
                cell.revealed = true;
                renderCell(cell);
                cell.el.textContent = '\ud83d\udca5';
                setTimeout(function() {
                    cell.el.style.background = '#1e1e32';
                    cell.el.textContent = '';
                }, 300);
            } else {
                cell.revealed = true;
                renderCell(cell);
            }
        }
        messageEl.textContent = '\u2622\ufe0f \u6838\u5f39\u6e05\u9664\u5b8c\u6210\uff01';
        setTimeout(function() { if (!gameOver) messageEl.textContent = ''; }, 1500);

        if (checkWin()) endGame(true);
    }, 500);
}
function endGame(won) {
    gameOver = true;
    clearInterval(timerInterval);
    clearTimeout(comboTimer);
    comboDisplay.classList.remove('visible', 'fire-1', 'fire-2', 'fire-3');

    if (won) {
        messageEl.textContent = '🎉 你赢了！';
        for (let r = 0; r < rows; r++) {
            for (let c = 0; c < cols; c++) {
                const cell = grid[r][c];
                if (cell.mine && !cell.flagged) {
                    cell.flagged = true;
                    flagCount++;
                    renderCell(cell);
                }
            }
        }
        updateMineDisplay();
        setTimeout(showVictoryAnimation, 300);
    } else {
        messageEl.textContent = '💥 踩雷了！';
        revealAllMines();
        setTimeout(showDeathAnalysis, 400);
    }
}

function revealAllMines() {
    for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
            const cell = grid[r][c];
            if (cell.mine && !cell.revealed) {
                cell.revealed = true;
                renderCell(cell);
            }
        }
    }
}

function checkWin() {
    for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
            const cell = grid[r][c];
            if (!cell.mine && !cell.revealed) return false;
        }
    }
    return true;
}

/* ==========================================================
   Victory Animation
   ========================================================== */
function showVictoryAnimation() {
    const overlay = document.getElementById('victoryOverlay');
    const stars = overlay.querySelector('.stars');
    const winTime = document.getElementById('winTime');
    const winDifficulty = document.getElementById('winDifficulty');
    const winCombo = document.getElementById('winCombo');
    const playAgainBtn = document.getElementById('playAgainBtn');

    winTime.textContent = seconds;
    const diffMap = { easy: '初级', medium: '中级', hard: '高级' };
    winDifficulty.textContent = diffMap[difficultyEl.value] || '未知';
    winCombo.textContent = comboCount;

    let starCount = 1;
    if (seconds < 30) starCount = 3;
    else if (seconds < 60) starCount = 2;
    stars.textContent = '⭐'.repeat(starCount);

    const quotes = [
        '「高手，这是高手！」',
        '「扫雷王的称号属于你」',
        '「这速度，闪电侠都服气」',
        '「恭喜通关，矿工退休了」',
        '「雷区已清理，村民安全了」',
        '「脑子：我转完了，手：我跟上了」',
        '「没有一颗雷能逃过你的眼睛」',
    ];
    overlay.querySelector('.quote').textContent = quotes[Math.floor(Math.random() * quotes.length)];

    boardEl.classList.add('victory-glow');

    // 单元格涟漪波浪（从中心向外扩散）
    const centerR = Math.floor(rows / 2);
    const centerC = Math.floor(cols / 2);
    const allCells = boardEl.querySelectorAll('.cell');
    const cellsWithDist = [];
    allCells.forEach(el => {
        const r = parseInt(el.dataset.r);
        const c = parseInt(el.dataset.c);
        const dist = Math.abs(r - centerR) + Math.abs(c - centerC);
        cellsWithDist.push({ el, dist });
    });
    cellsWithDist.sort((a, b) => a.dist - b.dist);
    cellsWithDist.forEach(({ el, dist }, i) => {
        setTimeout(() => {
            el.classList.add('victory-ripple');
            setTimeout(() => el.classList.remove('victory-ripple'), 600);
        }, i * 20 + 100);
    });

    // 烟花 + 星芒
    spawnFireworks();
    spawnSparkles();

    // 先显示弹窗，再启动持续撒花
    setTimeout(() => {
        overlay.classList.add('show');
        spawnEpicConfetti();
    }, 800);

    playAgainBtn.onclick = () => {
        overlay.classList.remove('show');
        boardEl.classList.remove('victory-glow');
        initBoard();
    };
    overlay.onclick = (e) => {
        if (e.target === overlay) {
            overlay.classList.remove('show');
            boardEl.classList.remove('victory-glow');
            initBoard();
        }
    };
}
function spawnFireworks() {
    // 多波次烟花
    const colors = ['#ff6b6b', '#ffd93d', '#6bcb77', '#4d96ff', '#ff6bff', '#ff9f43', '#00d2d3', '#fff', '#ff0080', '#00ff88'];

    for (let wave = 0; wave < 5; wave++) {
        setTimeout(function() {
            // 每波 3-5 个烟花
            const count = 3 + Math.floor(Math.random() * 3);
            for (let i = 0; i < count; i++) {
                const cx = 15 + Math.random() * 70;
                const cy = 10 + Math.random() * 40;
                const color1 = colors[Math.floor(Math.random() * colors.length)];
                const color2 = colors[Math.floor(Math.random() * colors.length)];
                const particleCount = 30 + Math.floor(Math.random() * 30);

                for (let j = 0; j < particleCount; j++) {
                    const el = document.createElement('div');
                    el.className = 'fw-particle';
                    const angle = (j / particleCount) * 360;
                    const speed = 60 + Math.random() * 80;
                    const tx = Math.cos(angle * Math.PI / 180) * speed;
                    const ty = Math.sin(angle * Math.PI / 180) * speed;
                    const size = 2 + Math.random() * 4;
                    el.style.cssText = 
                        'left: ' + cx + 'vw;' +
                        'top: ' + cy + 'vh;' +
                        'width: ' + size + 'px;' +
                        'height: ' + size + 'px;' +
                        '--fw-scale: 0;' +
                        '--fw-duration: ' + (0.8 + Math.random() * 0.6) + 's;' +
                        'background: ' + (j % 2 === 0 ? color1 : color2) + ';' +
                        'box-shadow: 0 0 ' + (size * 2) + 'px ' + color1 + ';' +
                        'transform: translate(' + tx + 'px, ' + ty + 'px);';
                    document.body.appendChild(el);
                    setTimeout(function() { if (el.parentNode) el.remove(); }, 2000);
                }
            }
        }, wave * 600);
    }
}
function spawnEpicConfetti() {
    const shapes = ['ribbon', 'circle', 'square'];
    const colors = ['#ff6b6b', '#ffd93d', '#6bcb77', '#4d96ff', '#ff6bff', '#ff9f43', '#00d2d3', '#ff0080', '#ffaa00', '#00ff88', '#ff4500', '#7b68ee'];

    // 持续撒花，每 300ms 生成一小波，直到棋盘被重置
    if (window._confettiStopped) return;
    window._confettiStopped = false;

    function spawnWave() {
        if (window._confettiStopped) { cleanupConfetti(); return; }

        for (let i = 0; i < 20; i++) {
            const el = document.createElement('div');
            const shape = shapes[Math.floor(Math.random() * shapes.length)];
            el.className = 'confetti-piece ' + shape;
            const color = colors[Math.floor(Math.random() * colors.length)];
            const size = shape === 'ribbon' ? 40 + Math.random() * 30 : 6 + Math.random() * 10;
            const rot = Math.random() * 720;
            const left = Math.random() * 100;
            const topOffset = -20 + Math.random() * 20;

            if (shape === 'ribbon') {
                el.style.cssText =
                    'left: ' + left + 'vw; top: ' + topOffset + 'px;' +
                    'width: ' + size + 'px; height: ' + (6 + Math.random() * 4) + 'px;' +
                    'background: ' + color + ';' +
                    '--cr: ' + rot + 'deg; --cs: ' + (0.5 + Math.random()) + ';' +
                    'animation-duration: ' + (3 + Math.random() * 3) + 's;' +
                    'animation-delay: ' + (Math.random() * 0.3) + 's;' +
                    'opacity: ' + (0.7 + Math.random() * 0.3) + ';' +
                    'box-shadow: 0 0 4px ' + color + '44;';
            } else {
                el.style.cssText =
                    'left: ' + left + 'vw; top: ' + topOffset + 'px;' +
                    'width: ' + size + 'px; height: ' + size + 'px;' +
                    'background: ' + color + ';' +
                    '--cr: ' + rot + 'deg; --cs: ' + (0.5 + Math.random()) + ';' +
                    'animation-duration: ' + (3 + Math.random() * 4) + 's;' +
                    'animation-delay: ' + (Math.random() * 0.5) + 's;' +
                    'opacity: ' + (0.8 + Math.random() * 0.2) + ';' +
                    'box-shadow: 0 0 ' + size + 'px ' + color + '33;';
            }
            document.body.appendChild(el);
            setTimeout(function() { if (el.parentNode) el.remove(); }, 8000);
        }

        window._confettiTimer = setTimeout(spawnWave, 300);
    }

    // 先撒一大波
    for (let i = 0; i < 60; i++) {
        const el = document.createElement('div');
        const shape = shapes[Math.floor(Math.random() * shapes.length)];
        el.className = 'confetti-piece ' + shape;
        const color = colors[Math.floor(Math.random() * colors.length)];
        const size = shape === 'ribbon' ? 40 + Math.random() * 30 : 6 + Math.random() * 10;
        const rot = Math.random() * 720;
        const left = Math.random() * 100;
        const topOffset = -20 + Math.random() * 20;

        if (shape === 'ribbon') {
            el.style.cssText =
                'left: ' + left + 'vw; top: ' + topOffset + 'px;' +
                'width: ' + size + 'px; height: ' + (6 + Math.random() * 4) + 'px;' +
                'background: ' + color + ';' +
                '--cr: ' + rot + 'deg; --cs: ' + (0.5 + Math.random()) + ';' +
                'animation-duration: ' + (3 + Math.random() * 4) + 's;' +
                'animation-delay: ' + (Math.random() * 0.5) + 's;' +
                'opacity: ' + (0.7 + Math.random() * 0.3) + ';' +
                'box-shadow: 0 0 4px ' + color + '44;';
        } else {
            el.style.cssText =
                'left: ' + left + 'vw; top: ' + topOffset + 'px;' +
                'width: ' + size + 'px; height: ' + size + 'px;' +
                'background: ' + color + ';' +
                '--cr: ' + rot + 'deg; --cs: ' + (0.5 + Math.random()) + ';' +
                'animation-duration: ' + (3 + Math.random() * 4) + 's;' +
                'animation-delay: ' + (Math.random() * 0.5) + 's;' +
                'opacity: ' + (0.8 + Math.random() * 0.2) + ';' +
                'box-shadow: 0 0 ' + size + 'px ' + color + '33;';
        }
        document.body.appendChild(el);
        setTimeout(function() { if (el.parentNode) el.remove(); }, 8000);
    }

    // 开始持续撒花
    window._confettiTimer = setTimeout(spawnWave, 500);
}
function cleanupConfetti() {
    window._confettiStopped = true;
    clearTimeout(window._confettiTimer);
    document.querySelectorAll('.confetti-piece').forEach(el => el.remove());
}
function spawnSparkles() {
    const count = 30;
    for (let i = 0; i < count; i++) {
        const el = document.createElement('div');
        el.className = 'sparkle-dot';
        const angle = (i / count) * 360;
        const radius = 180 + Math.random() * 60;
        const cx = 50; // center of screen in vw
        const cy = 45; // center of screen in vh
        const x = cx + Math.cos(angle * Math.PI / 180) * radius / 10;
        const y = cy + Math.sin(angle * Math.PI / 180) * radius / 10;
        const size = 6 + Math.random() * 8;
        el.style.cssText = `
            left: ${x}vw;
            top: ${y}vh;
            width: ${size}px;
            height: ${size}px;
            animation-delay: ${Math.random() * 0.5}s;
            animation-duration: ${1 + Math.random() * 1}s;
            opacity: ${0.6 + Math.random() * 0.4};
        `;
        document.body.appendChild(el);
        setTimeout(() => el.remove(), 3000);
    }
}
/* ==========================================================
   Death Analysis
   ========================================================== */
function showDeathAnalysis() {
    if (!lastDeathCell) return;
    const d = lastDeathCell;
    let flagsAround = 0;
    let minesAround = 0;
    forEachNeighbor(d.row, d.col, (nr, nc) => {
        const n = grid[nr][nc];
        if (n.flagged) flagsAround++;
        if (n.mine) minesAround++;
    });

    deathBody.innerHTML = `
        <p>💥 你踩到了 <span class="highlight">(${d.row+1}, ${d.col+1})</span> 位置的雷</p>
        <p>🔢 该格周围共有 <span class="highlight">${minesAround}</span> 颗雷</p>
        <p>🚩 你标记了 <span class="highlight">${flagsAround}</span> 面旗子</p>
        <p>${flagsAround < minesAround ? '😅 还差 ' + (minesAround - flagsAround) + ' 面旗子没标' : '✅ 旗子标够了，但你点到了雷相邻的格子'}</p>
        <p>⏱ 用时 <span class="highlight">${seconds}</span> 秒</p>
        <p style="margin-top:8px;font-size:0.85rem;color:#888;">下次注意观察数字哦！</p>
    `;
    deathModal.classList.add('show');
}

closeDeathBtn.addEventListener('click', () => {
    deathModal.classList.remove('show');
});

/* ==========================================================
   Timer
   ========================================================== */
function startTimer() {
    seconds = 0;
    timerEl.textContent = '⏱ 000';
    clearInterval(timerInterval);
    timerInterval = setInterval(() => {
        seconds++;
        timerEl.textContent = `⏱ ${String(seconds).padStart(3, '0')}`;
    }, 1000);
}

/* ==========================================================
   Event Listeners
   ========================================================== */
newGameBtn.addEventListener('click', initBoard);
difficultyEl.addEventListener('change', initBoard);
nukeBtn.addEventListener('click', useNuke);

/* ==========================================================
   Start!
   ========================================================== */
initBoard();








