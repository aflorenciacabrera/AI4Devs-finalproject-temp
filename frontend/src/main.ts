import { bootstrapApplication } from '@angular/platform-browser';
import { App } from './app/app';
import { appConfig } from './app/app.config';

// El servidor reemplaza el marcador por un nonce al servir /panel; con `ng serve` queda el marcador y no hay CSP.
const PLACEHOLDER = 'FIRMADOC_NONCE';
const attribute = document.querySelector('app-root')?.getAttribute('ngCspNonce');
const nonce = attribute && attribute !== PLACEHOLDER ? attribute : undefined;

bootstrapApplication(App, appConfig(nonce)).catch((err) => console.error(err));
