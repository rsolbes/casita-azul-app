// frontend/casita-azul-admin/src/app/services/dashboard.service.ts
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface DashboardStats {
  total_propiedades: number;
  propiedades_publicadas: number;
  total_visitas: number;
  propiedad_mas_visitada: {
    id: number;
    titulo: string;
    visitas: number;
    direccion: string;
  } | null;
  por_tipo_negocio: Array<{ nombre: string; cantidad: number }>;
  por_tipo_propiedad: Array<{ nombre: string; cantidad: number }>;
  por_estado_publicacion: Array<{ nombre: string; cantidad: number }>;
  top_ciudades: Array<{ ciudad: string; estado: string; cantidad: number }>;
  top_agentes: Array<{ nombre: string; email: string; propiedades_captadas: number }>;
  precios: {
    precio_promedio_venta: number;
    precio_promedio_alquiler: number;
    precio_min_venta: number;
    precio_max_venta: number;
    precio_min_alquiler: number;
    precio_max_alquiler: number;
  } | null;
  propiedades_nuevas_semana: number;
  imagenes: {
    con_imagenes: number;
    sin_imagenes: number;
  } | null;
}

export interface RecentActivity {
  id: number;
  titulo: string;
  created_at: string;
  updated_at: string | null;
  captado_por: string | null;
  estado: string;
}

@Injectable({
  providedIn: 'root'
})
export class DashboardService {
  private apiUrl = 'https://casita-azul-app.onrender.com/api/dashboard';

  constructor(private http: HttpClient) {}

  getStats(): Observable<DashboardStats> {
    return this.http.get<DashboardStats>(`${this.apiUrl}/stats`);
  }

  getRecentActivity(): Observable<RecentActivity[]> {
    return this.http.get<RecentActivity[]>(`${this.apiUrl}/recent-activity`);
  }
}
