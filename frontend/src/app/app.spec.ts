import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { ConfirmationService, MessageService } from 'primeng/api';
import { providePrimeNG } from 'primeng/config';
import { App } from './app';
import { API, AdminApi } from './core/admin-api';

describe('App', () => {
  beforeEach(() => {
    sessionStorage.clear();
    TestBed.configureTestingModule({
      imports: [App],
      providers: [provideHttpClient(), provideHttpClientTesting(), providePrimeNG(), MessageService, ConfirmationService],
    });
  });

  it('sin sesión muestra el ingreso y no la navegación', async () => {
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    const root: HTMLElement = fixture.nativeElement;
    expect(root.querySelector('app-login')).not.toBeNull();
    expect(root.querySelector('.sidebar')).toBeNull();
  });

  it('con sesión muestra las secciones y arranca en «Firmar documento»', async () => {
    const fixture = TestBed.createComponent(App);
    const http = TestBed.inject(HttpTestingController);
    const pending = TestBed.inject(AdminApi).login('t0ken-de-administracion-' + 'x'.repeat(20));
    http.expectOne(`${API}/events?limit=1`).flush({ items: [], total: 0 });
    await pending;
    await fixture.whenStable();
    const root: HTMLElement = fixture.nativeElement;
    const labels = Array.from(root.querySelectorAll('.sidebar .p-menu-item-label')).map((b) => b.textContent?.trim());
    expect(labels).toEqual(['Firmar documento', 'Documentos', 'Auditoría', 'Integradores', 'Confianza']);
    expect(root.querySelector('app-sign')).not.toBeNull();
    expect(root.querySelector('.sidebar .p-menu-item.active [data-automationid]')?.getAttribute('data-automationid')).toBe('sign');

    (root.querySelector('[data-automationid="documents"]') as HTMLElement).click();
    await fixture.whenStable();
    http.expectOne((r) => r.url.startsWith(`${API}/signature-requests`)).flush({ items: [], total: 0 });
    await fixture.whenStable();
    expect(root.querySelector('app-documents')).not.toBeNull();
    expect(root.querySelector('app-sign')).toBeNull();
    expect(root.querySelector('.sidebar .p-menu-item.active [data-automationid]')?.getAttribute('data-automationid')).toBe('documents');
  });

  it('en pantallas angostas el menú se abre como panel lateral y se cierra al elegir una sección', async () => {
    const fixture = TestBed.createComponent(App);
    const http = TestBed.inject(HttpTestingController);
    const pending = TestBed.inject(AdminApi).login('t0ken-de-administracion-' + 'x'.repeat(20));
    http.expectOne(`${API}/events?limit=1`).flush({ items: [], total: 0 });
    await pending;
    await fixture.whenStable();
    const app = fixture.componentInstance;
    expect(app.drawer()).toBe(false);
    expect(document.querySelector('.sidebar-drawer')).toBeNull();

    (fixture.nativeElement.querySelector('#menu-toggle button') as HTMLElement).click();
    await fixture.whenStable();
    expect(app.drawer()).toBe(true);
    const item = document.querySelector('.sidebar-drawer [data-automationid="trust"]') as HTMLElement;
    expect(item).not.toBeNull();

    item.click();
    await fixture.whenStable();
    http.match(() => true).forEach((r) => r.flush(r.request.url.includes('local-certificate') ? { current: null, archived: [] } : []));
    await fixture.whenStable();
    expect(app.tab()).toBe('trust');
    expect(app.drawer()).toBe(false);
    expect(fixture.nativeElement.querySelector('app-trust')).not.toBeNull();
  });
});
