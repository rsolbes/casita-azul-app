import { Injectable, Inject, PLATFORM_ID } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
// Importa switchMap y of de rxjs
import { Observable, BehaviorSubject, switchMap, tap, of, catchError } from 'rxjs';
import { isPlatformBrowser } from '@angular/common';

// Interfaz para el objeto User (asegúrate que coincida con lo que devuelve /api/user)
interface User {
  id: string;
  email: string;
  role?: string; // Propiedad rol añadida
}

// Interfaz para la respuesta inicial de /api/login
interface AuthResponse {
  access_token: string;
  refresh_token: string;
  user: { // Puede que no incluya el rol inicialmente
    id: string;
    email: string;
  };
}

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private apiUrl = 'https://casita-azul-backend.onrender.com/api';
  // Tipa explícitamente el BehaviorSubject
  private currentUserSubject = new BehaviorSubject<User | null>(null);
  public currentUser$ = this.currentUserSubject.asObservable();

  constructor(
    private http: HttpClient,
    @Inject(PLATFORM_ID) private platformId: Object
  ) {
    this.loadUserFromStorage();
  }

  // Getter para verificar si el usuario es admin
  get isAdmin(): boolean {
    return this.currentUserSubject.value?.role === 'admin';
  }

  register(email: string, password: string): Observable<any> {
    // La registración usualmente no devuelve el rol. Se obtiene al hacer login.
    return this.http.post(`${this.apiUrl}/register`, { email, password });
  }

  // --- FUNCIÓN LOGIN MODIFICADA ---
  // Ahora devuelve Observable<User | null>
  login(email: string, password: string): Observable<User | null> {
    return this.http.post<AuthResponse>(`${this.apiUrl}/login`, {
      email,
      password
    }).pipe(
      tap(response => {
        // Guarda los tokens inmediatamente
        if (isPlatformBrowser(this.platformId)) {
          localStorage.setItem('access_token', response.access_token);
          localStorage.setItem('refresh_token', response.refresh_token);
          // Ya no guardamos el usuario parcial aquí
        }
      }),
      // Usa switchMap para encadenar la llamada a fetchAndStoreUser
      // y devolver el resultado de esa llamada (el usuario completo)
      switchMap(response => this.fetchAndStoreUser(response.access_token)),
      catchError(error => {
        // Si el login falla (e.g., 401), limpia todo y devuelve null
        console.error("Login failed:", error);
        this.clearStorage();
        // Propaga el error para que el componente lo maneje
        throw error; // O puedes devolver of(null) si prefieres no propagar
      })
    );
  }

  // --- FUNCIÓN fetchAndStoreUser MODIFICADA ---
  // Ahora devuelve un Observable<User | null>
  fetchAndStoreUser(token: string | null): Observable<User | null> {
    // Si no hay token (puede pasar si se llama desde refresh y falló antes), limpia y devuelve null
    if (!token) {
      this.clearStorage();
      return of(null);
    }
    const headers = new HttpHeaders({
      'Authorization': `Bearer ${token}`
    });
    // Llama a /api/user para obtener los detalles completos
    return this.http.get<User>(`${this.apiUrl}/user`, { headers }).pipe(
      tap(user => {
        // Si se obtiene el usuario...
        if (user) {
          if (isPlatformBrowser(this.platformId)) {
            // Guarda el usuario completo (con rol) en localStorage
            localStorage.setItem('user', JSON.stringify(user));
            // Asegúrate que el token también esté guardado (importante si se llama desde refresh)
            localStorage.setItem('access_token', token);
          }
          // Actualiza el BehaviorSubject
          this.currentUserSubject.next(user);
        } else {
          // Si por alguna razón /api/user devuelve null o algo inesperado
          this.clearStorage();
        }
      }),
      catchError(error => {
         // Si la petición a /api/user falla (ej. token expirado después de refresh)
         console.error("Error fetching user details after login/refresh:", error);
         this.clearStorage();
         return of(null); // Devuelve null en caso de error al obtener el usuario
      })
    );
  }

  logout(): Observable<any> {
    const token = this.getToken();
    // Si no hay token, simplemente limpia el storage local y simula éxito
    if (!token && isPlatformBrowser(this.platformId)) {
      this.clearStorage();
      return of({}); // Devuelve un observable completado
    }
    // Si hay token, intenta invalidarlo en el backend
    const headers = new HttpHeaders({
      'Authorization': `Bearer ${token}`
    });

    return this.http.post(`${this.apiUrl}/logout`, {}, { headers }).pipe(
      tap({
        next: () => this.clearStorage(), // Limpia storage en éxito
        error: () => this.clearStorage() // Limpia storage también en error
      }),
      catchError(error => {
         // Aunque falle la llamada API (ej. token ya inválido), limpia localmente
         console.warn("Logout API call failed, clearing local storage anyway.", error);
         this.clearStorage();
         return of({}); // Devuelve éxito simulado para que la navegación funcione
      })
    );
  }

  // Devuelve el estado actual del usuario desde el BehaviorSubject
  getUser(): Observable<User | null> {
    return this.currentUser$;
  }

  refreshToken(): Observable<any> {
    if (!isPlatformBrowser(this.platformId)) {
      // No hacer nada si no estamos en el navegador (SSR/Pre-render)
      return of(null);
    }

    const refreshToken = localStorage.getItem('refresh_token');
    if (!refreshToken) {
      this.clearStorage(); // Limpia si no hay refresh token
      // Devuelve un observable que emite un error
      return new Observable(observer => observer.error('No refresh token'));
    }

    return this.http.post<{access_token: string, refresh_token?: string}>(`${this.apiUrl}/refresh`, {
      refresh_token: refreshToken
    }).pipe(
      tap((response) => {
        // Guarda los nuevos tokens (el refresh token puede ser opcional)
        if (isPlatformBrowser(this.platformId)) {
          localStorage.setItem('access_token', response.access_token);
          if (response.refresh_token) {
            localStorage.setItem('refresh_token', response.refresh_token);
          }
        }
      }),
      // Después de guardar tokens, usa switchMap para obtener el usuario actualizado
      switchMap(response => this.fetchAndStoreUser(response.access_token)),
      catchError((error) => {
        // Si el refresh falla (token inválido/expirado), limpia todo
        console.error("Refresh token failed:", error);
        this.clearStorage();
        // Propaga el error para que el interceptor o guardia lo maneje (ej. redirigir a login)
        throw error;
      })
    );
  }

  getToken(): string | null {
    if (isPlatformBrowser(this.platformId)) {
      return localStorage.getItem('access_token');
    }
    return null;
  }

  // Verifica si hay un usuario cargado Y un token
  isLoggedIn(): boolean {
    return !!this.currentUserSubject.value && !!this.getToken();
  }

  // Carga el usuario desde localStorage al iniciar el servicio
  private loadUserFromStorage(): void {
    if (isPlatformBrowser(this.platformId)) {
      const userString = localStorage.getItem('user');
      const token = localStorage.getItem('access_token'); // Verifica también el token
      if (userString && token) { // Solo carga si ambos existen
        try {
          const user = JSON.parse(userString) as User;
          this.currentUserSubject.next(user);
          // Opcional: Podrías verificar si el token sigue siendo válido aquí
          // llamando a this.fetchAndStoreUser(token), pero cuidado con bucles infinitos
          // si el refresh token también falla. Por ahora, confiamos en el guard.
        } catch (e) {
          console.error("Failed to parse user from storage", e);
          this.clearStorage(); // Limpia si el usuario guardado es inválido
        }
      } else {
        // Limpia si falta el usuario o el token
        this.clearStorage();
      }
    }
  }

  // Limpia tokens y usuario de localStorage y del BehaviorSubject
  private clearStorage(): void {
    if (isPlatformBrowser(this.platformId)) {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('user');
    }
    this.currentUserSubject.next(null); // Notifica que no hay usuario
  }
}