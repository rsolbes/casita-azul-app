import { Component, OnInit } from '@angular/core';
import { CommonModule, TitleCasePipe } from '@angular/common'; // Import TitleCasePipe
import { FormsModule, ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms'; // Import necessary modules
import { AdminService, AdminUser } from '../../services/admin.service';
import { RouterLink } from '@angular/router'; // Import RouterLink

@Component({
  selector: 'app-manage-users',
  standalone: true,
  imports: [CommonModule, FormsModule, ReactiveFormsModule, RouterLink, TitleCasePipe], // Add necessary imports
  templateUrl: './manage-users.component.html',
  styleUrls: ['./manage-users.component.css']
})
export class ManageUsersComponent implements OnInit {
  users: AdminUser[] = [];
  isLoading = false;
  errorMessage = '';
  successMessage = '';

  showAddForm = false;
  addUserForm: FormGroup;

  editingUserId: string | null = null;
  editingUserRole = '';
  availableRoles: string[] = ['admin', 'user', 'agent']; // Define available roles

  constructor(
    private adminService: AdminService,
    private fb: FormBuilder
  ) {
    this.addUserForm = this.fb.group({
      email: ['', [Validators.required, Validators.email]],
      password: ['', [Validators.required, Validators.minLength(6)]],
      role: ['user', Validators.required] // Default role 'user'
    });
  }

  ngOnInit(): void {
    this.loadUsers();
  }

  loadUsers(): void {
    this.isLoading = true;
    this.errorMessage = '';
    this.successMessage = '';
    this.adminService.getUsers().subscribe({
      next: (users) => {
        // Asumimos que el rol vendrá del backend (lo ajustamos en app.py)
        // Si no, necesitaremos buscar el perfil para cada usuario.
        this.users = users;
        this.isLoading = false;
      },
      error: (err) => {
        this.errorMessage = `Error cargando usuarios: ${err.error?.error || err.message}`;
        console.error(err);
        this.isLoading = false;
      }
    });
  }

  toggleAddForm(): void {
    this.showAddForm = !this.showAddForm;
    this.addUserForm.reset({ role: 'user' }); // Reset form with default role
    this.errorMessage = '';
    this.successMessage = '';
  }

  onSubmitNewUser(): void {
    if (this.addUserForm.invalid) {
      this.errorMessage = 'Por favor, completa el formulario correctamente.';
      return;
    }

    this.isLoading = true;
    this.errorMessage = '';
    this.successMessage = '';

    this.adminService.createUser(this.addUserForm.value).subscribe({
      next: (newUser) => {
        this.successMessage = `Usuario ${newUser.email} creado exitosamente.`;
        this.isLoading = false;
        this.showAddForm = false;
        this.addUserForm.reset({ role: 'user' }); // Clear the form
        this.loadUsers(); // Reload the list
      },
      error: (err) => {
        this.errorMessage = `Error creando usuario: ${err.error?.error || err.message}`;
        console.error(err);
        this.isLoading = false;
      }
    });
  }

  startEditRole(user: AdminUser): void {
    this.editingUserId = user.id;
    // El rol debería venir del backend
    this.editingUserRole = user.role || 'user';
    this.errorMessage = '';
    this.successMessage = '';
  }

  cancelEditRole(): void {
    this.editingUserId = null;
    this.editingUserRole = '';
  }

  saveUserRole(userId: string): void {
     this.isLoading = true;
     this.errorMessage = '';
     this.successMessage = '';
     this.adminService.updateUserRole(userId, this.editingUserRole).subscribe({
        next: () => {
           this.successMessage = `Rol del usuario actualizado.`;
           this.isLoading = false;
           this.editingUserId = null;
           // Find user in list and update role locally for immediate feedback
           const userIndex = this.users.findIndex(u => u.id === userId);
           if (userIndex > -1) {
               // Make sure role property exists before assigning
               this.users[userIndex] = { ...this.users[userIndex], role: this.editingUserRole };
           }
           // Optionally reload all users: this.loadUsers();
        },
        error: (err) => {
           this.errorMessage = `Error actualizando rol: ${err.error?.error || err.message}`;
           console.error(err);
           this.isLoading = false;
        }
     });
  }


  deleteUser(userId: string, userEmail: string): void {
    if (confirm(`¿Estás seguro de eliminar al usuario ${userEmail}? Esta acción no se puede deshacer.`)) {
      this.isLoading = true;
      this.errorMessage = '';
      this.successMessage = '';
      this.adminService.deleteUser(userId).subscribe({
        next: () => {
          this.successMessage = `Usuario ${userEmail} eliminado.`;
          this.isLoading = false;
          // Remove the user from the local array for immediate feedback
          this.users = this.users.filter(u => u.id !== userId);
          // Optionally reload: this.loadUsers();
        },
        error: (err) => {
          this.errorMessage = `Error eliminando usuario: ${err.error?.error || err.message}`;
          console.error(err);
          this.isLoading = false;
        }
      });
    }
  }
}