import { HttpClient, HttpErrorResponse, HttpHeaders } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import { MessageService } from 'primeng/api';
import { firstValueFrom } from 'rxjs';

export const API = '/api/v1/admin';
const KEY = 'firmadoc-admin-token';
export const UNAUTHORIZED = 'unauthorized';
export const DENIED = 'Acceso denegado: el token de administración no es válido.';

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

export function isUnauthorized(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401;
}

/**
 * Nombre de archivo de una cabecera `Content-Disposition`: primero `filename*` (UTF-8, el nombre exacto,
 * con acentos), si no `filename` (el fallback ASCII). `null` si no hay cabecera o no se puede leer.
 */
export function filenameFrom(disposition: string | null): string | null {
  if (!disposition) return null;
  const exact = /filename\*=UTF-8''([^;]+)/i.exec(disposition);
  if (exact) {
    try {
      return decodeURIComponent(exact[1].trim());
    } catch {
      /* mal codificado: se usa el fallback */
    }
  }
  const plain = /filename="?([^";]+)"?/i.exec(disposition);
  return plain ? plain[1] : null;
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function readStored(): string | null {
  try {
    return sessionStorage.getItem(KEY);
  } catch {
    return null;
  }
}

function store(value: string | null): void {
  try {
    if (value) sessionStorage.setItem(KEY, value);
    else sessionStorage.removeItem(KEY);
  } catch {
    /* sin almacenamiento: la sesión dura lo que dure la página */
  }
}

type Method = 'GET' | 'POST' | 'PATCH' | 'DELETE';

/**
 * Cliente de la API de administración. El token vive en memoria y en `sessionStorage` (se borra al cerrar
 * la pestaña) y viaja solo en `Authorization: Bearer`; un `401` cierra la sesión.
 */
@Injectable({ providedIn: 'root' })
export class AdminApi {
  private readonly http = inject(HttpClient);
  private readonly toast = inject(MessageService);
  private token: string | null = null;

  readonly loggedIn = signal(false);
  /** Mensaje para la pantalla de ingreso (token inválido, sesión cerrada por el servidor). */
  readonly loginError = signal('');

  /** Reanuda la sesión guardada en esta pestaña, si la hay. */
  async resume(): Promise<void> {
    const saved = readStored();
    if (saved) await this.login(saved);
  }

  async login(token: string): Promise<boolean> {
    this.token = token;
    try {
      await this.request('GET', '/events?limit=1');
    } catch (error) {
      if (!isUnauthorized(error)) this.logout('No se pudo ingresar: ' + errorMessage(error));
      return false; // con 401, request() ya cerró la sesión con el mensaje de acceso denegado
    }
    store(token);
    this.loginError.set('');
    this.loggedIn.set(true);
    return true;
  }

  logout(message = ''): void {
    this.token = null;
    store(null);
    this.loggedIn.set(false);
    this.loginError.set(message);
  }

  async request<T>(method: Method, path: string, body?: unknown): Promise<T> {
    try {
      return await firstValueFrom(this.http.request<T>(method, API + path, { body, headers: this.headers() }));
    } catch (error) {
      throw this.translate(error);
    }
  }

  /** Descarga un archivo (PDF de una versión) con el token en la cabecera; conserva el nombre original. */
  async download(path: string): Promise<{ blob: Blob; filename: string | null }> {
    try {
      const response = await firstValueFrom(
        this.http.get(API + path, { headers: this.headers(), observe: 'response', responseType: 'blob' }),
      );
      return { blob: response.body ?? new Blob(), filename: filenameFrom(response.headers.get('content-disposition')) };
    } catch (error) {
      throw this.translate(error);
    }
  }

  /** Muestra el error en pantalla, salvo que sea un 401 (la sesión ya se cerró con su propio mensaje). */
  fail(error: unknown, summary = 'No se pudo completar la acción'): void {
    if (isUnauthorized(error)) return;
    this.toast.add({ severity: 'error', summary, detail: errorMessage(error), life: 8000 });
  }

  ok(detail: string): void {
    this.toast.add({ severity: 'success', summary: 'Listo', detail, life: 4000 });
  }

  private headers(): HttpHeaders {
    return new HttpHeaders({ Authorization: 'Bearer ' + (this.token ?? '') });
  }

  private translate(error: unknown): Error {
    if (!(error instanceof HttpErrorResponse)) return error instanceof Error ? error : new Error(String(error));
    if (error.status === 401) {
      this.logout(DENIED);
      return new ApiError(UNAUTHORIZED, 401);
    }
    if (error.status === 0) return new ApiError('No se pudo conectar con el servidor.', 0);
    const body: unknown = error.error;
    const detail =
      body && typeof body === 'object' && 'detail' in body ? String((body as { detail: unknown }).detail) : null;
    return new ApiError(detail || 'Error ' + error.status, error.status);
  }
}
