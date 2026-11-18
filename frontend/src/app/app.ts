import { NgTemplateOutlet } from '@angular/common';
import { Component, computed, effect, inject, signal } from '@angular/core';
import { MenuItem } from 'primeng/api';
import { Button } from 'primeng/button';
import { ConfirmDialog } from 'primeng/confirmdialog';
import { Drawer } from 'primeng/drawer';
import { Menu } from 'primeng/menu';
import { Toast } from 'primeng/toast';
import { AdminApi } from './core/admin-api';
import { Theme } from './core/theme';
import { Audit } from './sections/audit';
import { Documents } from './sections/documents';
import { Integrators } from './sections/integrators';
import { Login } from './sections/login';
import { Sign } from './sections/sign';
import { Trust } from './sections/trust';

export type Tab = 'sign' | 'documents' | 'audit' | 'integrators' | 'trust';

export const TABS: { id: Tab; label: string; icon: string }[] = [
  { id: 'sign', label: 'Firmar documento', icon: 'pi pi-pen-to-square' },
  { id: 'documents', label: 'Documentos', icon: 'pi pi-file' },
  { id: 'audit', label: 'Auditoría', icon: 'pi pi-list-check' },
  { id: 'integrators', label: 'Integradores', icon: 'pi pi-sitemap' },
  { id: 'trust', label: 'Confianza', icon: 'pi pi-shield' },
];

@Component({
  selector: 'app-root',
  imports: [NgTemplateOutlet, Button, Drawer, Menu, Toast, ConfirmDialog, Login, Sign, Documents, Audit, Integrators, Trust],
  templateUrl: './app.html',
})
export class App {
  readonly api = inject(AdminApi);
  readonly theme = inject(Theme);
  readonly tab = signal<Tab>('sign');
  /** Menú lateral abierto como panel deslizante (pantallas angostas; en las anchas el menú está siempre visible). */
  readonly drawer = signal(false);
  /** Menú lateral de PrimeNG: la sección activa lleva la clase `active`; `automationId` identifica cada ítem. */
  readonly menu = computed<MenuItem[]>(() =>
    TABS.map((t) => ({
      label: t.label,
      icon: t.icon,
      automationId: t.id,
      styleClass: this.tab() === t.id ? 'active' : undefined,
      command: () => this.go(t.id),
    })),
  );

  constructor() {
    effect(() => {
      if (!this.api.loggedIn()) {
        this.tab.set('sign'); // la próxima sesión arranca en «Firmar documento»
        this.drawer.set(false);
      }
    });
    void this.api.resume();
  }

  go(tab: Tab): void {
    this.tab.set(tab);
    this.drawer.set(false);
  }

  logout(): void {
    this.drawer.set(false);
    this.api.logout();
  }
}
