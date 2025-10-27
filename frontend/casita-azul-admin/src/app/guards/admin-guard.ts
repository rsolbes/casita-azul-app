import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';
import { map, take } from 'rxjs/operators';
import { Observable } from 'rxjs';

export const AdminGuard: CanActivateFn = (route, state): Observable<boolean> | Promise<boolean> | boolean => {
  const authService = inject(AuthService);
  const router = inject(Router);

  // Check login status first
  if (!authService.isLoggedIn()) {
    router.navigate(['/login']);
    return false;
  }

  // Check if the current user is an admin
  // Use take(1) to get the current value and complete
  return authService.currentUser$.pipe(
    take(1),
    map(user => {
      if (user?.role === 'admin') {
        return true;
      } else {
        // Redirect non-admins (e.g., to the main admin page or a 'denied' page)
        console.warn('Access denied: Admin role required.');
        router.navigate(['/admin']); // Or another appropriate route
        return false;
      }
    })
  );
};