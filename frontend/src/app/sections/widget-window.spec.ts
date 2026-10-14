import { TestBed } from '@angular/core/testing';
import { SignResult } from '../core/widget-messages';
import { PopupLike, WidgetWindow, WidgetWindowHandle } from './widget-window';

const SIGNING_URL = 'http://firmadoc.test:8000/sign/0f3c7f5e-1111-2222-3333-444444444444#t=abc';
const ORIGIN = 'http://firmadoc.test:8000';

class FakePopup implements PopupLike {
  closed = false;
  location = { href: 'about:blank' };
  written = '';
  document = { write: (html: string) => (this.written += html), close: () => {} };
  close = vi.fn(() => (this.closed = true));
  focus = vi.fn();
}

describe('WidgetWindow', () => {
  let service: WidgetWindow;
  let popup: FakePopup;
  let openSpy: ReturnType<typeof vi.spyOn>;
  let results: SignResult[];
  let closedCount: number;

  beforeEach(() => {
    vi.useFakeTimers();
    service = TestBed.inject(WidgetWindow);
    popup = new FakePopup();
    openSpy = vi.spyOn(window, 'open').mockReturnValue(popup as unknown as Window);
    results = [];
    closedCount = 0;
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  const opened = (): WidgetWindowHandle => {
    const handle = service.reserve()!;
    handle.open(SIGNING_URL, { onResult: (r) => results.push(r), onClosed: () => closedCount++ });
    return handle;
  };

  const message = (data: unknown, origin = ORIGIN, source: unknown = popup) =>
    window.dispatchEvent(new MessageEvent('message', { data, origin, source: source as Window }));

  it('reserva una ventana emergente con nombre fijo y la navega a la signing_url', () => {
    opened();
    expect(openSpy).toHaveBeenCalledTimes(1);
    expect(openSpy.mock.calls[0][1]).toBe('firmadoc-firma');
    expect(String(openSpy.mock.calls[0][2])).toContain('popup=yes');
    expect(popup.written).toContain('Preparando el documento');
    expect(popup.location.href).toBe(SIGNING_URL);
  });

  it('devuelve null si el navegador bloqueó la ventana', () => {
    openSpy.mockReturnValue(null);
    expect(service.reserve()).toBeNull();
  });

  it('informa los resultados que vienen de esa ventana y de ese origen', () => {
    opened();
    message({ source: 'firmadoc', type: 'firmadoc:signed', requestId: 'r1' });
    message({ source: 'firmadoc', type: 'firmadoc:cancelled' });
    expect(results.map((r) => r.severity)).toEqual(['success', 'error']);
    expect(closedCount).toBe(0);
  });

  it('ignora otro origen, otra ventana y otro emisor', () => {
    opened();
    message({ source: 'firmadoc', type: 'firmadoc:signed' }, 'http://malicioso.test');
    message({ source: 'firmadoc', type: 'firmadoc:signed' }, ORIGIN, window);
    message({ source: 'otro', type: 'firmadoc:signed' });
    expect(results).toEqual([]);
  });

  it('con firmadoc:closed avisa una vez, cierra la ventana y deja de escuchar', () => {
    opened();
    message({ source: 'firmadoc', type: 'firmadoc:closed' });
    expect(closedCount).toBe(1);
    expect(popup.close).toHaveBeenCalled();
    vi.advanceTimersByTime(1000);
    message({ source: 'firmadoc', type: 'firmadoc:signed' });
    expect(results).toEqual([]);
    expect(closedCount).toBe(1);
  });

  it('detecta que la persona cerró la ventana', () => {
    opened();
    popup.closed = true;
    vi.advanceTimersByTime(400);
    expect(closedCount).toBe(1);
    vi.advanceTimersByTime(2000);
    expect(closedCount).toBe(1);
  });

  it('close() cierra la ventana sin avisar', () => {
    const handle = opened();
    handle.close();
    expect(popup.close).toHaveBeenCalled();
    expect(closedCount).toBe(0);
    vi.advanceTimersByTime(1000);
    expect(closedCount).toBe(0);
  });

  it('focus() trae la ventana al frente mientras esté abierta', () => {
    const handle = opened();
    handle.focus();
    expect(popup.focus).toHaveBeenCalledTimes(1);
    popup.closed = true;
    handle.focus();
    expect(popup.focus).toHaveBeenCalledTimes(1);
  });
});
