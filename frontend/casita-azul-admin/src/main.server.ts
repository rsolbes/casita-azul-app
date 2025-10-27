import {
  BootstrapContext, // 1. Asegúrate de importar esto
  bootstrapApplication
} from '@angular/platform-browser';
import { config } from './app/app.config.server';
import { AppComponent } from './app/app.component';

// 2. Asegúrate de que la función 'bootstrap' reciba el 'context'
const bootstrap = (context: BootstrapContext) =>
  bootstrapApplication(AppComponent, config, context); // 3. Y de pasarlo aquí

export default bootstrap;
