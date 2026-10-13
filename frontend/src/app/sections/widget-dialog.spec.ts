import { ComponentFixture, TestBed } from '@angular/core/testing';
import { DynamicDialogConfig, DynamicDialogRef } from 'primeng/dynamicdialog';
import { SignResult } from '../core/widget-messages';
import { WidgetDialog, WidgetDialogData } from './widget-dialog';

const SIGNING_URL = 'http://firmadoc.test:8000/sign/0f3c7f5e-1111-2222-3333-444444444444#t=abc';
const ORIGIN = 'http://firmadoc.test:8000';

describe('WidgetDialog', () => {
  let fixture: ComponentFixture<WidgetDialog>;
  let component: WidgetDialog;
  let results: SignResult[];
  let close: ReturnType<typeof vi.fn>;
  let source: Window;

  beforeEach(async () => {
    results = [];
    close = vi.fn();
    const data: WidgetDialogData = { signingUrl: SIGNING_URL, onResult: (r) => results.push(r) };
    TestBed.configureTestingModule({
      imports: [WidgetDialog],
      providers: [
        { provide: DynamicDialogConfig, useValue: { data } },
        { provide: DynamicDialogRef, useValue: { close } },
      ],
    });
    fixture = TestBed.createComponent(WidgetDialog);
    component = fixture.componentInstance;
    await fixture.whenStable();
    source = (fixture.nativeElement.querySelector('iframe') as HTMLIFrameElement).contentWindow!;
  });

  const message = (data: unknown, origin = ORIGIN, from: Window | null = source) =>
    component.onMessage(new MessageEvent('message', { data, origin, source: from }));

  it('embebe el widget con sandbox, allow y referrerpolicy', () => {
    const iframe = fixture.nativeElement.querySelector('iframe') as HTMLIFrameElement;
    expect(iframe.getAttribute('src')).toBe(SIGNING_URL);
    expect(iframe.getAttribute('sandbox')).toBe('allow-scripts allow-same-origin allow-downloads allow-popups allow-popups-to-escape-sandbox');
    expect(iframe.getAttribute('allow')).toContain('local-network-access');
    expect(iframe.getAttribute('referrerpolicy')).toBe('no-referrer');
    expect(component.origin).toBe(ORIGIN);
  });

  it('informa firmadoc:signed desde la ventana del iframe y su origen', () => {
    message({ source: 'firmadoc', type: 'firmadoc:signed', requestId: 'r1' });
    expect(results).toEqual([expect.objectContaining({ severity: 'success' })]);
    expect(close).not.toHaveBeenCalled();
  });

  it('ignora otro origen, otra ventana y otro emisor', () => {
    message({ source: 'firmadoc', type: 'firmadoc:signed' }, 'http://malicioso.test');
    message({ source: 'firmadoc', type: 'firmadoc:signed' }, ORIGIN, window);
    message({ source: 'otro', type: 'firmadoc:signed' });
    message('texto suelto');
    expect(results).toEqual([]);
    expect(close).not.toHaveBeenCalled();
  });

  it('informa lotes parciales, fallos y cancelaciones', () => {
    message({ source: 'firmadoc', type: 'firmadoc:batch-completed', signed: 2, total: 3 });
    message({ source: 'firmadoc', type: 'firmadoc:failed', code: 'agent_missing' });
    message({ source: 'firmadoc', type: 'firmadoc:cancelled' });
    expect(results.map((r) => r.severity)).toEqual(['error', 'error', 'error']);
    expect(results[0].text).toContain('2 de 3 documentos firmados');
    expect(results[1].text).toBe('La firma falló (agent_missing).');
  });

  it('se cierra cuando la persona cierra la pantalla final del widget', () => {
    message({ source: 'firmadoc', type: 'firmadoc:closed' });
    expect(close).toHaveBeenCalledTimes(1);
  });
});
