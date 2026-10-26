import { provideHttpClient } from '@angular/common/http';
import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import Aura from '@primeuix/themes/aura';
import { ConfirmationService, MessageService } from 'primeng/api';
import { providePrimeNG } from 'primeng/config';

/**
 * `nonce`: el que el servidor escribe en `ngCspNonce` al servir `/panel`. Angular lo usa para sus estilos y
 * PrimeNG para el tema que inyecta en tiempo de ejecución; sin él la CSP del panel los bloquearía.
 */
export function appConfig(nonce?: string): ApplicationConfig {
  return {
    providers: [
      provideBrowserGlobalErrorListeners(),
      provideHttpClient(),
      providePrimeNG({
        theme: { preset: Aura, options: { darkModeSelector: '[data-theme="dark"]', cssLayer: false } },
        csp: { nonce },
        ripple: false,
        translation: {
          accept: 'Sí',
          reject: 'No',
          choose: 'Elegir',
          upload: 'Cargar',
          cancel: 'Cancelar',
          pending: 'Pendiente',
          fileSizeTypes: ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'],
          emptyMessage: 'Sin resultados',
          emptyFilterMessage: 'Sin resultados',
        },
      }),
      MessageService,
      ConfirmationService,
    ],
  };
}
