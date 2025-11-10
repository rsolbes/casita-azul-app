// frontend/casita-azul-admin/src/app/app.routes.ts
import { Routes } from '@angular/router';

// Import components
import { LoginComponent } from './components/login/login.component';
import { DashboardComponent } from './components/dashboard/dashboard.component';
import { AdminComponent } from './components/admin/admin.component';
import { ManageUsersComponent } from './components/manage-users/manage-users.component';
import { ManageAgentsComponent } from './components/manage-agents/manage-agents.component';

// Import guards
import { AuthGuard } from './guards/auth.guard';
import { AdminGuard } from './guards/admin-guard';

export const routes: Routes = [
  {
    path: 'login',
    component: LoginComponent
  },
  {
    path: 'dashboard',
    component: DashboardComponent,
    canActivate: [AuthGuard]
  },
  {
    path: 'admin', // Main property management page
    component: AdminComponent,
    canActivate: [AuthGuard]
  },
  {
    path: 'admin/users', // User management page
    component: ManageUsersComponent,
    canActivate: [AuthGuard, AdminGuard]
  },
  {
    path: 'admin/agents', // Agent management page
    component: ManageAgentsComponent,
    canActivate: [AuthGuard, AdminGuard]
  },
  {
    path: '',
    redirectTo: '/dashboard', // Changed to dashboard
    pathMatch: 'full'
  },
  {
    path: '**',
    redirectTo: '/dashboard' // Changed to dashboard
  }
];
