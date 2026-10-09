import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { DomSanitizer } from '@angular/platform-browser';
import { ConfirmationService, MessageService } from 'primeng/api';
import { providePrimeNG } from 'primeng/config';
import { API } from '../core/admin-api';
import { Sign } from './sign';

const SIGNING_URL = 'http://firmadoc.test:8000/sign/0f3c7f5e-1111-2222-3333-444444444444#t=abc';

function pdf(name: string, size = 10): File {
  return new File([new Uint8Array(size)], name, { type: 'application/pdf' });
}

/** Espera a que el componente termine de leer los archivos (FileReader) y envíe el pedido. */
async function expectRequest(http: HttpTestingController, url: string) {
  for (let i = 0; i < 100; i++) {
    await new Promise((resolve) => setTimeout(resolve, 1));
    const pending = http.match(url);
    if (pending.length) return pending[0];
  }
  throw new Error('no se envió ' + url);
}

describe('Sign', () => {
  let fixture: ComponentFixture<Sign>;
  let component: Sign;
  let http: HttpTestingController;
  let toast: MessageService;

  beforeEach(async () => {
    TestBed.configureTestingModule({
      imports: [Sign],
      providers: [provideHttpClient(), provideHttpClientTesting(), providePrimeNG(), MessageService, ConfirmationService],
    });
    fixture = TestBed.createComponent(Sign);
    component = fixture.componentInstance;
    http = TestBed.inject(HttpTestingController);
    toast = TestBed.inject(MessageService);
    await fixture.whenStable();
  });

  afterEach(() => http.verify());

  it('arranca en la carga, sin widget', () => {
    expect(fixture.nativeElement.querySelector('p-fileupload')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('iframe')).toBeNull();
  });

  it('rechaza en el navegador un archivo que no es PDF sin enviar nada', async () => {
    const add = vi.spyOn(toast, 'add');
    await component.upload([pdf('a.pdf'), new File(['x'], 'notas.txt', { type: 'text/plain' })]);
    expect(add).toHaveBeenCalledWith(expect.objectContaining({ severity: 'error', detail: expect.stringContaining('notas.txt') }));
    http.expectNone(`${API}/signing-uploads`);
    http.expectNone(`${API}/signing-batch-uploads`);
  });

  it('un PDF se carga como individual y muestra la tarjeta y el iframe del widget', async () => {
    const pending = component.upload([pdf('Resolucion.pdf')]);
    const request = await expectRequest(http, `${API}/signing-uploads`);
    expect(request.request.body).toEqual({ filename: 'Resolucion.pdf', document_base64: expect.any(String) });
    request.flush({
      request_id: 'r1',
      document_id: 'd1',
      signing_url: SIGNING_URL,
      filename: 'Resolucion.pdf',
      page_count: 2,
      size_bytes: 2048,
      document_hash: 'h',
    });
    await pending;
    await fixture.whenStable();
    const root: HTMLElement = fixture.nativeElement;
    expect(root.querySelector('#sign-name')?.textContent).toBe('Resolucion.pdf');
    expect(root.textContent).toContain('2 páginas · 2 KB');
    const iframe = root.querySelector('iframe')!;
    expect(iframe.getAttribute('src')).toBe(SIGNING_URL);
    expect(iframe.getAttribute('sandbox')).toBe('allow-scripts allow-same-origin allow-downloads');
    expect(iframe.getAttribute('referrerpolicy')).toBe('no-referrer');
    expect(component.ready()?.origin).toBe('http://firmadoc.test:8000');
  });

  it('varios PDF se cargan como lote', async () => {
    const pending = component.upload([pdf('a.pdf'), pdf('b.pdf')]);
    const request = await expectRequest(http, `${API}/signing-batch-uploads`);
    expect(request.request.body.documents).toHaveLength(2);
    request.flush({
      batch_id: 'b1',
      signing_url: SIGNING_URL,
      documents: [
        { document_id: 'd1', document_hash: 'h1', filename: 'a.pdf', page_count: 1, size_bytes: 10 },
        { document_id: 'd2', document_hash: 'h2', filename: 'b.pdf', page_count: 1, size_bytes: 10 },
      ],
    });
    await pending;
    await fixture.whenStable();
    expect(fixture.nativeElement.querySelector('#sign-name')?.textContent).toBe('2 documentos');
    expect(fixture.nativeElement.querySelectorAll('#sign-docs li')).toHaveLength(2);
  });

  describe('mensajes del widget', () => {
    let source: Window;

    beforeEach(async () => {
      const url = TestBed.inject(DomSanitizer).bypassSecurityTrustResourceUrl(SIGNING_URL);
      component.ready.set({ name: 'x', meta: '', url, origin: 'http://firmadoc.test:8000', documents: null });
      await fixture.whenStable();
      source = (fixture.nativeElement.querySelector('iframe') as HTMLIFrameElement).contentWindow!;
    });

    const message = (data: unknown, origin = 'http://firmadoc.test:8000', from: Window | null = source) =>
      component.onMessage(new MessageEvent('message', { data, origin, source: from }));

    it('acepta firmadoc:signed desde la ventana del iframe y su origen', () => {
      message({ source: 'firmadoc', type: 'firmadoc:signed', requestId: 'r1' });
      expect(component.result()?.severity).toBe('success');
    });

    it('ignora otro origen, otra ventana y otro emisor', () => {
      message({ source: 'firmadoc', type: 'firmadoc:signed' }, 'http://malicioso.test');
      message({ source: 'firmadoc', type: 'firmadoc:signed' }, 'http://firmadoc.test:8000', window);
      message({ source: 'otro', type: 'firmadoc:signed' });
      message('texto suelto');
      expect(component.result()).toBeNull();
    });

    it('informa lotes parciales, fallos y cancelaciones', () => {
      message({ source: 'firmadoc', type: 'firmadoc:batch-completed', signed: 2, total: 3 });
      expect(component.result()).toEqual({ severity: 'error', text: expect.stringContaining('2 de 3 documentos firmados') });
      message({ source: 'firmadoc', type: 'firmadoc:failed', code: 'agent_missing' });
      expect(component.result()?.text).toBe('La firma falló (agent_missing).');
      message({ source: 'firmadoc', type: 'firmadoc:cancelled' });
      expect(component.result()?.severity).toBe('error');
    });

    it('«Quitar» vuelve a la carga sin widget', async () => {
      component.reset();
      await fixture.whenStable();
      expect(fixture.nativeElement.querySelector('iframe')).toBeNull();
      expect(fixture.nativeElement.querySelector('p-fileupload')).not.toBeNull();
    });
  });
});
