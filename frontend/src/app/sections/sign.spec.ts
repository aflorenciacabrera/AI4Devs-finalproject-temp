import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ConfirmationService, MessageService } from 'primeng/api';
import { providePrimeNG } from 'primeng/config';
import { API } from '../core/admin-api';
import { CLOSED_WITHOUT_SIGNING, Sign } from './sign';
import { PopupLike } from './widget-window';

const SIGNING_URL = 'http://firmadoc.test:8000/sign/0f3c7f5e-1111-2222-3333-444444444444#t=abc';
const ORIGIN = 'http://firmadoc.test:8000';

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

class FakePopup implements PopupLike {
  closed = false;
  location = { href: 'about:blank' };
  document = { write: () => {}, close: () => {} };
  close = vi.fn(() => (this.closed = true));
  focus = vi.fn();
}

const dialogIframe = () => document.querySelector('.widget-dialog iframe') as HTMLIFrameElement | null;

const singleUpload = {
  request_id: 'r1',
  document_id: 'd1',
  signing_url: SIGNING_URL,
  filename: 'Resolucion.pdf',
  page_count: 2,
  size_bytes: 2048,
  document_hash: 'h',
};

describe('Sign', () => {
  let fixture: ComponentFixture<Sign>;
  let component: Sign;
  let http: HttpTestingController;
  let toast: MessageService;
  let popup: FakePopup;
  let open: ReturnType<typeof vi.spyOn>;

  beforeEach(async () => {
    popup = new FakePopup();
    open = vi.spyOn(window, 'open').mockReturnValue(popup as unknown as Window);
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
    vi.restoreAllMocks();
  });

  const fromPopup = (data: unknown) =>
    window.dispatchEvent(new MessageEvent('message', { data, origin: ORIGIN, source: popup as unknown as Window }));

  it('arranca en la carga, sin widget', () => {
    expect(fixture.nativeElement.querySelector('p-fileupload')).not.toBeNull();
    expect(open).not.toHaveBeenCalled();
    expect(dialogIframe()).toBeNull();
  });

  it('rechaza en el navegador un archivo que no es PDF sin enviar nada ni abrir ventanas', async () => {
    const add = vi.spyOn(toast, 'add');
    await component.upload([pdf('a.pdf'), new File(['x'], 'notas.txt', { type: 'text/plain' })]);
    expect(add).toHaveBeenCalledWith(expect.objectContaining({ severity: 'error', detail: expect.stringContaining('notas.txt') }));
    expect(open).not.toHaveBeenCalled();
    http.expectNone(`${API}/signing-uploads`);
    http.expectNone(`${API}/signing-batch-uploads`);
  });

  it('un PDF se carga como individual, muestra la tarjeta y abre el widget en una ventana propia', async () => {
    const pending = component.upload([pdf('Resolucion.pdf')]);
    expect(open).toHaveBeenCalledTimes(1); // reservada en el gesto del usuario, antes de subir
    expect(popup.location.href).toBe('about:blank');
    const request = await expectRequest(http, `${API}/signing-uploads`);
    expect(request.request.body).toEqual({ filename: 'Resolucion.pdf', document_base64: expect.any(String) });
    request.flush(singleUpload);
    await pending;
    await fixture.whenStable();
    const root: HTMLElement = fixture.nativeElement;
    expect(root.querySelector('#sign-name')?.textContent).toBe('Resolucion.pdf');
    expect(root.textContent).toContain('2 páginas · 2 KB');
    expect(component.widgetOpen()).toBe(true);
    expect(popup.location.href).toBe(SIGNING_URL);
    expect(popup.close).not.toHaveBeenCalled(); // la ventana reservada es la que se usa
    expect(dialogIframe()).toBeNull();
    expect(root.querySelector('#sign-open')?.textContent).toContain('Ir a la ventana de firma');
  });

  it('si la carga falla, la ventana reservada se cierra', async () => {
    vi.spyOn(toast, 'add');
    const pending = component.upload([pdf('Resolucion.pdf')]);
    const request = await expectRequest(http, `${API}/signing-uploads`);
    request.flush({ detail: 'no' }, { status: 422, statusText: 'Unprocessable' });
    await pending;
    expect(popup.close).toHaveBeenCalled();
    expect(component.widgetOpen()).toBe(false);
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
    expect(popup.location.href).toBe(SIGNING_URL);
  });

  it('si el navegador bloquea la ventana, el widget se abre en un diálogo como respaldo', async () => {
    open.mockReturnValue(null);
    const pending = component.upload([pdf('Resolucion.pdf')]);
    (await expectRequest(http, `${API}/signing-uploads`)).flush(singleUpload);
    await pending;
    await fixture.whenStable();
    expect(component.widgetOpen()).toBe(true);
    const iframe = dialogIframe();
    expect(iframe?.getAttribute('src')).toBe(SIGNING_URL);
    expect(iframe?.getAttribute('sandbox')).toBe('allow-scripts allow-same-origin allow-downloads allow-popups allow-popups-to-escape-sandbox');
    expect(document.querySelector('.widget-dialog .p-dialog-title')?.textContent).toContain('Resolucion.pdf');
    component.closeWidget();
    await fixture.whenStable();
    expect(component.widgetOpen()).toBe(false);
    expect(component.result()).toEqual(CLOSED_WITHOUT_SIGNING);
  });

  describe('con un documento cargado en la ventana propia', () => {
    beforeEach(async () => {
      component.ready.set({ name: 'x.pdf', meta: '1 página · 1 KB', signingUrl: SIGNING_URL, documents: null });
      component.openWidget();
      await fixture.whenStable();
    });

    it('cerrar la ventana sin firmar deja el aviso y permite reabrirla', async () => {
      expect(component.widgetOpen()).toBe(true);
      fromPopup({ source: 'firmadoc', type: 'firmadoc:closed' });
      await fixture.whenStable();
      expect(component.widgetOpen()).toBe(false);
      expect(component.result()).toEqual(CLOSED_WITHOUT_SIGNING);
      expect(fixture.nativeElement.querySelector('#sign-open')?.textContent).toContain('Abrir módulo de firma');
    });

    it('el resultado del widget se refleja en la tarjeta sin cerrar la ventana', async () => {
      fromPopup({ source: 'firmadoc', type: 'firmadoc:signed', requestId: 'r1' });
      await fixture.whenStable();
      expect(component.result()?.severity).toBe('success');
      expect(component.widgetOpen()).toBe(true);
      expect(popup.close).not.toHaveBeenCalled();
      expect(fixture.nativeElement.querySelector('#sign-result')?.textContent).toContain('Documento firmado');
      fromPopup({ source: 'firmadoc', type: 'firmadoc:closed' });
      await fixture.whenStable();
      expect(component.widgetOpen()).toBe(false);
      expect(component.result()?.severity).toBe('success'); // el aviso de «sin firmar» no pisa el resultado
    });

    it('«Ir a la ventana de firma» la trae al frente', () => {
      component.focusWidget();
      expect(popup.focus).toHaveBeenCalledTimes(1);
    });

    it('«Quitar» vuelve a la carga y cierra la ventana', async () => {
      component.reset();
      await fixture.whenStable();
      expect(component.widgetOpen()).toBe(false);
      expect(popup.close).toHaveBeenCalled();
      expect(fixture.nativeElement.querySelector('p-fileupload')).not.toBeNull();
    });
  });
});
