import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

// Interfaz para las imágenes
export interface PropertyImage {
  id: number;
  url: string;
  nombre_archivo: string;
  es_principal: boolean;
  orden: number;
}

// Interfaz de Propiedad COMPLETA
export interface Property {
  id?: number;
  titulo: string;
  descripcion?: string | null;
  precio?: number | null;
  precio_alquiler?: number | null;
  valor_administracion?: number | null;
  habitaciones?: number | null;
  alcobas?: number | null;
  banos?: number | null;
  banos_medios?: number | null;
  estacionamientos?: number | null;
  anio_construccion?: number | null;
  piso?: string | null;
  m2_terreno?: number | null;
  m2_construccion?: number | null;
  m2_privada?: number | null;
  direccion?: string | null;
  codigo_postal?: string | null;
  lat?: number | null;
  lng?: number | null;
  visitas?: number | null;
  registro_publico?: string | null;
  convenio_url?: string | null;
  convenio_validado?: boolean | null; // Cambiado a boolean (no null)
  fecha_validacion?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  deleted_at?: string | null;
  tipo_negocio_id?: number | null;
  tipo_propiedad_id?: number | null;
  estado_publicacion_id?: number | null;
  captado_por_agente_id?: number | null;
  moneda_id?: number | null;
  frecuencia_alquiler_id?: number | null;
  estado_fisico_id?: number | null;
  estado_id?: number | null;
  ciudad_id?: number | null;
  zona_id?: number | null;
  agente_id?: number | null;
  agente_externo_id?: number | null;
  validado_por_usuario_id?: number | null;
  imagenes?: PropertyImage[] | null;
}

// Interfaz para la respuesta de la API de propiedades
export interface PropertiesApiResponse {
  properties: Property[];
}

// --- Interfaces Corregidas para Catálogos ---
// Interfaz base para ítems de catálogo
interface CatalogoItem {
  id: number;
  nombre: string;
}

// Interfaz específica para Agente (si devuelve más campos)
interface AgenteItem extends CatalogoItem {
  email?: string;
  telefono?: string | null;
}

// Interfaz específica para Moneda (solo id y nombre por ahora)
interface MonedaItem extends CatalogoItem {
  // codigo?: string; // Comentado - No devuelto por el backend actual
  // simbolo?: string; // Comentado - No devuelto por el backend actual
}


// Interfaz para la respuesta COMPLETA de la API de catálogos
export interface CatalogosApiResponse {
  agentes?: AgenteItem[]; // Usa la interfaz específica si aplica
  agentes_externos?: CatalogoItem[];
  ciudades?: CatalogoItem[];
  estados?: CatalogoItem[];
  estados_fisicos?: CatalogoItem[];
  estados_publicacion?: CatalogoItem[];
  frecuencias_alquiler?: CatalogoItem[];
  monedas?: MonedaItem[]; // Usa la interfaz MonedaItem corregida
  tipos_negocio?: CatalogoItem[];
  tipos_propiedad?: CatalogoItem[];
  zonas?: CatalogoItem[];
  // Firma de índice para permitir acceso genérico sin error TS
  [key: string]: CatalogoItem[] | AgenteItem[] | MonedaItem[] | undefined;
}
// --- Fin Interfaces Corregidas ---


@Injectable({
  providedIn: 'root'
})
export class PropertyService {
  // Asegúrate que esta URL apunte a tu backend Flask
  private apiUrl = 'https://casita-azul-backend.onrender.com/api';
  
  constructor(private http: HttpClient) {}

  // --- Métodos de Propiedades ---
  getAll(): Observable<PropertiesApiResponse> {
    return this.http.get<PropertiesApiResponse>(`${this.apiUrl}/propiedades`);
  }

  getById(id: number): Observable<Property> {
    return this.http.get<Property>(`${this.apiUrl}/propiedades/${id}`);
  }

  // Devuelve Observable<any> o una interfaz más específica si tu backend la define
  add(property: Property): Observable<{ id: number; status: string }> {
    return this.http.post<{ id: number; status: string }>(`${this.apiUrl}/propiedades`, property);
  }

  update(property: Property): Observable<any> {
    // Asegúrate de enviar el ID correcto en la URL
    return this.http.put(`${this.apiUrl}/propiedades/${property.id}`, property);
  }

  delete(id: number): Observable<any> {
    return this.http.delete(`${this.apiUrl}/propiedades/${id}`);
  }

  // --- Métodos de Catálogos ---
  getCatalogos(): Observable<CatalogosApiResponse> {
    return this.http.get<CatalogosApiResponse>(`${this.apiUrl}/catalogos`);
  }

  // --- Métodos de Imágenes ---
  uploadImage(propiedadId: number, file: File, esPrincipal: boolean = false): Observable<any> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('es_principal', esPrincipal.toString());

    return this.http.post(`${this.apiUrl}/propiedades/${propiedadId}/imagenes`, formData);
  }

  deleteImage(propiedadId: number, imagenId: number): Observable<any> {
    return this.http.delete(`${this.apiUrl}/propiedades/${propiedadId}/imagenes/${imagenId}`);
  }

  setPrincipalImage(propiedadId: number, imagenId: number): Observable<any> {
    // El backend espera un cuerpo vacío ({}), así que lo enviamos
    return this.http.put(`${this.apiUrl}/propiedades/${propiedadId}/imagenes/${imagenId}/principal`, {});
  }
}