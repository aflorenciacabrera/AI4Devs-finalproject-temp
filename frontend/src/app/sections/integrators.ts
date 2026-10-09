import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ConfirmationService } from 'primeng/api';
import { Button } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { TableModule } from 'primeng/table';
import { Textarea } from 'primeng/textarea';
import { AdminApi } from '../core/admin-api';
import { Integrator } from '../core/api-types';

/** Credenciales de un solo uso: viven solo en esta pantalla, nunca en almacenamiento ni en la URL. */
export interface Credentials {
  title: string;
  entries: [string, string][];
}

export function originsList(text: string): string[] {
  return text
    .split(/[\n,]/)
    .map((o) => o.trim())
    .filter(Boolean);
}

@Component({
  selector: 'app-integrators',
  imports: [FormsModule, Button, InputText, Textarea, TableModule],
  templateUrl: './integrators.html',
})
export class Integrators implements OnInit {
  readonly api = inject(AdminApi);
  private readonly confirm = inject(ConfirmationService);

  readonly items = signal<Integrator[]>([]);
  readonly loading = signal(false);
  readonly credentials = signal<Credentials | null>(null);
  readonly name = signal('');
  readonly origins = signal('');
  readonly editing = signal<Integrator | null>(null);
  readonly editingOrigins = signal('');

  ngOnInit(): void {
    void this.load();
  }

  async load(): Promise<void> {
    this.loading.set(true);
    try {
      this.items.set(await this.api.request<Integrator[]>('GET', '/integrators'));
    } catch (error) {
      this.api.fail(error);
    } finally {
      this.loading.set(false);
    }
  }

  async create(): Promise<void> {
    const name = this.name().trim();
    if (!name) return;
    try {
      const r = await this.api.request<Integrator & { api_key: string; webhook_secret: string }>('POST', '/integrators', {
        name,
        allowed_origins: originsList(this.origins()),
      });
      this.name.set('');
      this.origins.set('');
      this.credentials.set({
        title: `Integrador «${r.name}» creado`,
        entries: [
          ['API key', r.api_key],
          ['Secreto de webhook', r.webhook_secret],
        ],
      });
      this.api.ok('Integrador creado.');
      await this.load();
    } catch (error) {
      this.api.fail(error);
    }
  }

  edit(integrator: Integrator): void {
    this.editing.set(integrator);
    this.editingOrigins.set(integrator.allowed_origins.join('\n'));
  }

  cancelEdit(): void {
    this.editing.set(null);
  }

  async saveOrigins(): Promise<void> {
    const target = this.editing();
    if (!target) return;
    try {
      await this.api.request('PATCH', `/integrators/${target.id}`, { allowed_origins: originsList(this.editingOrigins()) });
      this.editing.set(null);
      this.api.ok('Orígenes actualizados.');
      await this.load();
    } catch (error) {
      this.api.fail(error);
    }
  }

  rotateWebhookSecret(i: Integrator): void {
    this.confirm.confirm({
      message: `¿Rotar el secreto de webhook de ${i.name}? El sistema deberá usar el nuevo para validar las notificaciones.`,
      acceptLabel: 'Rotar',
      rejectLabel: 'Cancelar',
      accept: async () => {
        try {
          const r = await this.api.request<{ webhook_secret: string }>('POST', `/integrators/${i.id}/rotate-webhook-secret`);
          this.credentials.set({ title: `Nuevo secreto de webhook de ${i.name}`, entries: [['Secreto de webhook', r.webhook_secret]] });
          await this.load();
        } catch (error) {
          this.api.fail(error);
        }
      },
    });
  }

  rotateApiKey(i: Integrator): void {
    this.confirm.confirm({
      message: `¿Rotar la API key de ${i.name}? La anterior deja de funcionar de inmediato.`,
      acceptLabel: 'Rotar',
      rejectLabel: 'Cancelar',
      acceptButtonStyleClass: 'p-button-danger',
      accept: async () => {
        try {
          const r = await this.api.request<{ api_key: string }>('POST', `/integrators/${i.id}/rotate-api-key`);
          this.credentials.set({ title: `Nueva API key de ${i.name}`, entries: [['API key', r.api_key]] });
          await this.load();
        } catch (error) {
          this.api.fail(error);
        }
      },
    });
  }

  toggle(i: Integrator): void {
    const disabling = i.status === 'active';
    const run = async () => {
      try {
        await this.api.request('POST', `/integrators/${i.id}/${disabling ? 'disable' : 'enable'}`);
        this.api.ok(disabling ? 'Integrador deshabilitado.' : 'Integrador habilitado.');
        await this.load();
      } catch (error) {
        this.api.fail(error);
      }
    };
    if (!disabling) {
      void run();
      return;
    }
    this.confirm.confirm({
      message: `¿Deshabilitar a ${i.name}? No podrá usar la API hasta que lo habilites de nuevo.`,
      acceptLabel: 'Deshabilitar',
      rejectLabel: 'Cancelar',
      acceptButtonStyleClass: 'p-button-danger',
      accept: run,
    });
  }

  async copy(label: string, value: string): Promise<void> {
    try {
      await navigator.clipboard.writeText(value);
      this.api.ok(`${label} copiada.`);
    } catch {
      this.api.fail(new Error('No se pudo copiar: seleccionalo a mano.'));
    }
  }

  hideCredentials(): void {
    this.credentials.set(null);
  }
}
