import { Component, OnInit, inject, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { AdminService } from '../../../core/services/admin.service';

@Component({
  selector: 'app-admin-order-list',
  standalone: true,
  imports: [CommonModule, RouterModule, FormsModule],
  template: `
    <div class="admin-page">
      <div class="page-header">
        <h2>Manage Orders</h2>
      </div>

      <div class="filters-card">
        <div class="filter-group">
          <input type="text" [(ngModel)]="search" placeholder="Search order #..." class="form-control" (keyup.enter)="loadOrders()">
        </div>
        <div class="filter-group">
          <select [(ngModel)]="status" class="form-control" (change)="loadOrders()">
            <option value="">All Statuses</option>
            <option value="pending">Pending</option>
            <option value="processing">Processing</option>
            <option value="shipped">Shipped</option>
            <option value="delivered">Delivered</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </div>
        <button class="btn btn-secondary" (click)="loadOrders()">Apply</button>
      </div>

      <div *ngIf="error" class="alert alert-danger">{{ error }}</div>

      <div class="table-responsive" *ngIf="!isLoading && orders.length > 0">
        <table class="table">
          <thead>
            <tr>
              <th>Order #</th>
              <th>Customer</th>
              <th>Total</th>
              <th>Status</th>
              <th>Date</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr *ngFor="let order of orders">
              <td><strong>#{{ order.id }}</strong></td>
              <td>
                <div class="customer-info">
                  {{ order.user?.name }}
                  <small>{{ order.user?.email }}</small>
                </div>
              </td>
              <td>\${{ order.total }}</td>
              <td>
                <span class="badge" [ngClass]="getStatusClass(order.status)">{{ order.status }}</span>
              </td>
              <td>{{ order.created_at | date:'medium' }}</td>
              <td class="actions">
                <a [routerLink]="['/admin/orders', order.id]" class="btn btn-sm btn-info">View Details</a>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Pagination -->
      <div class="pagination" *ngIf="!isLoading && pagination && pagination.last_page > 1">
        <button class="btn btn-sm" [disabled]="pagination.current_page === 1" (click)="changePage(pagination.current_page - 1)">Previous</button>
        <span>Page {{ pagination.current_page }} of {{ pagination.last_page }}</span>
        <button class="btn btn-sm" [disabled]="pagination.current_page === pagination.last_page" (click)="changePage(pagination.current_page + 1)">Next</button>
      </div>

      <div *ngIf="isLoading" class="loader">Loading orders...</div>
      
      <div *ngIf="!isLoading && orders.length === 0" class="empty-state">
        No orders found matching your criteria.
      </div>
    </div>
  `,
  styles: [`
    .page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
    h2 { margin: 0; color: #333; }
    
    .filters-card { background: white; padding: 15px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); display: flex; gap: 15px; flex-wrap: wrap; align-items: center; }
    .filter-group { flex: 1; min-width: 200px; }
    .form-control { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
    
    .table-responsive { background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); overflow-x: auto; }
    .table { width: 100%; border-collapse: collapse; }
    .table th, .table td { padding: 12px 15px; text-align: left; border-bottom: 1px solid #eee; vertical-align: middle; }
    .table th { background-color: #f8f9fa; font-weight: 600; color: #555; }
    
    .customer-info { display: flex; flex-direction: column; }
    .customer-info small { color: #666; font-size: 0.8rem; }
    
    .badge { padding: 5px 10px; border-radius: 20px; font-size: 0.8rem; font-weight: 500; text-transform: capitalize; }
    .badge-pending { background-color: #ffeeba; color: #856404; }
    .badge-processing { background-color: #b8daff; color: #004085; }
    .badge-shipped { background-color: #d1ecf1; color: #0c5460; }
    .badge-delivered { background-color: #d4edda; color: #155724; }
    .badge-cancelled { background-color: #f8d7da; color: #721c24; }
    
    .actions { display: flex; gap: 8px; }
    .btn-sm { padding: 5px 10px; font-size: 0.85rem; }
    .btn-info { background-color: #17a2b8; color: white; border: none; border-radius: 4px; text-decoration: none; cursor: pointer; }
    .btn-secondary { background-color: #6c757d; color: white; padding: 10px 15px; border: none; border-radius: 4px; cursor: pointer; }
    
    .pagination { display: flex; justify-content: center; align-items: center; gap: 15px; margin-top: 20px; }
    .loader { text-align: center; padding: 40px; color: #666; }
    .empty-state { text-align: center; padding: 40px; background: white; border-radius: 8px; color: #666; }
    .alert { padding: 15px; border-radius: 4px; margin-bottom: 15px; }
    .alert-danger { background: #f8d7da; color: #721c24; border: 1px solid #f5c2c7; }
  `]
})
export class AdminOrderListComponent implements OnInit {
  private adminService = inject(AdminService);
  private cdr = inject(ChangeDetectorRef);

  orders: any[] = [];
  pagination: any = null;
  isLoading = true;
  error = '';

  // Filters
  search = '';
  status = '';
  page = 1;

  ngOnInit() {
    this.loadOrders();
  }

  loadOrders() {
    this.isLoading = true;
    this.error = '';

    const params: any = { page: this.page };
    if (this.search) params.search = this.search;
    if (this.status) params.status = this.status;

    this.adminService.getOrders(params).subscribe({
      next: (res: any) => {
        if (res && res.data) {
          if (Array.isArray(res.data)) this.orders = res.data;
          else if (res.data.orders && Array.isArray(res.data.orders)) this.orders = res.data.orders;
          else if (res.data.data && Array.isArray(res.data.data)) this.orders = res.data.data;

          this.pagination = res.data.pagination || res.pagination || res.meta || null;
        } else {
          this.orders = [];
        }
        this.isLoading = false;
        this.cdr.detectChanges();
      },
      error: () => {
        this.error = 'Failed to load orders.';
        this.isLoading = false;
        this.cdr.detectChanges();
      }
    });
  }

  changePage(newPage: number) {
    this.page = newPage;
    this.loadOrders();
  }

  getStatusClass(status: string): string {
    return `badge-${status.toLowerCase()}`;
  }
}
