import { Component, OnInit, inject, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AdminService } from '../../../core/services/admin.service';

@Component({
  selector: 'app-admin-dashboard',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="dashboard-page">
      <h2>Dashboard Overview</h2>

      <div *ngIf="isLoading" class="loader">Loading metrics...</div>
      <div *ngIf="error" class="alert alert-danger">{{ error }}</div>

      <div class="metrics-grid" *ngIf="!isLoading && metrics">
        <div class="metric-card bg-primary">
          <div class="metric-value">{{ metrics.total_users }}</div>
          <div class="metric-label">Total Users</div>
        </div>
        <div class="metric-card bg-info">
          <div class="metric-value">{{ metrics.customers }}</div>
          <div class="metric-label">Customers</div>
        </div>
        <div class="metric-card bg-success">
          <div class="metric-value">{{ metrics.products }}</div>
          <div class="metric-label">Products</div>
        </div>
        <div class="metric-card bg-warning text-dark">
          <div class="metric-value">{{ metrics.categories }}</div>
          <div class="metric-label">Categories</div>
        </div>
        <div class="metric-card bg-primary">
          <div class="metric-value">{{ metrics.orders }}</div>
          <div class="metric-label">Total Orders</div>
        </div>
        <div class="metric-card bg-warning text-dark">
          <div class="metric-value">{{ metrics.pending_orders }}</div>
          <div class="metric-label">Pending Orders</div>
        </div>
        <div class="metric-card bg-success">
          <div class="metric-value">{{ metrics.delivered_orders }}</div>
          <div class="metric-label">Delivered Orders</div>
        </div>
        <div class="metric-card bg-dark">
          <div class="metric-value">\${{ metrics.revenue }}</div>
          <div class="metric-label">Total Revenue</div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .dashboard-page { padding-bottom: 20px; }
    h2 { margin-top: 0; margin-bottom: 25px; color: #333; }
    
    .metrics-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
      gap: 20px;
    }
    
    .metric-card {
      padding: 25px 20px;
      border-radius: 8px;
      color: white;
      text-align: center;
      box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    
    .metric-value { font-size: 2.2rem; font-weight: bold; margin-bottom: 5px; }
    .metric-label { font-size: 1rem; opacity: 0.9; }
    
    .bg-primary { background-color: #0d6efd; }
    .bg-success { background-color: #198754; }
    .bg-info { background-color: #0dcaf0; color: #000; }
    .bg-warning { background-color: #ffc107; color: #000; }
    .bg-dark { background-color: #212529; }
    .text-dark { color: #000 !important; }
    
    .loader { text-align: center; padding: 40px; color: #666; font-size: 1.1rem; }
    .alert { padding: 15px; border-radius: 6px; margin-bottom: 20px; }
    .alert-danger { background-color: #f8d7da; color: #842029; border: 1px solid #f5c2c7; }
  `]
})
export class AdminDashboardComponent implements OnInit {
  private adminService = inject(AdminService);
  private cdr = inject(ChangeDetectorRef);

  metrics: any = null;
  isLoading = true;
  error = '';

  ngOnInit() {
    this.loadDashboard();
  }

  loadDashboard() {
    this.isLoading = true;
    this.adminService.getDashboard().subscribe({
      next: (res: any) => {
        if (res && res.data) {
          this.metrics = res.data;
        } else {
          this.metrics = res;
        }
        this.isLoading = false;
        this.cdr.detectChanges();
      },
      error: (err) => {
        this.error = 'Failed to load dashboard metrics.';
        this.isLoading = false;
        this.cdr.detectChanges();
      }
    });
  }
}
