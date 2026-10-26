import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ConfirmationService } from 'primeng/api';
import { Button } from 'primeng/button';
import { Select } from 'primeng/select';
import { TableModule } from 'primeng/table';
import { AdminApi } from '../core/admin-api';
import { AdminEvent, Page, WebhookDelivery } from '../core/api-types';
import { FmtPipe } from '../core/format';

/** Auditoría: entregas de webhook (con reenvío de las fallidas) y eventos de administración. */
@Component({
  selector: 'app-audit',
  imports: [FormsModule, Button, Select, TableModule, FmtPipe],
  templateUrl: './audit.html',
})
export class Audit implements OnInit {
  readonly api = inject(AdminApi);
  private readonly confirm = inject(ConfirmationService);

  readonly statusOptions = [
    { label: 'Todos', value: '' },
    { label: 'pending', value: 'pending' },
    { label: 'delivered', value: 'delivered' },
    { label: 'failed', value: 'failed' },
  ];
  readonly status = signal('');
  readonly deliveries = signal<WebhookDelivery[]>([]);
  readonly events = signal<AdminEvent[]>([]);
  readonly loading = signal(false);

  ngOnInit(): void {
    void Promise.all([this.loadDeliveries(), this.loadEvents()]);
  }

  async loadDeliveries(): Promise<void> {
    this.loading.set(true);
    try {
      const q = new URLSearchParams({ limit: '100' });
      if (this.status()) q.set('status', this.status());
      this.deliveries.set((await this.api.request<Page<WebhookDelivery>>('GET', '/webhook-deliveries?' + q)).items);
    } catch (error) {
      this.api.fail(error);
    } finally {
      this.loading.set(false);
    }
  }

  async loadEvents(): Promise<void> {
    try {
      this.events.set((await this.api.request<Page<AdminEvent>>('GET', '/events?limit=100')).items);
    } catch (error) {
      this.api.fail(error);
    }
  }

  retry(delivery: WebhookDelivery): void {
    this.confirm.confirm({
      message: '¿Reenviar esta entrega de webhook?',
      acceptLabel: 'Reenviar',
      rejectLabel: 'Cancelar',
      accept: async () => {
        try {
          await this.api.request('POST', `/webhook-deliveries/${delivery.id}/retry`);
          this.api.ok('Entrega reencolada.');
          await Promise.all([this.loadDeliveries(), this.loadEvents()]);
        } catch (error) {
          this.api.fail(error);
        }
      },
    });
  }
}
