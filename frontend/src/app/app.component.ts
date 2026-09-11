import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';

import { AvisosComponent } from '@shared/componentes/avisos.component';

@Component({
  selector: 'ute-raiz',
  standalone: true,
  imports: [RouterOutlet, AvisosComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <router-outlet />
    <ute-avisos />
  `,
})
export class AppComponent {}
