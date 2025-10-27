import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

// Define an interface for the Agent object
export interface Agent {
  id?: number; // Optional for creation
  nombre: string;
  email: string;
  telefono?: string | null; // Optional
}

@Injectable({
  providedIn: 'root'
})
export class AgentService {
  private apiUrl = 'http://localhost:5000/api/agentes'; // Base URL for agent actions

  constructor(private http: HttpClient) {}

  // Fetch all agents (public or requires auth based on backend)
  getAgents(): Observable<Agent[]> {
    return this.http.get<Agent[]>(this.apiUrl);
  }

  // Create a new agent (requires admin)
  createAgent(agentData: Agent): Observable<{ id: number, status: string }> {
    return this.http.post<{ id: number, status: string }>(this.apiUrl, agentData);
  }

  // Update an existing agent (requires admin)
  updateAgent(id: number, agentData: Agent): Observable<any> {
    return this.http.put(`${this.apiUrl}/${id}`, agentData);
  }

  // Delete an agent (requires admin)
  deleteAgent(id: number): Observable<any> {
    return this.http.delete(`${this.apiUrl}/${id}`);
  }
}