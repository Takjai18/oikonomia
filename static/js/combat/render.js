/** @file Apply view updates from combat context */

export function renderAll(views, ctx, options = {}) {
  views.hud?.update(ctx, options);
  views.actions?.update(ctx);
}