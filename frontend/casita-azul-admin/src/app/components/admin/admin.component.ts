// src/app/components/admin/admin.component.ts
import { Component, OnInit, ViewChild } from '@angular/core'; // <-- CAMBIO: Añadido ViewChild
import { Router, RouterLink } from '@angular/router';
import { FormsModule, NgForm } from '@angular/forms'; // <-- CAMBIO: Añadido NgForm
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
  title = 'Administración de Propiedades';
  isLoading = false;
  errorMessage = '';
  successMessage = '';
  properties: Property[] = [];
  editingProperty: Property | null = null;
  isNewMode = false; // Flag for new property

  // Búsqueda UI
  showSearch = false;
  searchQuery = '';

  catalogos: CatalogosApiResponse = {};
  newProperty: Property = this.createEmptyProperty();

  selectedFiles: File[] = [];
  uploadingImages = false;
  editingImages: PropertyImage[] = [];

  // Information for the logged-in user
  currentUser: any = null;
  isAdmin = false;

  // --- CAMBIO: Añadidas referencias a los formularios del HTML ---
  @ViewChild('editForm') editForm!: NgForm;
  @ViewChild('addForm') addForm!: NgForm;

  constructor(
    private propertyService: PropertyService,
    public authService: AuthService,
    private router: Router
  ) {}

  ngOnInit(): void {
    this.loadUserInfo();
    this.loadData();
  }

  loadUserInfo(): void {
    this.authService.currentUser$.subscribe(user => {
      this.currentUser = user;
      this.isAdmin = user?.role === 'admin';
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
          this.authService.logout(); // Force clear local storage
          this.currentUser = null;
          this.isAdmin = false;
          this.router.navigate(['/login']);
        }
      });
    }
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
         if (err.status === 401 || err.status === 403) {
            console.error("Authentication/Authorization error loading data. Logging out.");
            this.logout();
         }
      }
    });
  }

  // Devuelve propiedades filtradas según searchQuery (si está vacío devuelve todas)
  get displayedProperties(): Property[] {
    const q = (this.searchQuery || '').trim().toLowerCase();
    if (!q) return this.properties;
    return this.properties.filter(p => {
      const titulo = (p.titulo || '').toString().toLowerCase();
      const descripcion = (p.descripcion || '').toString().toLowerCase();
      const direccion = (p.direccion || '').toString().toLowerCase();
      return titulo.includes(q) || descripcion.includes(q) || direccion.includes(q);
    });
  }

  toggleSearch() {
    this.showSearch = !this.showSearch;
    if (!this.showSearch) {
      this.searchQuery = '';
    }
  }

  onSearch(_q: string) {
    // El filtrado ocurre por el getter displayedProperties; este método existe para el binding (ngModelChange)
  }

  editProperty(prop: Property) {
    this.editingProperty = JSON.parse(JSON.stringify(prop));
    this.editingImages = prop.imagenes ? [...prop.imagenes] : [];
    this.selectedFiles = [];
    this.isNewMode = false; // Estamos editando
    this.errorMessage = ''; // Limpia error
    this.successMessage = ''; // Limpia éxito
  }

  // Lógica para el formulario de agregar (separada)
  showAddForm() {
    this.newProperty = this.createEmptyProperty();
    this.editingProperty = null; // Nos aseguramos de no estar editando
    this.selectedFiles = [];
    this.editingImages = [];
    this.isNewMode = true; // Estamos agregando
    this.errorMessage = ''; // Limpia error
    this.successMessage = ''; // Limpia éxito
  }


  saveChanges() {
    if (!this.editingProperty) return;

    // --- CAMBIO: Añadida validación ---
    // Marcamos todos los campos como "touched" para forzar la UI a mostrar errores
    this.editForm.form.markAllAsTouched();
    
    // Si el formulario (que ahora incluye los ngModelGroup) es inválido, no continuamos.
    if (!this.editForm.valid) {
      console.log("Formulario de EDICIÓN es inválido.");
      return;
    }

    this.normalizeNullValues(this.editingProperty);
    // Limpia mensajes antes de la operación
    this.errorMessage = '';
    this.successMessage = '';

    this.propertyService.update(this.editingProperty).subscribe({
      next: () => {
        // Muestra mensaje de éxito
        this.successMessage = `Propiedad ID ${this.editingProperty?.id} actualizada correctamente.`;
        if (this.selectedFiles.length > 0 && this.editingProperty?.id) {
          this.uploadSelectedImages(this.editingProperty.id, () => {
            this.loadData();
            this.cancelEdit();
          });
        } else {
          this.loadData();
          this.cancelEdit();
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
    this.isNewMode = false;
    this.newProperty = this.createEmptyProperty(); // Limpia el formulario de nuevo
    this.errorMessage = ''; // Limpia error
    this.successMessage = ''; // Limpia éxito
  }

  deleteProperty(id: number | undefined) {
    if (!id || !confirm('¿Seguro que deseas eliminar esta propiedad? (Borrado lógico)')) return;

    this.propertyService.delete(id).subscribe({
      next: () => this.loadData(),
      error: (err) => {
        this.errorMessage = `Error al eliminar propiedad: ${err.error?.error || err.message}`;
        console.error(err);
      }
    });
  }

  addProperty() {
    // --- CAMBIO: Añadida validación ---
    // Marcamos todos los campos como "touched" para forzar la UI a mostrar errores
    this.addForm.form.markAllAsTouched();

    // Si el formulario (que ahora incluye los ngModelGroup) es inválido, no continuamos.
    if (!this.addForm.valid) {
      console.log("Formulario de AGREGAR es inválido.");
      return; 
    }

    this.normalizeNullValues(this.newProperty);
     // Limpia mensajes antes de la operación
    this.errorMessage = '';
    this.successMessage = '';

    this.propertyService.add(this.newProperty).subscribe({
      next: (response) => {
        const newId = response.id;
        // Muestra mensaje de éxito
        this.successMessage = `Propiedad "${this.newProperty.titulo}" agregada correctamente con ID ${newId}.`;
        if (this.selectedFiles.length > 0 && newId) {
           this.uploadSelectedImages(newId, () => {
             this.loadData();
             this.cancelEdit();
           });
        } else {
           this.loadData();
           this.cancelEdit();
        }
      },
      error: (err) => {
        this.errorMessage = `Error al agregar propiedad: ${err.error?.error || err.message}`;
        console.error(err);
      }
    });
  }

  normalizeNullValues(prop: Property) {
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
        if (prop[key] === '' || prop[key] === undefined) {
           (prop as any)[key] = null;
        }
        // Manejar campos numéricos que pueden ser 0 pero no nulos si se dejan vacíos
        const numericFields: (keyof Property)[] = [
          'habitaciones', 'alcobas', 'banos', 'banos_medios', 'estacionamientos',
          'm2_terreno', 'm2_construccion', 'm2_privada'
        ];
        if (numericFields.includes(key) && prop[key] === null) {
           (prop as any)[key] = 0;
        }
      }
      if (prop.convenio_validado === undefined || prop.convenio_validado === null) {
          prop.convenio_validado = false;
      }
    }


  getCatalogoNombre(catalogoKey: keyof CatalogosApiResponse, id: number | null | undefined): string {
    if (id === null || id === undefined || !this.catalogos || !this.catalogos[catalogoKey]) {
      return 'N/A';
    }
    const items = this.catalogos[catalogoKey];
    if (!Array.isArray(items)) {
        console.warn(`Catalog items for key "${String(catalogoKey)}" is not an array.`);
        return 'Error';
    }
    const item = items.find(c => c.id === id);
    return item ? item.nombre : `ID ${id} ?`;
  }


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
      const uploadObservables: Observable<any>[] = [];

      this.selectedFiles.forEach((file, index) => {
        // Lógica corregida:
        // Es principal si es el primer archivo (index === 0) Y
        // (estamos en modo "Nuevo" O estamos en modo "Editar" y no hay imágenes existentes)
        const noExistingImages = !this.editingImages || this.editingImages.length === 0;
        const esPrincipal = index === 0 && (this.isNewMode || noExistingImages);

        uploadObservables.push(
            this.propertyService.uploadImage(propiedadId, file, esPrincipal)
        );
      });

      forkJoin(uploadObservables).subscribe({
        next: (results) => {
          console.log('Todas las imágenes subidas:', results);
          this.uploadingImages = false;
          callback();
        },
        error: (err) => {
          console.error('Error durante la subida de una o más imágenes:', err);
          this.errorMessage = `Error al subir imágenes: ${err.error?.error || err.message}`;
          this.uploadingImages = false;
          callback();
        }
      });
    }

  deleteImage(propiedadId: number, imagenId: number) {
     if (!confirm('¿Eliminar esta imagen?')) return;

     this.propertyService.deleteImage(propiedadId, imagenId).subscribe({
       next: () => {
         if(this.editingProperty && this.editingProperty.imagenes) {
            this.editingProperty.imagenes = this.editingProperty.imagenes.filter(img => img.id !== imagenId);
            this.editingImages = [...this.editingProperty.imagenes];
         }
         // No es necesario recargar toda la data, solo actualizar el local
       },
       error: (err) => {
         this.errorMessage = `Error al eliminar imagen: ${err.error?.error || err.message}`;
         console.error(err);
       }
     });
  }

  setPrincipal(propiedadId: number, imagenId: number) {
     this.propertyService.setPrincipalImage(propiedadId, imagenId).subscribe({
       next: () => {
         if(this.editingProperty && this.editingProperty.imagenes) {
             this.editingProperty.imagenes.forEach(img => {
                 img.es_principal = img.id === imagenId;
             });
             this.editingImages = [...this.editingProperty.imagenes];
         }
       },
       error: (err) => {
          this.errorMessage = `Error al establecer imagen principal: ${err.error?.error || err.message}`;
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