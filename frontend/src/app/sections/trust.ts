import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ConfirmationService } from 'primeng/api';
import { Button } from 'primeng/button';
import { TableModule } from 'primeng/table';
import { Textarea } from 'primeng/textarea';
import { AdminApi } from '../core/admin-api';
import { LocalCertificate, TrustAnchor } from '../core/api-types';
import { FmtPipe } from '../core/format';

/** Confianza: anclas (agregar y quitar) y certificado propio del proveedor local (rotar). */
@Component({
  selector: 'app-trust',
  imports: [FormsModule, Button, Textarea, TableModule, FmtPipe],
  templateUrl: './trust.html',
})
export class Trust implements OnInit {
  readonly api = inject(AdminApi);
  private readonly confirm = inject(ConfirmationService);

  readonly anchors = signal<TrustAnchor[]>([]);
  readonly certificate = signal<LocalCertificate | null>(null);
  readonly pem = signal('');
  readonly loading = signal(false);

  ngOnInit(): void {
    void Promise.all([this.loadAnchors(), this.loadCertificate()]);
  }

  async loadAnchors(): Promise<void> {
    this.loading.set(true);
    try {
      this.anchors.set(await this.api.request<TrustAnchor[]>('GET', '/trust-anchors'));
    } catch (error) {
      this.api.fail(error);
    } finally {
      this.loading.set(false);
    }
  }

  async loadCertificate(): Promise<void> {
    try {
      this.certificate.set(await this.api.request<LocalCertificate>('GET', '/local-certificate'));
    } catch (error) {
      this.api.fail(error);
    }
  }

  async addAnchor(): Promise<void> {
    if (!this.pem().trim()) return;
    try {
      await this.api.request('POST', '/trust-anchors', { certificate_pem: this.pem() });
      this.pem.set('');
      this.api.ok('Ancla agregada.');
      await this.loadAnchors();
    } catch (error) {
      this.api.fail(error);
    }
  }

  removeAnchor(anchor: TrustAnchor): void {
    this.confirm.confirm({
      message: `¿Quitar esta ancla de confianza?\n${anchor.subject}`,
      acceptLabel: 'Quitar',
      rejectLabel: 'Cancelar',
      acceptButtonStyleClass: 'p-button-danger',
      accept: async () => {
        try {
          await this.api.request('DELETE', `/trust-anchors/${anchor.fingerprint}`);
          this.api.ok('Ancla quitada.');
          await this.loadAnchors();
        } catch (error) {
          this.api.fail(error);
        }
      },
    });
  }

  rotate(): void {
    this.confirm.confirm({
      message: '¿Rotar el certificado propio? La clave vigente se destruye; las firmas anteriores siguen verificándose.',
      acceptLabel: 'Rotar',
      rejectLabel: 'Cancelar',
      acceptButtonStyleClass: 'p-button-danger',
      accept: async () => {
        try {
          await this.api.request('POST', '/local-certificate/rotate');
          this.api.ok('Certificado rotado.');
          await this.loadCertificate();
        } catch (error) {
          this.api.fail(error);
        }
      },
    });
  }
}
