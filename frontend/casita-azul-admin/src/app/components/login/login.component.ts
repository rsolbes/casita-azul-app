import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  templateUrl: './login.component.html',
  styleUrls: ['./login.component.css']
})
export class LoginComponent {
  loginForm: FormGroup;
  registerForm: FormGroup;
  isLoginMode = true;
  loading = false;
  errorMessage = '';
  successMessage = '';

  constructor(
    private fb: FormBuilder,
    private authService: AuthService,
    private router: Router
  ) {
    this.loginForm = this.fb.group({
      email: ['', [Validators.required, Validators.email]],
      password: ['', [Validators.required, Validators.minLength(6)]]
    });

    this.registerForm = this.fb.group({
      email: ['', [Validators.required, Validators.email]],
      password: ['', [Validators.required, Validators.minLength(6)]],
      confirmPassword: ['', [Validators.required]] // Sin validador extra aquí
    }, { validators: this.passwordMatchValidator }); // Añadir validador al grupo
  }

  // Validador personalizado para confirmar contraseña
  passwordMatchValidator(form: FormGroup) {
    const password = form.get('password');
    const confirmPassword = form.get('confirmPassword');
    // Solo valida si ambos campos tienen valor para evitar errores iniciales
    if (password && confirmPassword && password.value !== confirmPassword.value) {
      confirmPassword.setErrors({ mismatch: true });
    } else if (confirmPassword) {
      // Si coinciden y tenía el error, lo quitamos
      if (confirmPassword.hasError('mismatch')) {
         // Clona los errores existentes (si hay otros)
         const errors = { ...confirmPassword.errors };
         delete errors['mismatch']; // Elimina solo el error de mismatch
         // Si no quedan errores, establece null, si no, establece los restantes
         confirmPassword.setErrors(Object.keys(errors).length === 0 ? null : errors);
      }
    }
    return null; // El validador de grupo no necesita devolver error aquí
  }

  toggleMode(): void {
    this.isLoginMode = !this.isLoginMode;
    this.errorMessage = '';
    this.successMessage = '';
    this.loginForm.reset();
    this.registerForm.reset();
  }

  onLogin(): void {
    if (this.loginForm.invalid) {
      // Marcar campos como tocados para mostrar errores si es necesario
      this.loginForm.markAllAsTouched();
      return;
    }

    this.loading = true;
    this.errorMessage = '';
    this.successMessage = ''; // Limpiar mensaje de éxito

    const { email, password } = this.loginForm.value;

    this.authService.login(email, password).subscribe({
      next: (user) => { // Ahora recibe el usuario completo
        this.loading = false;
        if (user) { // Verifica que el usuario no sea null
            this.successMessage = 'Login exitoso!';
            // Navega inmediatamente ya que tenemos la info del usuario
            this.router.navigate(['/admin']);
        } else {
             // Caso improbable si login tiene éxito pero fetch falla y devuelve null
             this.errorMessage = 'No se pudieron obtener los detalles del usuario.';
        }
      },
      error: (error) => {
        this.loading = false;
        this.errorMessage = error.error?.error || 'Error al iniciar sesión. Verifica tus credenciales.';
        console.error("Login error:", error);
      }
    });
  }

  onRegister(): void {
    if (this.registerForm.invalid) {
      this.registerForm.markAllAsTouched();
      return;
    }

    // Ya no necesitamos la validación de coincidencia aquí porque está en el grupo
    // const { password, confirmPassword } = this.registerForm.value;
    // if (password !== confirmPassword) { ... }

    this.loading = true;
    this.errorMessage = '';
    this.successMessage = ''; // Limpiar mensaje de éxito

    const { email, password } = this.registerForm.value;

    this.authService.register(email, password).subscribe({
      next: (response) => {
        this.loading = false;
        this.successMessage = response.message || 'Registro exitoso. Revisa tu email para confirmar.'; // Usa mensaje del backend si existe
        this.registerForm.reset();
        // Cambia a modo login después de un mensaje exitoso
        setTimeout(() => {
          this.isLoginMode = true;
          this.successMessage = ''; // Limpiar mensaje después de cambiar
        }, 3000); // Espera 3 segundos
      },
      error: (error) => {
        this.loading = false;
        this.errorMessage = error.error?.error || 'Error al registrarse. El email podría ya estar en uso.';
        console.error("Register error:", error);
      }
    });
  }
}