import { Injectable, Inject, PLATFORM_ID } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable, BehaviorSubject, map } from 'rxjs'; // Import map
import { tap } from 'rxjs/operators';
import { isPlatformBrowser } from '@angular/common';

// Add 'role' to the user object interface
interface User {
  id: string;
  email: string;
  role?: string; // Add role property
}

interface AuthResponse {
  access_token: string;
  refresh_token: string;
  user: User; // Use the User interface
}

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private apiUrl = 'http://localhost:5000/api'; // Ensure this matches your backend
  // Explicitly type the BehaviorSubject
  private currentUserSubject = new BehaviorSubject<User | null>(null);
  public currentUser$ = this.currentUserSubject.asObservable();

  constructor(
    private http: HttpClient,
    @Inject(PLATFORM_ID) private platformId: Object
  ) {
    this.loadUserFromStorage();
  }

  // Helper getter for admin check
  get isAdmin(): boolean {
    return this.currentUserSubject.value?.role === 'admin';
  }

  register(email: string, password: string): Observable<any> {
    // Role is assigned by backend logic (default 'user' or admin-created)
    return this.http.post(`${this.apiUrl}/register`, { email, password });
  }

  login(email: string, password: string): Observable<AuthResponse> {
    return this.http.post<AuthResponse>(`${this.apiUrl}/login`, {
      email,
      password
    }).pipe(
      tap(response => {
        // Store tokens immediately
        if (isPlatformBrowser(this.platformId)) {
          localStorage.setItem('access_token', response.access_token);
          localStorage.setItem('refresh_token', response.refresh_token);
        }
        // Fetch full user details including role *after* storing tokens
        this.fetchAndStoreUser(response.access_token);
      })
    );
  }

  // New function to fetch user data (including role) and store it
  fetchAndStoreUser(token: string): void {
    const headers = new HttpHeaders({
      'Authorization': `Bearer ${token}`
    });

    // Don't return observable, just execute
    this.http.get<User>(`${this.apiUrl}/user`, { headers }).subscribe({
      next: (user) => {
        if (isPlatformBrowser(this.platformId)) {
          localStorage.setItem('user', JSON.stringify(user)); // Store full user object with role
        }
        this.currentUserSubject.next(user);
      },
      error: (err) => {
        console.error("Failed to fetch user data", err);
        this.clearStorage(); // Log out if user fetch fails
      }
    });
  }


  logout(): Observable<any> {
    const token = this.getToken();
    // If no token, just clear storage and log out locally
    if (!token) {
        this.clearStorage();
        return new Observable(observer => { observer.next({}); observer.complete(); });
    }
    const headers = new HttpHeaders({
      'Authorization': `Bearer ${token}`
    });

    return this.http.post(`${this.apiUrl}/logout`, {}, { headers }).pipe(
      tap({
        next: () => this.clearStorage(),
        // Also clear storage on error (e.g., expired token)
        error: () => this.clearStorage()
      })
    );
  }

  // Modified getUser to return User type
  getUser(): Observable<User | null> {
    // This now primarily relies on the BehaviorSubject
    return this.currentUser$;
  }


  refreshToken(): Observable<any> {
    if (!isPlatformBrowser(this.platformId)) {
      return new Observable(observer => observer.complete());
    }

    const refreshToken = localStorage.getItem('refresh_token');
    if (!refreshToken) {
         this.clearStorage(); // Ensure logout if refresh token is missing
         return new Observable(observer => observer.error('No refresh token'));
    }

    return this.http.post<{access_token: string, refresh_token: string}>(`${this.apiUrl}/refresh`, {
      refresh_token: refreshToken
    }).pipe(
      tap(
        (response) => {
          if (isPlatformBrowser(this.platformId)) {
            localStorage.setItem('access_token', response.access_token);
            // Update refresh token if backend sends a new one
            if (response.refresh_token) {
               localStorage.setItem('refresh_token', response.refresh_token);
            }
            // Re-fetch user details with the new token to update role/info
            this.fetchAndStoreUser(response.access_token);
          }
        },
        (error) => {
          // If refresh fails (e.g., token expired/invalid), log out the user
          console.error("Refresh token failed:", error);
          this.clearStorage();
          // Optionally redirect to login here via Router if needed globally
        }
      )
    );
  }

  getToken(): string | null {
    if (isPlatformBrowser(this.platformId)) {
      return localStorage.getItem('access_token');
    }
    return null;
  }

  isLoggedIn(): boolean {
    // Check subject value instead of just token for more reliability
    return !!this.currentUserSubject.value && !!this.getToken();
  }

  private loadUserFromStorage(): void {
    if (isPlatformBrowser(this.platformId)) {
      const userString = localStorage.getItem('user');
      const token = localStorage.getItem('access_token');
      if (userString && token) {
        try {
          const user = JSON.parse(userString) as User;
          this.currentUserSubject.next(user);
          // Optional: Verify token is still valid by calling /user endpoint again
          this.fetchAndStoreUser(token);
        } catch (e) {
            console.error("Failed to parse user from storage", e);
            this.clearStorage();
        }
      } else if (token) {
        // Has token but no user object, fetch it
        this.fetchAndStoreUser(token);
      }
      else {
          this.clearStorage(); // Ensure clean state if token or user is missing
      }
    }
  }

  private clearStorage(): void {
    if (isPlatformBrowser(this.platformId)) {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('user');
    }
    this.currentUserSubject.next(null);
  }
}