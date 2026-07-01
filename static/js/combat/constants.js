/** Shared combat constants (protagonist keys, etc.). */

export const PROTAGONIST_ROUTE_KEYS = Object.freeze(['iggy', 'marah']);

export function isValidProtagonistRouteKey(key) {
  return PROTAGONIST_ROUTE_KEYS.includes(String(key || '').trim().toLowerCase());
}

export const PROTAGONIST_ROUTE_KEY_HINT = PROTAGONIST_ROUTE_KEYS.join(' 或 ');