import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Button } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Message } from 'primeng/message';
import { AdminApi } from '../core/admin-api';

@Component({
  selector: 'app-login',
  imports: [FormsModule, InputText, Button, Message],
  template: `
    <section class="login">
      <h2>Ingreso</h2>
      <form (ngSubmit)="submit()">
        <label for="token">Token de administración</label>
        <input pInputText id="token" name="token" type="password" autocomplete="off" required [(ngModel)]="token" />
        <p-button type="submit" label="Ingresar" [loading]="busy()" />
      </form>
      @if (api.loginError(); as error) {
        <p-message severity="error" role="alert" id="login-error">{{ error }}</p-message>
      }
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
