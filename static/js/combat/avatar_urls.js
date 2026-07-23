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
    if (trimmed.startsWith('images/enemies/') || trimmed.startsWith('static/images/enemies/')) {
      return `/${trimmed.replace(/^\/+/, '').replace(/^static\//, '')}`;
    }
    if (trimmed.includes('/')) return `/${trimmed.replace(/^\/+/, '')}`;
    // svg / png / jpg / webp all live under enemies/
    const base = trimmed.split('/').pop() || trimmed;
    return `/static/images/enemies/${encodeURIComponent(base).replace(/%2F/gi, '/')}`;
  }
  if (isProtagonist) return `/static/portraits/${trimmed}`;
  // Legacy renames / png→jpg (keep in sync with utils/helpers.py)
  const AVATAR_ALIASES = {
    'lok sum.jpg': 'loksum.jpg',
    'lok tin.jpg': 'lokting.jpg',
    'lok ting.jpg': 'lokting.jpg',
    'lok ying.jpg': 'lokying.jpg',
    'lok yiu.jpg': 'lokyiu.jpg',
    'sumwing 2.jpg': 'sumwing2.jpg',
    'pak yat.jpg': 'ethan.jpg',
    'fung.png': 'fung.jpg',
    'siujai.png': 'siujai.jpg',
    'sumwing.png': 'sumwing.jpg',
    'tak.png': 'tak.jpg',
    'ted.png': 'ted.jpg',
  };
  let path = trimmed;
  const segs = path.split('/');
  const base = segs[segs.length - 1] || '';
  const mapped = AVATAR_ALIASES[base] || AVATAR_ALIASES[base.toLowerCase()];
  if (mapped) {
    segs[segs.length - 1] = mapped;
    path = segs.join('/');
  } else if (/\.png$/i.test(base) && path.includes('new avatars')) {
    segs[segs.length - 1] = base.replace(/\.png$/i, '.jpg');
    path = segs.join('/');
  }
  if (!path.includes('/')) {
    path = `new avatars for players/${path}`;
  }
  // Encode segments so "new avatars for players/Mike.jpg" works in URLs
  const encoded = path.split('/').map(encodeURIComponent).join('/');
  return `/static/avatars/${encoded}`;
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