// auth-interceptor.ts
import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { AuthService } from '../services/auth.service';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const authService = inject(AuthService);
  const token = authService.getToken();
  
  // Lista de dominios que requieren autenticación
  const apiDomains = [
    'https://casita-azul-app.onrender.com',
    'http://localhost:5000' // Para desarrollo local
  ];

  // Verifica si la petición es a alguno de tus APIs
  const requiresAuth = apiDomains.some(domain => req.url.startsWith(domain));

  if (token && requiresAuth) {
    const cloned = req.clone({
      setHeaders: {
        Authorization: `Bearer ${token}`
      }
    });
    return next(cloned);
  }
  
  return next(req);
};