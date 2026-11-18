import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Button } from 'primeng/button';
import { Card } from 'primeng/card';
import { InputText } from 'primeng/inputtext';
import { Message } from 'primeng/message';
import { AdminApi } from '../core/admin-api';

@Component({
  selector: 'app-login',
  imports: [FormsModule, InputText, Button, Card, Message],
  template: `
    <section class="login">
      <p-card styleClass="login-card">
        <div class="brand">
          <span class="brand-mark" aria-hidden="true"><i class="pi pi-verified"></i></span>
          <span>
            <strong class="brand-name">Firmadoc</strong>
            <span class="brand-sub">Panel de administración</span>
          </span>
        </div>
        <h2>Ingreso</h2>
        <form (ngSubmit)="submit()">
          <label for="token">Token de administración</label>
          <input pInputText id="token" name="token" type="password" autocomplete="off" required [(ngModel)]="token" />
          <p-button type="submit" label="Ingresar" icon="pi pi-sign-in" [loading]="busy()" styleClass="login-submit" />
        </form>
        @if (api.loginError(); as error) {
          <p-message severity="error" role="alert" id="login-error">{{ error }}</p-message>
        }
      </p-card>
    </section>
  `,
})
export class Login {
  readonly api = inject(AdminApi);
  readonly token = signal('');
  readonly busy = signal(false);

  async submit(): Promise<void> {
    const value = this.token().trim();
    if (!value || this.busy()) return;
    this.busy.set(true);
    try {
      if (await this.api.login(value)) this.token.set('');
    } finally {
      this.busy.set(false);
    }
  }
}
