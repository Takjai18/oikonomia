/** @file Combat HUD avatar URL resolution + load fallback */

export const DEFAULT_PLAYER_AVATAR = '/static/avatars/default.png';
export const DEFAULT_ENEMY_AVATAR = '/static/images/enemies/parasite_shadow.svg';

/**
 * @param {string|null|undefined} raw
 * @param {{ isProtagonist?: boolean, isEnemy?: boolean }} [options]
 */
export function resolveCombatAvatarUrl(raw, { isProtagonist = false, isEnemy = false } = {}) {
  const fallback = isEnemy ? DEFAULT_ENEMY_AVATAR : DEFAULT_PLAYER_AVATAR;
  if (!raw || typeof raw !== 'string') return fallback;
  const trimmed = raw.trim();
  if (!trimmed) return fallback;
  if (trimmed.startsWith('http://') || trimmed.startsWith('https://') || trimmed.startsWith('/')) {
    return trimmed;
  }
  if (isEnemy) {
    if (trimmed.includes('/')) return `/${trimmed.replace(/^\/+/, '')}`;
    if (trimmed.endsWith('.svg')) return `/static/images/enemies/${trimmed}`;
    return `/static/portraits/${trimmed}`;
  }
  if (isProtagonist) return `/static/portraits/${trimmed}`;
  return `/static/avatars/${trimmed}`;
}

/**
 * @param {HTMLImageElement|null|undefined} img
 * @param {string|null|undefined} raw
 * @param {{ isProtagonist?: boolean, isEnemy?: boolean }} [options]
 */
export function bindAvatarImage(img, raw, options = {}) {
  if (!img) return;
  const fallback = options.isEnemy ? DEFAULT_ENEMY_AVATAR : DEFAULT_PLAYER_AVATAR;
  img.onerror = () => {
    img.onerror = null;
    img.src = fallback;
  };
  img.src = resolveCombatAvatarUrl(raw, options);
}