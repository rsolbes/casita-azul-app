import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

// Define an interface for the User object expected from the backend
export interface AdminUser {
  id: string;
  email: string;
  role?: string; // Role might come from profiles, fetched separately or joined
  created_at?: string;
  // Add other fields returned by supabase_admin.auth.admin.list_users() if needed
}

@Injectable({
  providedIn: 'root'
})
export class AdminService {
  private apiUrl = 'http://localhost:5000/api/admin/users'; // Base URL for admin user actions

  constructor(private http: HttpClient) {}

  // Fetch all users (requires admin)
  getUsers(): Observable<AdminUser[]> {
    return this.http.get<AdminUser[]>(this.apiUrl);
  }

  // Create a new user (requires admin)
  createUser(userData: { email: string; password?: string; role: string }): Observable<AdminUser> {
    // Password might be optional if you handle resets separately
    return this.http.post<AdminUser>(this.apiUrl, userData);
  }

  // Update a user's role (requires admin)
  updateUserRole(userId: string, role: string): Observable<any> {
    return this.http.put(`${this.apiUrl}/${userId}/role`, { role });
  }

  // Delete a user (requires admin)
  deleteUser(userId: string): Observable<any> {
    return this.http.delete(`${this.apiUrl}/${userId}`);
  }
}