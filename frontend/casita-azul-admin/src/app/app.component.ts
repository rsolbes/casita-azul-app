import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { PropertyService, Property, PropertyImage, CatalogosApiResponse } from './services/property.service';
import { forkJoin } from 'rxjs';

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

  catalogos: CatalogosApiResponse = {};
  newProperty: Property = this.createEmptyProperty();

  // Variables para manejo de imágenes
  selectedFiles: File[] = [];
  uploadingImages = false;
  editingImages: PropertyImage[] = [];

  constructor(private propertyService: PropertyService) {}

  ngOnInit(): void {
    this.loadData();
  }

  createEmptyProperty(): Property {
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
      validado_por_usuario_id: null,
      imagenes: []
    };
  }

  loadData() {
    this.isLoading = true;
    this.errorMessage = '';

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
    this.editingProperty = JSON.parse(JSON.stringify(prop));
    this.editingImages = prop.imagenes ? [...prop.imagenes] : [];
    this.selectedFiles = [];
  }

  saveChanges() {
    if (!this.editingProperty) return;

    this.normalizeNullValues(this.editingProperty);

    this.propertyService.update(this.editingProperty).subscribe({
      next: () => {
        // Si hay archivos seleccionados, subirlos
        if (this.selectedFiles.length > 0 && this.editingProperty?.id) {
          this.uploadSelectedImages(this.editingProperty.id, () => {
            this.loadData();
            this.editingProperty = null;
            this.selectedFiles = [];
          });
        } else {
          this.loadData();
          this.editingProperty = null;
        }
      },
      error: (err) => {
        alert('Error al actualizar propiedad');
        console.error(err);
      }
    });
  }

  cancelEdit() {
    this.editingProperty = null;
    this.selectedFiles = [];
    this.editingImages = [];
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
    this.normalizeNullValues(this.newProperty);

    this.propertyService.add(this.newProperty).subscribe({
      next: (response) => {
        const newId = response.id;

        // Si hay archivos seleccionados, subirlos
        if (this.selectedFiles.length > 0 && newId) {
          this.uploadSelectedImages(newId, () => {
            this.loadData();
            this.newProperty = this.createEmptyProperty();
            this.selectedFiles = [];
          });
        } else {
          this.loadData();
          this.newProperty = this.createEmptyProperty();
        }
      },
      error: (err) => {
        alert('Error al agregar propiedad');
        console.error(err);
      }
    });
  }

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

  getCatalogoNombre(catalogoKey: keyof CatalogosApiResponse, id: number | null | undefined): string {
    if (!id || !this.catalogos[catalogoKey]) {
      return 'N/A';
    }

    const item = this.catalogos[catalogoKey].find(c => c.id === id);
    return item ? item.nombre : 'N/A';
  }

  // --- Métodos para manejo de imágenes ---

  onFileSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files) {
      this.selectedFiles = Array.from(input.files);
    }
  }

  uploadSelectedImages(propiedadId: number, callback: () => void) {
    if (this.selectedFiles.length === 0) {
      callback();
      return;
    }

    this.uploadingImages = true;
    let uploadedCount = 0;

    this.selectedFiles.forEach((file, index) => {
      const esPrincipal = index === 0 && (!this.editingImages || this.editingImages.length === 0);

      this.propertyService.uploadImage(propiedadId, file, esPrincipal).subscribe({
        next: () => {
          uploadedCount++;
          if (uploadedCount === this.selectedFiles.length) {
            this.uploadingImages = false;
            callback();
          }
        },
        error: (err) => {
          console.error('Error al subir imagen:', err);
          uploadedCount++;
          if (uploadedCount === this.selectedFiles.length) {
            this.uploadingImages = false;
            callback();
          }
        }
      });
    });
  }

  deleteImage(propiedadId: number, imagenId: number) {
    if (!confirm('¿Eliminar esta imagen?')) return;

    this.propertyService.deleteImage(propiedadId, imagenId).subscribe({
      next: () => {
        // Actualizar la lista de imágenes localmente
        this.editingImages = this.editingImages.filter(img => img.id !== imagenId);

        // Actualizar en la propiedad en edición
        if (this.editingProperty) {
          this.editingProperty.imagenes = this.editingImages;
        }

        // Recargar datos
        this.loadData();
      },
      error: (err) => {
        alert('Error al eliminar imagen');
        console.error(err);
      }
    });
  }

  setPrincipal(propiedadId: number, imagenId: number) {
    this.propertyService.setPrincipalImage(propiedadId, imagenId).subscribe({
      next: () => {
        // Actualizar la lista de imágenes localmente
        this.editingImages.forEach(img => {
          img.es_principal = img.id === imagenId;
        });

        this.loadData();
      },
      error: (err) => {
        alert('Error al establecer imagen principal');
        console.error(err);
      }
    });
  }

  getPrincipalImage(property: Property): string | null {
    if (!property.imagenes || property.imagenes.length === 0) {
      return null;
    }

    const principal = property.imagenes.find(img => img.es_principal);
    return principal ? principal.url : property.imagenes[0].url;
  }

  removeSelectedFile(index: number) {
    this.selectedFiles.splice(index, 1);
  }
}
