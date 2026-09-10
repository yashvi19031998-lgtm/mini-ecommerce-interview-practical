import { Component, OnInit, inject, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { OrderService } from '../../core/services/order.service';

@Component({
  selector: 'app-order-list',
  standalone: true,
  imports: [CommonModule, RouterModule],
  template: `
    <div class="orders-page">
      <h2>My Orders</h2>

      <div *ngIf="isLoading" class="loader">Loading orders...</div>
      <div *ngIf="error" class="alert alert-danger">{{ error }}</div>

      <div class="orders-list" *ngIf="!isLoading && orders.length > 0">
        <div class="order-card" *ngFor="let order of orders">
          <div class="order-header">
            <div class="order-id">
              <span>Order #{{ order.id }}</span>
              <span class="order-date">Placed on {{ order.created_at | date:'longDate' }}</span>
            </div>
            <div class="order-status">
              <span class="badge" [ngClass]="getStatusClass(order.status)">{{ order.status }}</span>
            </div>
          </div>
          
          <div class="order-body">
            <div class="order-summary">
              <div class="summary-col">
                <span class="label">Total Amount</span>
                <span class="value">\${{ order.total }}</span>
              </div>
              <div class="summary-col">
                <span class="label">Items</span>
                <span class="value">{{ order.items?.length || 0 }} items</span>
              </div>
            </div>
            
            <div class="order-actions">
              <a [routerLink]="['/orders', order.id]" class="btn btn-outline">View Order Details</a>
            </div>
          </div>
        </div>
      </div>

      <!-- Pagination -->
      <div class="pagination" *ngIf="!isLoading && pagination && pagination.last_page > 1">
        <button class="btn btn-sm" [disabled]="pagination.current_page === 1" (click)="changePage(pagination.current_page - 1)">Previous</button>
        <span>Page {{ pagination.current_page }} of {{ pagination.last_page }}</span>
        <button class="btn btn-sm" [disabled]="pagination.current_page === pagination.last_page" (click)="changePage(pagination.current_page + 1)">Next</button>
      </div>

      <div *ngIf="!isLoading && orders.length === 0" class="empty-state">
        You haven't placed any orders yet.
        <br><br>
        <a routerLink="/products" class="btn btn-primary">Start Shopping</a>
      </div>
    </div>
  `,
  styles: [`
    .orders-page { padding-bottom: 40px; max-width: 800px; margin: 0 auto; }
    h2 { color: #333; margin-bottom: 25px; }
    
    .orders-list { display: flex; flex-direction: column; gap: 20px; }
    .order-card { background: white; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); overflow: hidden; border: 1px solid #eaeaea; }
    
    .order-header { background: #f8f9fa; padding: 15px 20px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #eaeaea; }
    .order-id { display: flex; flex-direction: column; font-weight: 600; color: #333; font-size: 1.1rem; }
    .order-date { font-weight: normal; font-size: 0.85rem; color: #666; margin-top: 3px; }
    
    .order-body { padding: 20px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 20px; }
    .order-summary { display: flex; gap: 40px; }
    .summary-col { display: flex; flex-direction: column; gap: 5px; }
    .summary-col .label { font-size: 0.85rem; color: #666; text-transform: uppercase; letter-spacing: 0.5px; }
    .summary-col .value { font-size: 1.1rem; font-weight: 600; color: #333; }
    
    .badge { padding: 5px 12px; border-radius: 20px; font-size: 0.85rem; font-weight: 500; text-transform: capitalize; }
    .badge-pending { background-color: #ffeeba; color: #856404; }
    .badge-processing { background-color: #b8daff; color: #004085; }
    .badge-shipped { background-color: #d1ecf1; color: #0c5460; }
    .badge-delivered { background-color: #d4edda; color: #155724; }
    .badge-cancelled { background-color: #f8d7da; color: #721c24; }
    
    .btn { padding: 10px 20px; border-radius: 4px; cursor: pointer; font-size: 0.95rem; text-decoration: none; text-align: center; font-weight: 500; transition: all 0.2s; }
    .btn-outline { border: 1px solid #007bff; color: #007bff; background: transparent; }
    .btn-outline:hover { background: #007bff; color: white; }
    .btn-primary { background-color: #007bff; color: white; border: none; }
    .btn-primary:hover { background-color: #0056b3; }
    .btn-sm { padding: 5px 10px; font-size: 0.85rem; }
    
    .pagination { display: flex; justify-content: center; align-items: center; gap: 15px; margin-top: 30px; }
    
    .loader { text-align: center; padding: 40px; color: #666; }
    .empty-state { text-align: center; padding: 40px; background: white; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); color: #666; line-height: 1.6; }
    .alert { padding: 15px; border-radius: 4px; margin-bottom: 20px; }
    .alert-danger { background: #f8d7da; color: #721c24; border: 1px solid #f5c2c7; }
    
    @media (max-width: 600px) {
      .order-body { flex-direction: column; align-items: flex-start; }
      .order-actions { width: 100%; }
      .order-actions .btn { display: block; width: 100%; box-sizing: border-box; }
    }
  `]
})
export class OrderListComponent implements OnInit {
  private orderService = inject(OrderService);
  private cdr = inject(ChangeDetectorRef);

  orders: any[] = [];
  pagination: any = null;
  isLoading = true;
  error = '';
  page = 1;

  ngOnInit() {
    this.loadOrders();
  }

  loadOrders() {
    this.isLoading = true;
    this.error = '';
    
    this.orderService.getOrders(this.page).subscribe({
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
        this.error = 'Failed to load your orders.';
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
    if (!status) return '';
    return `badge-${status.toLowerCase()}`;
  }
}
