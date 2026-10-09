import { fmt, formatSize, isPdf, pagesLabel, providerLabel, statusLabel } from './format';

describe('format', () => {
  it('fmt muestra vacíos como guion, fechas en es-AR y objetos como JSON', () => {
    expect(fmt(null)).toBe('-');
    expect(fmt('')).toBe('-');
    expect(fmt(undefined)).toBe('-');
    expect(fmt({ a: 1 })).toBe('{"a":1}');
    expect(fmt(3)).toBe('3');
    expect(fmt('2026-10-08T12:00:00Z')).toBe(new Date('2026-10-08T12:00:00Z').toLocaleString('es-AR'));
    expect(fmt('no es fecha')).toBe('no es fecha');
  });

  it('formatSize redondea a KB o MB', () => {
    expect(formatSize(10)).toBe('1 KB');
    expect(formatSize(2048)).toBe('2 KB');
    expect(formatSize(1.5 * 1048576)).toBe('1.5 MB');
  });

  it('isPdf acepta por tipo o por extensión', () => {
    expect(isPdf({ type: 'application/pdf', name: 'x' })).toBe(true);
    expect(isPdf({ type: '', name: 'Resolucion.PDF' })).toBe(true);
    expect(isPdf({ type: 'text/plain', name: 'notas.txt' })).toBe(false);
  });

  it('etiquetas en español con el valor técnico como respaldo', () => {
    expect(pagesLabel(1)).toBe('1 página');
    expect(pagesLabel(3)).toBe('3 páginas');
    expect(statusLabel('signed')).toBe('Firmado');
    expect(statusLabel('otro')).toBe('otro');
    expect(providerLabel('local')).toBe('Propio');
  });
});
