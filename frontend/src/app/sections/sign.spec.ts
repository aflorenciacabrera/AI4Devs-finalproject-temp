import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ConfirmationService, MessageService } from 'primeng/api';
import { providePrimeNG } from 'primeng/config';
import { API } from '../core/admin-api';
import { CLOSED_WITHOUT_SIGNING, Sign } from './sign';

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

const dialogIframe = () => document.querySelector('.widget-dialog iframe') as HTMLIFrameElement | null;

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

  afterEach(async () => {
    component.closeWidget();
    await fixture.whenStable();
    http.verify();
  });

  it('arranca en la carga, sin widget', () => {
    expect(fixture.nativeElement.querySelector('p-fileupload')).not.toBeNull();
    expect(dialogIframe()).toBeNull();
  });

  it('rechaza en el navegador un archivo que no es PDF sin enviar nada', async () => {
    const add = vi.spyOn(toast, 'add');
    await component.upload([pdf('a.pdf'), new File(['x'], 'notas.txt', { type: 'text/plain' })]);
    expect(add).toHaveBeenCalledWith(expect.objectContaining({ severity: 'error', detail: expect.stringContaining('notas.txt') }));
    http.expectNone(`${API}/signing-uploads`);
    http.expectNone(`${API}/signing-batch-uploads`);
  });

  it('un PDF se carga como individual, muestra la tarjeta y abre el widget en un diálogo', async () => {
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
    expect(component.widgetOpen()).toBe(true);
    const iframe = dialogIframe();
    expect(iframe?.getAttribute('src')).toBe(SIGNING_URL);
    expect(iframe?.getAttribute('sandbox')).toBe('allow-scripts allow-same-origin allow-downloads allow-popups allow-popups-to-escape-sandbox');
    expect(document.querySelector('.widget-dialog .p-dialog-title')?.textContent).toContain('Resolucion.pdf');
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
    expect(dialogIframe()).not.toBeNull();
  });

  describe('con un documento cargado', () => {
    beforeEach(async () => {
      component.ready.set({ name: 'x.pdf', meta: '1 página · 1 KB', signingUrl: SIGNING_URL, documents: null });
      component.openWidget();
      await fixture.whenStable();
    });

    it('cerrar el diálogo sin firmar deja el aviso y permite reabrirlo', async () => {
      expect(dialogIframe()).not.toBeNull();
      component.closeWidget();
      await fixture.whenStable();
      expect(component.widgetOpen()).toBe(false);
      expect(component.result()).toEqual(CLOSED_WITHOUT_SIGNING);
      expect(fixture.nativeElement.querySelector('#sign-open')).not.toBeNull();
    });

    it('el resultado del widget se refleja en la tarjeta sin cerrar el diálogo', async () => {
      const iframe = dialogIframe()!;
      window.dispatchEvent(
        new MessageEvent('message', {
          data: { source: 'firmadoc', type: 'firmadoc:signed', requestId: 'r1' },
          origin: 'http://firmadoc.test:8000',
          source: iframe.contentWindow,
        }),
      );
      await fixture.whenStable();
      expect(component.result()?.severity).toBe('success');
      expect(component.widgetOpen()).toBe(true);
      expect(fixture.nativeElement.querySelector('#sign-result')?.textContent).toContain('Documento firmado');
    });

    it('«Quitar» vuelve a la carga y cierra el widget', async () => {
      component.reset();
      await fixture.whenStable();
      expect(component.widgetOpen()).toBe(false);
      expect(fixture.nativeElement.querySelector('p-fileupload')).not.toBeNull();
    });
  });
});
