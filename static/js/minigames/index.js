
export const MINIGAMES = {
    color_illusion_trap: () => import('./color_illusion_trap.js'),
    spot_the_difference: () => import('./spot_the_difference.js'),
    bilateral_brain: () => import('./bilateral_brain.js'),
    reverse_contrarian: () => import('./reverse_contrarian.js'),
    sudoku: () => import('./sudoku.js'),
    g2048: () => import('./g2048.js'),
    wordle_custom: () => import('./wordle_custom.js'),
    mapdle_hk: () => import('./mapdle_hk.js'),
    voice_record: () => import('./voice_record.js'),
    memory_match: () => import('./memory_match.js'),
    mastermind: () => import('./mastermind.js'),
    flash_memory: () => import('./flash_memory.js'),
};

let currentUnmount = null;

export async function openMinigame(gameId, rootEl, options) {
    if (currentUnmount) {
        currentUnmount();
        currentUnmount = null;
    }
    
    if (!MINIGAMES[gameId]) throw new Error(`Minigame ${gameId} not found`);
    const module = await MINIGAMES[gameId]();
    module.mount(rootEl, options);
    
    currentUnmount = () => module.unmount(rootEl);
    return currentUnmount;
}
