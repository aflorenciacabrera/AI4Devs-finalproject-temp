import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { MessageService } from 'primeng/api';
import { API, AdminApi, DENIED, UNAUTHORIZED, filenameFrom, isUnauthorized } from './admin-api';

const TOKEN = 't0ken-de-administracion-' + 'x'.repeat(20);

describe('filenameFrom', () => {
  it('prefiere el nombre exacto de filename* (UTF-8) al fallback ASCII', () => {
    const header = `attachment; filename="Resolucion 450 (nueva).pdf"; filename*=UTF-8''Resoluci%C3%B3n%20450%20%28nueva%29.pdf`;
    expect(filenameFrom(header)).toBe('Resolución 450 (nueva).pdf');
  });

  it('usa filename cuando no hay filename*', () => {
    expect(filenameFrom('attachment; filename="acta.pdf"')).toBe('acta.pdf');
    expect(filenameFrom('attachment; filename=acta.pdf')).toBe('acta.pdf');
  });

  it('cae al fallback si filename* está mal codificado y devuelve null sin cabecera', () => {
    expect(filenameFrom(`attachment; filename="acta.pdf"; filename*=UTF-8''%E0%A4%A`)).toBe('acta.pdf');
    expect(filenameFrom(null)).toBeNull();
    expect(filenameFrom('inline')).toBeNull();
  });
});

describe('AdminApi', () => {
  let api: AdminApi;
  let http: HttpTestingController;
  let toast: MessageService;

  beforeEach(() => {
    sessionStorage.clear();
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting(), MessageService] });
    api = TestBed.inject(AdminApi);
    http = TestBed.inject(HttpTestingController);
    toast = TestBed.inject(MessageService);
  });

  afterEach(() => http.verify());

  it('ingresa con Bearer y guarda el token en sessionStorage', async () => {
    const pending = api.login(TOKEN);
    const request = http.expectOne(`${API}/events?limit=1`);
    expect(request.request.headers.get('Authorization')).toBe('Bearer ' + TOKEN);
    request.flush({ items: [], total: 0 });
    expect(await pending).toBe(true);
    expect(api.loggedIn()).toBe(true);
    expect(sessionStorage.getItem('firmadoc-admin-token')).toBe(TOKEN);
  });

  it('un 401 cierra la sesión con «acceso denegado» y no guarda el token', async () => {
    const pending = api.login('token-incorrecto');
    http.expectOne(`${API}/events?limit=1`).flush({ detail: 'no autorizado' }, { status: 401, statusText: 'Unauthorized' });
    expect(await pending).toBe(false);
    expect(api.loggedIn()).toBe(false);
    expect(api.loginError()).toBe(DENIED);
    expect(sessionStorage.getItem('firmadoc-admin-token')).toBeNull();
  });

  it('otro error al ingresar se informa sin guardar el token', async () => {
    const pending = api.login(TOKEN);
    http.expectOne(`${API}/events?limit=1`).flush({ detail: 'base caída' }, { status: 500, statusText: 'Error' });
    expect(await pending).toBe(false);
    expect(api.loginError()).toBe('No se pudo ingresar: base caída');
  });

  it('request traduce el detail del servidor y envía el cuerpo como JSON', async () => {
    const pending = api.request('POST', '/trust-anchors', { certificate_pem: 'x' });
    const request = http.expectOne(`${API}/trust-anchors`);
    expect(request.request.body).toEqual({ certificate_pem: 'x' });
    request.flush({ detail: 'PEM inválido' }, { status: 422, statusText: 'Unprocessable' });
    await expect(pending).rejects.toThrow('PEM inválido');
  });

  it('fail muestra el error salvo si es un 401', () => {
    const add = vi.spyOn(toast, 'add');
    api.fail(new Error('algo falló'));
    expect(add).toHaveBeenCalledTimes(1);
    const pending = api.request('GET', '/events');
    http.expectOne(`${API}/events`).flush(null, { status: 401, statusText: 'Unauthorized' });
    return pending.catch((error) => {
      expect(isUnauthorized(error)).toBe(true);
      expect(error.message).toBe(UNAUTHORIZED);
      api.fail(error);
      expect(add).toHaveBeenCalledTimes(1);
    });
  });

  it('resume reanuda la sesión guardada en la pestaña', async () => {
    sessionStorage.setItem('firmadoc-admin-token', TOKEN);
    const pending = api.resume();
    http.expectOne(`${API}/events?limit=1`).flush({ items: [], total: 0 });
    await pending;
    expect(api.loggedIn()).toBe(true);
  });
});
