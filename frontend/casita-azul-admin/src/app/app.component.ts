import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { PropertyService, Property, CatalogosApiResponse } from './services/property.service';
import { forkJoin } from 'rxjs'; // Importante para peticiones en paralelo

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css']
})
export class AppComponent implements OnInit {
  title = 'Administración de Casita Azul';
  isLoading = false;
  errorMessage = '';
  properties: Property[] = [];
  editingProperty: Property | null = null;
  
  // Objeto para almacenar todos los catálogos
  catalogos: CatalogosApiResponse = {};

  // Propiedad 'plantilla' para el formulario de agregar
  newProperty: Property = this.createEmptyProperty();

  constructor(private propertyService: PropertyService) {}

  ngOnInit(): void {
    this.loadData();
  }

  createEmptyProperty(): Property {
    // Devuelve un objeto limpio para el formulario de 'nuevo'
    return {
      titulo: '',
      descripcion: null,
      precio: null,
      precio_alquiler: null,
      valor_administracion: null,
      habitaciones: 0,
      alcobas: 0,
      banos: 0,
      banos_medios: 0,
      estacionamientos: 0,
      anio_construccion: null,
      piso: null,
      m2_terreno: 0,
      m2_construccion: 0,
      m2_privada: 0,
      direccion: null,
      codigo_postal: null,
      lat: null,
      lng: null,
      registro_publico: null,
      convenio_url: null,
      convenio_validado: false,
      tipo_negocio_id: null,
      tipo_propiedad_id: null,
      estado_publicacion_id: null,
      captado_por_agente_id: null,
      moneda_id: null,
      frecuencia_alquiler_id: null,
      estado_fisico_id: null,
      estado_id: null,
      ciudad_id: null,
      zona_id: null,
      agente_id: null,
      agente_externo_id: null,
      validado_por_usuario_id: null
    };
  }

  loadData() {
    this.isLoading = true;
    this.errorMessage = '';

    // Usamos forkJoin para esperar a que ambas peticiones terminen
    forkJoin({
      props: this.propertyService.getAll(),
      cats: this.propertyService.getCatalogos()
    }).subscribe({
      next: (data) => {
        this.properties = data.props.properties || [];
        this.catalogos = data.cats;
        this.isLoading = false;
      },
      error: (err) => {
        this.errorMessage = 'Error al cargar datos. Revisa la consola (backend y frontend).';
        console.error(err);
        this.isLoading = false;
      }
    });
  }

  editProperty(prop: Property) {
    // Creamos una copia profunda para no modificar la tabla directamente
    this.editingProperty = JSON.parse(JSON.stringify(prop));
  }

  saveChanges() {
    if (!this.editingProperty) return;
    
    // Convertimos IDs de select (que pueden ser string) a null si están vacíos
    this.normalizeNullValues(this.editingProperty);

    this.propertyService.update(this.editingProperty).subscribe({
      next: () => {
        this.loadData(); // Recarga todo
        this.editingProperty = null;
      },
      error: (err) => {
        alert('Error al actualizar propiedad');
        console.error(err);
      }
    });
  }

  cancelEdit() {
    this.editingProperty = null;
  }

  deleteProperty(id: number | undefined) {
    if (!id || !confirm('¿Seguro que deseas eliminar esta propiedad? (Borrado lógico)')) return;
    
    this.propertyService.delete(id).subscribe({
      next: () => this.loadData(),
      error: (err) => {
        alert('Error al eliminar propiedad');
        console.error(err);
      }
    });
  }

  addProperty() {
    // Convertimos IDs de select (que pueden ser string) a null si están vacíos
    this.normalizeNullValues(this.newProperty);

    this.propertyService.add(this.newProperty).subscribe({
      next: () => {
        this.loadData(); // Recarga todo
        this.newProperty = this.createEmptyProperty(); // Resetea el formulario
      },
      error: (err) => {
        alert('Error al agregar propiedad');
        console.error(err);
      }
    });
  }
  
  // Función útil para manejar los <select>
  // Un <select> con valor "" (string vacío) debe ser guardado como 'null' en la DB
  normalizeNullValues(prop: Property) {
    const keys: (keyof Property)[] = [
      'tipo_negocio_id', 'tipo_propiedad_id', 'estado_publicacion_id', 
      'captado_por_agente_id', 'moneda_id', 'frecuencia_alquiler_id', 
      'estado_fisico_id', 'estado_id', 'ciudad_id', 'zona_id', 'agente_id', 
      'agente_externo_id', 'validado_por_usuario_id'
    ];
    
    for (const key of keys) {
      if (prop[key] === '' || prop[key] === undefined) {
        (prop as any)[key] = null;
      }
    }
  }

  /**
   * Función para traducir un ID a su nombre usando el objeto de catálogos.
   * @param catalogoKey El nombre del catálogo (ej: 'tipos_negocio', 'ciudades')
   * @param id El ID que queremos traducir
   * @returns El nombre correspondiente o 'N/A' si no se encuentra.
   */
  getCatalogoNombre(catalogoKey: keyof CatalogosApiResponse, id: number | null | undefined): string {
    // Si no hay ID o el catálogo no ha cargado, devolvemos 'N/A'
    if (!id || !this.catalogos[catalogoKey]) {
      return 'N/A';
    }
    
    // Buscamos el item en el arreglo del catálogo
    const item = this.catalogos[catalogoKey].find(c => c.id === id);
    
    // Devolvemos el nombre si se encontró, o 'N/A'
    return item ? item.nombre : 'N/A';
  }
}