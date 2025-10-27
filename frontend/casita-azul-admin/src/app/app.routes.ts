import { Routes } from '@angular/router';

// Import components
import { LoginComponent } from './components/login/login.component';
import { AdminComponent } from './components/admin/admin.component';
import { ManageUsersComponent } from './components/manage-users/manage-users.component';
import { ManageAgentsComponent } from './components/manage-agents/manage-agents.component';

// Import guards
import { AuthGuard } from './guards/auth.guard';
import { AdminGuard } from './guards/admin-guard'; // Usa el nombre de archivo con guión

export const routes: Routes = [
  {
    path: 'login',
    component: LoginComponent
  },
  {
    path: 'admin', // Main property management page
    component: AdminComponent,
    canActivate: [AuthGuard]
  },
  {
    path: 'admin/users', // User management page
    component: ManageUsersComponent,
    canActivate: [AuthGuard, AdminGuard] // MUST be logged in AND admin
  },
  {
    path: 'admin/agents', // Agent management page
    component: ManageAgentsComponent,
    canActivate: [AuthGuard, AdminGuard] // MUST be logged in AND admin
  },
  {
    path: '',
    redirectTo: '/login', // Default redirect
    pathMatch: 'full'
  },
  {
    path: '**', // Catch-all route
    redirectTo: '/login'
  }
];