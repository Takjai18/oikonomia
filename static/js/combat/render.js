/** @file Apply view updates from combat context */

export function renderAll(views, ctx, options = {}) {
  const snapshot = options.snapshot ?? ctx._lastPollSnapshot ?? null;
  views.hud?.update(ctx, { ...options, snapshot });
  if (!options.hpOnly) {
    views.actions?.update(ctx);
  }
}