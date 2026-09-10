import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, Router } from '@angular/router';
import { AuthService } from '../../../core/services/auth.service';

@Component({
  selector: 'app-admin-layout',
  standalone: true,
  imports: [CommonModule, RouterModule],
  template: `
    <div class="admin-layout">
      <!-- Sidebar -->
      <aside class="admin-sidebar" [class.mobile-open]="isMobileMenuOpen">
        <div class="sidebar-header">
          <h2>Admin Panel</h2>
          <button class="btn-close-mobile" (click)="toggleMobileMenu()">&times;</button>
        </div>
        
        <nav class="sidebar-nav">
          <a routerLink="/admin/dashboard" routerLinkActive="active" (click)="closeMobileMenu()">Dashboard</a>
          <a routerLink="/admin/users" routerLinkActive="active" (click)="closeMobileMenu()">Users</a>
          <a routerLink="/admin/categories" routerLinkActive="active" (click)="closeMobileMenu()">Categories</a>
          <a routerLink="/admin/products" routerLinkActive="active" (click)="closeMobileMenu()">Products</a>
          <a routerLink="/admin/orders" routerLinkActive="active" (click)="closeMobileMenu()">Orders</a>
        </nav>
      </aside>

      <!-- Main Content Area -->
      <div class="admin-main">
        <!-- Topbar -->
        <header class="admin-topbar">
          <button class="btn-menu-mobile" (click)="toggleMobileMenu()">&#9776;</button>
          
          <div class="topbar-right">
            <span class="admin-name">Welcome, {{ adminName }}</span>
            <button class="btn-logout" (click)="logout()">Logout</button>
            <a routerLink="/" class="btn-storefront">Storefront</a>
          </div>
        </header>

        <!-- Page Content -->
        <main class="admin-content">
          <router-outlet></router-outlet>
        </main>
      </div>
      
      <!-- Mobile Overlay -->
      <div class="mobile-overlay" *ngIf="isMobileMenuOpen" (click)="closeMobileMenu()"></div>
    </div>
  `,
  styles: [`
    .admin-layout { display: flex; min-height: 100vh; background-color: #f4f7f6; }
    
    .admin-sidebar { 
      width: 250px; 
      background-color: #2c3e50; 
      color: white; 
      display: flex; 
      flex-direction: column;
      transition: transform 0.3s ease;
      z-index: 100;
    }
    
    .sidebar-header {
      padding: 20px;
      background-color: #1a252f;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    
    .sidebar-header h2 { margin: 0; font-size: 1.2rem; }
    
    .btn-close-mobile { display: none; background: none; border: none; color: white; font-size: 1.5rem; cursor: pointer; }
    
    .sidebar-nav {
      display: flex;
      flex-direction: column;
      padding: 10px 0;
    }
    
    .sidebar-nav a {
      padding: 15px 20px;
      color: #b8c7ce;
      text-decoration: none;
      transition: all 0.2s;
      border-left: 3px solid transparent;
    }
    
    .sidebar-nav a:hover, .sidebar-nav a.active {
      color: white;
      background-color: #34495e;
      border-left-color: #3498db;
    }
    
    .admin-main {
      flex: 1;
      display: flex;
      flex-direction: column;
      overflow-x: hidden;
    }
    
    .admin-topbar {
      background: white;
      padding: 15px 25px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      box-shadow: 0 2px 5px rgba(0,0,0,0.05);
      z-index: 10;
    }
    
    .btn-menu-mobile { display: none; background: none; border: none; font-size: 1.5rem; cursor: pointer; color: #333; }
    
    .topbar-right {
      display: flex;
      align-items: center;
      gap: 15px;
      margin-left: auto;
    }
    
    .admin-name { font-weight: 500; color: #333; }
    
    .btn-logout { background: none; border: 1px solid #dc3545; color: #dc3545; padding: 5px 10px; border-radius: 4px; cursor: pointer; font-size: 0.9rem; }
    .btn-logout:hover { background: #dc3545; color: white; }
    
    .btn-storefront { color: #007bff; text-decoration: none; font-size: 0.9rem; }
    .btn-storefront:hover { text-decoration: underline; }
    
    .admin-content {
      padding: 25px;
      flex: 1;
      overflow-y: auto;
    }
    
    .mobile-overlay { display: none; }
    
    @media (max-width: 768px) {
      .admin-sidebar {
        position: fixed;
        left: 0;
        top: 0;
        bottom: 0;
        transform: translateX(-100%);
      }
      .admin-sidebar.mobile-open { transform: translateX(0); }
      .btn-close-mobile { display: block; }
      .btn-menu-mobile { display: block; }
      .mobile-overlay {
        display: block;
        position: fixed;
        top: 0; left: 0; right: 0; bottom: 0;
        background: rgba(0,0,0,0.5);
        z-index: 90;
      }
    }
  `]
})
export class AdminLayoutComponent {
  private authService = inject(AuthService);
  private router = inject(Router);

  isMobileMenuOpen = false;

  get adminName(): string {
    return this.authService.currentUserValue?.name || 'Admin';
  }

  toggleMobileMenu() {
    this.isMobileMenuOpen = !this.isMobileMenuOpen;
  }

  closeMobileMenu() {
    this.isMobileMenuOpen = false;
  }

  logout() {
    this.authService.logout().subscribe({
      next: () => this.router.navigate(['/login']),
      error: () => this.router.navigate(['/login'])
    });
  }
}
