import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';

// Define an interface for the User object expected from the backend
export interface AdminUser {
  id: string;
  email: string;
  role?: string;
  created_at?: string;
}

@Injectable({
  providedIn: 'root'
})
export class AdminService {
  private apiUrl = 'https://casita-azul-app.onrender.com/api/admin/users';

  constructor(private http: HttpClient) {}

  /**
   * Obtiene el token de autorización del localStorage
   */
  private getAuthHeaders(): HttpHeaders {
    const token = localStorage.getItem('access_token');
    return new HttpHeaders({
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    });
  }

  /**
   * Fetch all users (requires admin)
   */
  getUsers(): Observable<AdminUser[]> {
    const headers = this.getAuthHeaders();
    return this.http.get<AdminUser[]>(this.apiUrl, { headers });
  }

  /**
   * Create a new user (requires admin)
   */
  createUser(userData: { email: string; password: string; role: string }): Observable<AdminUser> {
    const headers = this.getAuthHeaders();
    return this.http.post<AdminUser>(this.apiUrl, userData, { headers });
  }

  /**
   * Update a user's role (requires admin)
   */
  updateUserRole(userId: string, role: string): Observable<any> {
    const headers = this.getAuthHeaders();
    return this.http.put(`${this.apiUrl}/${userId}/role`, { role }, { headers });
  }

  /**
   * Delete a user (requires admin)
   */
  deleteUser(userId: string): Observable<any> {
    const headers = this.getAuthHeaders();
    return this.http.delete(`${this.apiUrl}/${userId}`, { headers });
  }
}