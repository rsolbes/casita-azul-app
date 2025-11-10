// frontend/casita-azul-admin/src/app/components/dashboard/dashboard.component.ts
import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { DashboardService, DashboardStats, RecentActivity } from '../../services/dashboard.service';
import { AuthService } from '../../services/auth.service';
import { Router } from '@angular/router';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.css']
})
export class DashboardComponent implements OnInit {
  stats: DashboardStats | null = null;
  recentActivity: RecentActivity[] = [];
  isLoading = false;
  errorMessage = '';
  currentUser: any = null;
  isAdmin = false;

  constructor(
    private dashboardService: DashboardService,
    private authService: AuthService,
    private router: Router
  ) {}

  ngOnInit(): void {
    this.loadUserInfo();
    this.loadDashboardData();
  }

  loadUserInfo(): void {
    this.authService.currentUser$.subscribe(user => {
      this.currentUser = user;
      this.isAdmin = user?.role === 'admin';
    });
  }

  loadDashboardData(): void {
    this.isLoading = true;
    this.errorMessage = '';

    this.dashboardService.getStats().subscribe({
      next: (stats) => {
        this.stats = stats;
        this.loadRecentActivity();
      },
      error: (err) => {
        this.errorMessage = 'Error al cargar estadísticas del dashboard';
        console.error(err);
        this.isLoading = false;
      }
    });
  }

  loadRecentActivity(): void {
    this.dashboardService.getRecentActivity().subscribe({
      next: (activity) => {
        this.recentActivity = activity;
        this.isLoading = false;
      },
      error: (err) => {
        console.error('Error al cargar actividad reciente:', err);
        this.isLoading = false;
      }
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
          this.authService.logout();
          this.router.navigate(['/login']);
        }
      });
    }
  }

  formatDate(dateString: string | null): string {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleDateString('es-MX', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  }

  formatCurrency(amount: number | null | undefined): string {
    if (!amount) return 'N/A';
    return new Intl.NumberFormat('es-MX', {
      style: 'currency',
      currency: 'MXN'
    }).format(amount);
  }

  getPercentage(part: number, total: number): number {
    if (total === 0) return 0;
    return Math.round((part / total) * 100);
  }
}