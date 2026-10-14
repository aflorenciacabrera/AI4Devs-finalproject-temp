/** Alto que necesita la tarjeta del widget, en píxeles. `null` si todavía no hay contenido medible. */
export function measureCardHeight(root: ParentNode = document): number | null {
  const card = root.querySelector(".card");
  if (!(card instanceof HTMLElement)) return null;
  const body = card.querySelector(".body");
  const actions = card.querySelector(".actions");
  // scrollHeight del cuerpo incluye lo que queda fuera de la vista; el pie no se comprime.
  const bodyHeight = body instanceof HTMLElement ? body.scrollHeight : 0;
  const actionsHeight = actions instanceof HTMLElement ? actions.offsetHeight : 0;
  const height = Math.ceil(bodyHeight + actionsHeight);
  return height > 0 ? height : null;
}
