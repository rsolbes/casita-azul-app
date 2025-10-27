import { Routes } from '@angular/router';

// 1. Importa tus COMPONENTES
import { LoginComponent } from './components/login/login.component';
import { AdminComponent } from './components/admin/admin.component';

// 2. Importa tu GUARDIA
import { AuthGuard } from './guards/auth.guard';

export const routes: Routes = [
  {
    path: 'login',
    component: LoginComponent // Solo le dices qué componente usar
  },
  {
    path: 'admin',
    component: AdminComponent,
    canActivate: [AuthGuard] // Le pones el guardia de seguridad
  },
  {
    path: '',
    redirectTo: '/login',
    pathMatch: 'full'
  }
];
