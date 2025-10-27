// src/app/components/admin/admin.component.ts
import { Component, OnInit } from '@angular/core';
import { Router, RouterLink } from '@angular/router'; // Import RouterLink
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { PropertyService, Property, PropertyImage, CatalogosApiResponse } from '../../services/property.service';
import { AuthService } from '../../services/auth.service';
import { forkJoin, Observable } from 'rxjs'; // Import Observable

@Component({
  selector: 'app-admin',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink], // Add RouterLink
  templateUrl: './admin.component.html',
  styleUrls: ['./admin.component.css']
})
export class AdminComponent implements OnInit {
  title = 'Administración de Propiedades'; // Title adjusted
  isLoading = false;
  errorMessage = '';
  properties: Property[] = [];
  editingProperty: Property | null = null;

  catalogos: CatalogosApiResponse = {};
  newProperty: Property = this.createEmptyProperty();

  selectedFiles: File[] = [];
  uploadingImages = false;
  editingImages: PropertyImage[] = [];

  // Information for the logged-in user
  currentUser: any = null;
  isAdmin = false; // Add isAdmin property

  constructor(
    private propertyService: PropertyService,
    public authService: AuthService, // Make it public to access in template if needed, or use getter
    private router: Router
  ) {}

  ngOnInit(): void {
    this.loadUserInfo();
    this.loadData();
  }

  loadUserInfo(): void {
    // Subscribe to user changes to get role
    this.authService.currentUser$.subscribe(user => {
      this.currentUser = user;
      this.isAdmin = user?.role === 'admin'; // Update isAdmin flag
    });
  }

  logout(): void {
    if (confirm('¿Cerrar sesión?')) {
      this.authService.logout().subscribe({
        next: () => {
          this.router.navigate(['/login']);
        },
        error: (err) => {
          console.error('Error al cerrar sesión:', err);
          // Force clear storage and navigate even if API call fails
          localStorage.clear(); // Consider calling the service method if preferred
          this.currentUser = null;
          this.isAdmin = false;
          this.router.navigate(['/login']);
        }
      });
    }
  }

