import { useLayoutEffect } from "react";

import { measureCardHeight } from "./frameHeight";
import type { HostNotifier } from "./hostMessages";

/**
 * Avisa el alto de la pantalla actual. Se mide la tarjeta y no el `.shell`: ese ocupa al menos
 * el alto del iframe (`min-height: 100vh`) y no encogería el diálogo.
 */
export function ReportFrameHeight({ host, screen }: { host: HostNotifier | null; screen: string }) {
  useLayoutEffect(() => {
    if (!host) return;
    const shell = document.querySelector(".shell");
    if (!shell) return;
    let last = 0;
    const publish = () => {
      const height = measureCardHeight();
      if (height === null || height === last) return;
      last = height;
      host.resized(height);
    };
    publish();
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(publish);
    observer.observe(shell);
    for (const node of shell.querySelectorAll(".card, .body, .actions")) observer.observe(node);
    return () => observer.disconnect();
  }, [host, screen]);
  return null;
}
