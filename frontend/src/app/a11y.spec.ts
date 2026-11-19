import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, TestRequest, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import axe from 'axe-core';
import { ConfirmationService, MessageService } from 'primeng/api';
import { providePrimeNG } from 'primeng/config';
import { App, Tab } from './app';
import { API, AdminApi } from './core/admin-api';
import { Custody, Integrator, LocalCertificate, RequestItem, TrustAnchor, WebhookDelivery } from './core/api-types';
import { Sign } from './sections/sign';

/**
 * Accesibilidad del panel, pantalla por pantalla, con axe. Cada pantalla se revisa con datos y en sus estados
 * menos frecuentes (vacío, detalle, documento cargado), que son los que nadie abre a mano.
 * Límites, a propósito:
 * - jsdom no calcula estilos, así que el contraste de color queda fuera (regla `color-contrast`).
 * - `p-confirmdialog` de PrimeNG deja siempre en la página un `<p-dialog role="alertdialog">` vacío y sin
 *   nombre, aunque el diálogo esté cerrado; no se puede corregir sin tocar la librería. Se excluye ese
 *   elemento cerrado y se revisa aparte el diálogo abierto, que es el que alguien llega a usar.
 * - No se entra al iframe del widget (`iframes: false`): jsdom no lo carga, y el widget tiene sus propias
 *   pruebas con axe. Sí se revisa que el iframe tenga título.
 */
const OPTIONS = { iframes: false, rules: { 'color-contrast': { enabled: false } } };
const CLOSED_CONFIRM_HOST = 'p-confirmdialog > p-dialog';

async function violations(root: Element): Promise<string[]> {
  const results = await axe.run(
    { include: [root as HTMLElement], exclude: [[CLOSED_CONFIRM_HOST]] },
    OPTIONS,
  );
  return results.violations.map((v) => `${v.id}: ${v.help} (${v.nodes.map((n) => n.target.join(' ')).join(' | ')})`);
}

const REQUEST: RequestItem = {
  id: 'r1',
  created_at: '2026-11-18T14:44:20Z',
  status: 'pending',
  provider: 'token',
  integrating_system: { id: 's1', name: 'Firmadoc (panel)' },
  document: {
    id: 'd1',
    external_document_id: 'Resolucion-0457',
    signing_status: 'pending_signature',
    current_version_number: 1,
    signature_deadline: '2026-12-01T00:00:00Z',
  },
  signer: { name: 'Firmante de Prueba', identifier: '20000000001' },
  certificate: null,
  origin: { kind: 'batch', batch_id: 'b1', label: '#0004' },
};

const CUSTODY: Custody = {
  document: {
    id: 'd1',
    external_document_id: 'Resolucion-0457',
    signing_status: 'signed',
    signature_deadline: null,
    integrating_system_name: 'Firmadoc (panel)',
  },
  versions: [
    { version_number: 1, origin: 'uploaded', signature_level: null, is_current: false, document_hash: 'h1', created_at: '2026-11-18T14:44:20Z' },
    { version_number: 2, origin: 'signed', signature_level: 'B-B', is_current: true, document_hash: 'h2', created_at: '2026-11-18T14:45:00Z' },
  ],
  timeline: [
    { at: '2026-11-18T14:44:20Z', actor: 'panel', title: 'Documento cargado', detail: null, kind: 'ok' },
    { at: '2026-11-18T14:45:00Z', actor: 'Firmante de Prueba', title: 'Firmado', detail: 'PAdES B-B', kind: 'ok' },
  ],
  technical: null,
};

const INTEGRATORS: Integrator[] = [
  { id: 'i1', name: 'Sistema de expedientes', allowed_origins: ['https://sistema.example.org'], has_webhook_secret: true, status: 'active', internal: false, created_at: '2026-11-01T00:00:00Z' },
  { id: 'i2', name: 'Firmadoc (panel)', allowed_origins: [], has_webhook_secret: false, status: 'disabled', internal: true, created_at: '2026-11-01T00:00:00Z' },
];

const ANCHORS: TrustAnchor[] = [{ is_root: true, subject: 'AC de Prueba', not_after: '2036-11-08T12:12:50Z', fingerprint: 'ab'.repeat(32) }];
const CERTIFICATE: LocalCertificate = {
  current: { subject: 'Firmadoc Demo Signer', serial_number: '4348', not_after: '2027-11-18T00:00:00Z' },
  archived: [],
};
const DELIVERY: WebhookDelivery = {
  id: 'w1',
  created_at: '2026-11-18T14:45:01Z',
  event_type: 'signature_request.signed',
  url: 'https://sistema.example.org/webhooks/firmadoc',
  status: 'failed',
  attempts: 3,
  next_attempt_at: null,
  last_error: 'timeout',
  response_status: null,
};

/** Responde cada pedido pendiente con datos de ejemplo según su URL. */
function answer(request: TestRequest, empty: boolean): void {
  const url = request.request.url;
  if (url.includes('/custody')) request.flush(CUSTODY);
  else if (url.includes('/signature-requests')) request.flush(empty ? { items: [], total: 0 } : { items: [REQUEST], total: 1 });
  else if (url.includes('/webhook-deliveries')) request.flush({ items: empty ? [] : [DELIVERY], total: empty ? 0 : 1 });
  else if (url.includes('/events')) request.flush({ items: empty ? [] : [{ id: 'e1', created_at: '2026-11-18T14:44:20Z', actor: 'admin', action: 'panel_upload', detail: { filename: 'x.pdf' } }], total: 1 });
  else if (url.includes('/integrators')) request.flush(empty ? [] : INTEGRATORS);
  else if (url.includes('/trust-anchors')) request.flush(empty ? [] : ANCHORS);
  else if (url.includes('/local-certificate')) request.flush(empty ? { current: null, archived: [] } : CERTIFICATE);
  else request.flush({});
}

