import { Injectable, computed, effect, signal } from '@angular/core';

export type ThemeName = 'light' | 'dark';
const THEME_KEY = 'firmadoc-admin-theme';

function systemTheme(): ThemeName {
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function readTheme(): ThemeName | null {
  try {
    const value = localStorage.getItem(THEME_KEY);
    return value === 'dark' || value === 'light' ? value : null;
  } catch {
    return null;
  }
}

/** Tema claro/oscuro: sigue al sistema hasta que la persona elige; la elección queda en este navegador. */
@Injectable({ providedIn: 'root' })
export class Theme {
  readonly current = signal<ThemeName>(readTheme() ?? systemTheme());
  readonly icon = computed(() => (this.current() === 'dark' ? 'pi pi-sun' : 'pi pi-moon'));
  readonly label = computed(() => 'Cambiar a modo ' + (this.current() === 'dark' ? 'claro' : 'oscuro'));

  constructor() {
    effect(() => document.documentElement.setAttribute('data-theme', this.current()));
  }

  toggle(): void {
    const next: ThemeName = this.current() === 'dark' ? 'light' : 'dark';
    this.current.set(next);
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch {
      /* sin almacenamiento: vale para esta página */
    }
  }
}