  createEmptyProperty(): Property {
    // (Keep existing implementation)
    return {
      titulo: '',
      descripcion: null,
      precio: null,
      // ... rest of the properties initialized to null or default values
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
         // Handle potential 401/403 errors - maybe logout?
         if (err.status === 401 || err.status === 403) {
            console.error("Authentication/Authorization error loading data. Logging out.");
            this.logout(); // Or navigate directly
         }
      }
    });
  }

  // --- Keep all existing property methods (editProperty, saveChanges, etc.) ---
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
        if (this.selectedFiles.length > 0 && this.editingProperty?.id) {
          this.uploadSelectedImages(this.editingProperty.id, () => {
            this.loadData(); // Reload data after successful upload
            this.cancelEdit(); // Close edit form
          });
        } else {
          this.loadData(); // Reload data if no images were uploaded
          this.cancelEdit(); // Close edit form
        }
      },
      error: (err) => {
        this.errorMessage = `Error al actualizar propiedad: ${err.error?.error || err.message}`;
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
      next: () => this.loadData(), // Reload data on success
      error: (err) => {
        this.errorMessage = `Error al eliminar propiedad: ${err.error?.error || err.message}`;
        console.error(err);
      }
    });
  }

  addProperty() {
    this.normalizeNullValues(this.newProperty);

    this.propertyService.add(this.newProperty).subscribe({
      next: (response) => {
        const newId = response.id;
        if (this.selectedFiles.length > 0 && newId) {
           this.uploadSelectedImages(newId, () => {
             this.loadData(); // Reload data after successful upload
             this.newProperty = this.createEmptyProperty(); // Reset form
             this.selectedFiles = [];
           });
        } else {
           this.loadData(); // Reload data if no images were added
           this.newProperty = this.createEmptyProperty(); // Reset form
           this.selectedFiles = [];
        }
      },
      error: (err) => {
        this.errorMessage = `Error al agregar propiedad: ${err.error?.error || err.message}`;
        console.error(err);
      }
    });
  }

  normalizeNullValues(prop: Property) {
      // (Keep existing implementation)
      const keys: (keyof Property)[] = [
        'descripcion', 'precio', 'precio_alquiler', 'valor_administracion',
        'anio_construccion', 'piso', 'direccion', 'codigo_postal', 'lat', 'lng',
        'registro_publico', 'convenio_url', 'fecha_validacion', 'updated_at', 'deleted_at',
        'tipo_negocio_id', 'tipo_propiedad_id', 'estado_publicacion_id',
        'captado_por_agente_id', 'moneda_id', 'frecuencia_alquiler_id',
        'estado_fisico_id', 'estado_id', 'ciudad_id', 'zona_id', 'agente_id',
        'agente_externo_id', 'validado_por_usuario_id'
      ];

      for (const key of keys) {
        if (prop[key] === '' || prop[key] === undefined || prop[key] === 0 && (key === 'habitaciones' || key === 'alcobas' || key === 'banos' || key === 'banos_medios' || key === 'estacionamientos' || key === 'm2_terreno' || key === 'm2_construccion' || key === 'm2_privada')) {
           // For numeric fields that can be 0, handle them specifically if needed
           // Otherwise, generally set empty strings/undefined to null for DB consistency
           (prop as any)[key] = null;
        }
      }
       // Ensure boolean is handled correctly
      if (prop.convenio_validado === undefined || prop.convenio_validado === null) {
          prop.convenio_validado = false;
      }
    }


  getCatalogoNombre(catalogoKey: keyof CatalogosApiResponse, id: number | null | undefined): string {
    // (Keep existing implementation)
    if (id === null || id === undefined || !this.catalogos || !this.catalogos[catalogoKey]) {
      return 'N/A';
    }
    const items = this.catalogos[catalogoKey];
    if (!Array.isArray(items)) {
        console.warn(`Catalog items for key "${String(catalogoKey)}" is not an array.`);
        return 'Error';
    }
    const item = items.find(c => c.id === id);
    return item ? item.nombre : `ID ${id} ?`; // Show ID if name not found
  }


  onFileSelected(event: Event) {
    // (Keep existing implementation)
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
      const uploadObservables: Observable<any>[] = []; // Store observables

      this.selectedFiles.forEach((file, index) => {
        // Determine if it should be principal: only if it's the first file AND
        // either we are NOT editing, OR we ARE editing and there are no existing images.
        const noExistingImages = !this.editingImages || this.editingImages.length === 0;
        const esPrincipal = index === 0 && noExistingImages;

        // Add the upload observable to the array
        uploadObservables.push(
            this.propertyService.uploadImage(propiedadId, file, esPrincipal)
        );
      });

      // Execute all uploads concurrently
      forkJoin(uploadObservables).subscribe({
        next: (results) => {
          console.log('Todas las imágenes subidas:', results);
          this.uploadingImages = false;
          callback(); // Execute callback after all uploads succeed
        },
        error: (err) => {
          console.error('Error durante la subida de una o más imágenes:', err);
          this.errorMessage = `Error al subir imágenes: ${err.error?.error || err.message}`;
          this.uploadingImages = false;
          // Optionally call callback even on error, depending on desired behavior
          callback();
        }
      });
    }

  deleteImage(propiedadId: number, imagenId: number) {
    // (Keep existing implementation)
     if (!confirm('¿Eliminar esta imagen?')) return;

     this.propertyService.deleteImage(propiedadId, imagenId).subscribe({
       next: () => {
         // Update local state immediately
         if(this.editingProperty && this.editingProperty.imagenes) {
            this.editingProperty.imagenes = this.editingProperty.imagenes.filter(img => img.id !== imagenId);
            this.editingImages = [...this.editingProperty.imagenes]; // Update editingImages too
         }
         // Optionally reload all data if not editing or to ensure consistency
         // this.loadData();
       },
       error: (err) => {
         this.errorMessage = `Error al eliminar imagen: ${err.error?.error || err.message}`;
         console.error(err);
       }
     });
  }

  setPrincipal(propiedadId: number, imagenId: number) {
     // (Keep existing implementation)
     this.propertyService.setPrincipalImage(propiedadId, imagenId).subscribe({
       next: () => {
         // Update local state immediately
         if(this.editingProperty && this.editingProperty.imagenes) {
             this.editingProperty.imagenes.forEach(img => {
                 img.es_principal = img.id === imagenId;
             });
             this.editingImages = [...this.editingProperty.imagenes]; // Update editingImages
         }
          // Optionally reload all data
         // this.loadData();
       },
       error: (err) => {
          this.errorMessage = `Error al establecer imagen principal: ${err.error?.error || err.message}`;
          console.error(err);
       }
     });
  }


  getPrincipalImage(property: Property): string | null {
    // (Keep existing implementation)
     if (!property.imagenes || property.imagenes.length === 0) {
       return null;
     }
     const principal = property.imagenes.find(img => img.es_principal);
     return principal ? principal.url : property.imagenes[0].url; // Fallback to first image
  }


  removeSelectedFile(index: number) {
    // (Keep existing implementation)
     this.selectedFiles.splice(index, 1);
  }

}