describe('Accesibilidad del panel (axe)', () => {
  let fixture: ComponentFixture<App>;
  let http: HttpTestingController;

  beforeEach(() => {
    sessionStorage.clear();
    TestBed.configureTestingModule({
      imports: [App],
      providers: [provideHttpClient(), provideHttpClientTesting(), providePrimeNG(), MessageService, ConfirmationService],
    });
    fixture = TestBed.createComponent(App);
    http = TestBed.inject(HttpTestingController);
  });

  async function settle(empty = false): Promise<void> {
    for (let i = 0; i < 4; i++) {
      await fixture.whenStable();
      http.match(() => true).forEach((r) => answer(r, empty));
    }
    await fixture.whenStable();
  }

  async function login(): Promise<void> {
    const pending = TestBed.inject(AdminApi).login('t0ken-de-administracion-' + 'x'.repeat(20));
    http.expectOne(`${API}/events?limit=1`).flush({ items: [], total: 0 });
    await pending;
    await settle();
  }

  async function open(tab: Tab, empty = false): Promise<void> {
    await login();
    fixture.componentInstance.go(tab);
    await settle(empty);
  }

  it('ingreso', async () => {
    await fixture.whenStable();
    expect(await violations(fixture.nativeElement)).toEqual([]);
  });

  it('estructura con el menú lateral y la carga de documentos', async () => {
    await login();
    expect(fixture.nativeElement.querySelector('app-sign p-fileupload')).not.toBeNull();
    expect(await violations(fixture.nativeElement)).toEqual([]);
  });

  it('menú en panel deslizante (pantallas angostas)', async () => {
    await login();
    fixture.componentInstance.drawer.set(true);
    await settle();
    const drawer = document.querySelector('.sidebar-drawer');
    expect(drawer).not.toBeNull();
    expect(await violations(drawer!)).toEqual([]);
  });

  it('documento cargado con el módulo de firma abierto, y con el aviso de cierre sin firmar', async () => {
    await login();
    const sign = fixture.debugElement.query((el) => el.componentInstance instanceof Sign).componentInstance as Sign;
    sign.ready.set({ name: 'Resolucion-0457.pdf', meta: '2 páginas · 180 KB', signingUrl: 'http://firmadoc.test:8000/sign/x#t=abc', documents: null });
    sign.openWidget();
    await settle();
    expect(fixture.nativeElement.querySelector('#sign-widget iframe')).not.toBeNull();
    expect(await violations(fixture.nativeElement)).toEqual([]);
    sign.closeWidget();
    await settle();
    expect(fixture.nativeElement.querySelector('#sign-result')).not.toBeNull();
    expect(await violations(fixture.nativeElement)).toEqual([]);
  });

  it('documentos: listado con datos, listado vacío y detalle de custodia', async () => {
    await open('documents');
    expect(fixture.nativeElement.querySelectorAll('#requests-table tbody tr').length).toBe(1);
    expect(await violations(fixture.nativeElement)).toEqual([]);

    (fixture.nativeElement.querySelector('#requests-table tbody button') as HTMLElement).click();
    await settle();
    expect(fixture.nativeElement.querySelector('#document-detail')).not.toBeNull();
    expect(await violations(fixture.nativeElement)).toEqual([]);
  });

  it('documentos sin resultados', async () => {
    await open('documents', true);
    expect(fixture.nativeElement.querySelector('.empty-state')).not.toBeNull();
    expect(await violations(fixture.nativeElement)).toEqual([]);
  });

  it('auditoría con una entrega fallida, y vacía', async () => {
    await open('audit');
    expect(fixture.nativeElement.textContent).toContain('Reenviar');
    expect(await violations(fixture.nativeElement)).toEqual([]);
  });

  it('integradores con uno activo y uno interno deshabilitado', async () => {
    await open('integrators');
    expect(fixture.nativeElement.querySelectorAll('#integrators-table tbody tr').length).toBe(2);
    expect(await violations(fixture.nativeElement)).toEqual([]);
  });

  it('confianza con anclas y certificado propio, y sin anclas', async () => {
    await open('trust');
    expect(fixture.nativeElement.querySelector('#certificate-info')).not.toBeNull();
    expect(await violations(fixture.nativeElement)).toEqual([]);
  });

  it('confianza sin anclas ni certificado', async () => {
    await open('trust', true);
    expect(await violations(fixture.nativeElement)).toEqual([]);
  });

  it('diálogo de confirmación abierto: tiene nombre y botones con texto', async () => {
    await login();
    TestBed.inject(ConfirmationService).confirm({ message: '¿Rotar el certificado propio?', acceptLabel: 'Rotar', rejectLabel: 'Cancelar' });
    await settle();
    const dialog = document.querySelector('.p-dialog[role="alertdialog"], [role="alertdialog"] .p-dialog, .p-confirmdialog');
    expect(dialog).not.toBeNull();
    expect(document.body.textContent).toContain('¿Rotar el certificado propio?');
    const open = Array.from(document.querySelectorAll('[role="alertdialog"]')).filter((el) => el.textContent?.includes('Rotar'));
    expect(open.length).toBeGreaterThan(0);
    for (const element of open) {
      const results = await axe.run(element as HTMLElement, OPTIONS);
      expect(results.violations.map((v) => v.id + ' ' + v.nodes.map((n) => n.html.slice(0, 220)).join(' || '))).toEqual([]);
    }
  });
});
