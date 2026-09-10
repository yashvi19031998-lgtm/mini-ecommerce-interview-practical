import { Component, OnInit, inject, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterModule } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { AdminService } from '../../../core/services/admin.service';

@Component({
  selector: 'app-admin-order-detail',
  standalone: true,
  imports: [CommonModule, RouterModule, FormsModule],
  template: `
    <div class="admin-page">
      <div class="page-header">
        <h2>Order Details #{{ orderId }}</h2>
        <a routerLink="/admin/orders" class="btn btn-secondary">Back to Orders</a>
      </div>

      <div *ngIf="error" class="alert alert-danger">{{ error }}</div>
      <div *ngIf="successMsg" class="alert alert-success">{{ successMsg }}</div>
      <div *ngIf="isLoading" class="loader">Loading order details...</div>

      <div *ngIf="!isLoading && order">
        <div class="order-layout">
          <!-- Main Content -->
          <div class="order-main">
            <div class="card mb-4">
              <div class="card-header">
                <h3>Order Items</h3>
              </div>
              <div class="card-body">
                <table class="table">
                  <thead>
                    <tr>
                      <th>Product</th>
                      <th>Price</th>
                      <th>Quantity</th>
                      <th>Subtotal</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr *ngFor="let item of order.items">
                      <td>
                        <strong>{{ item.product_name }}</strong>
                        <div *ngIf="item.product" class="text-muted"><small>Current Catalog: {{ item.product.name }}</small></div>
                      </td>
                      <td>\${{ item.price }}</td>
                      <td>{{ item.quantity }}</td>
                      <td>\${{ item.price * item.quantity | number:'1.2-2' }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
            
            <div class="card">
              <div class="card-header">
                <h3>Summary</h3>
              </div>
              <div class="card-body">
                <div class="summary-row">
                  <span>Subtotal</span>
                  <span>\${{ order.subtotal }}</span>
                </div>
                <div class="summary-row total-row">
                  <span>Total</span>
                  <span>\${{ order.total }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Sidebar -->
          <div class="order-sidebar">
            <div class="card mb-4">
              <div class="card-header">
                <h3>Customer Information</h3>
              </div>
              <div class="card-body" *ngIf="order.user">
                <p><strong>Name:</strong> {{ order.user.name }}</p>
                <p><strong>Email:</strong> {{ order.user.email }}</p>
                <p><strong>Order Date:</strong> {{ order.created_at | date:'medium' }}</p>
              </div>
            </div>

            <div class="card">
              <div class="card-header">
                <h3>Update Status</h3>
              </div>
              <div class="card-body">
                <p><strong>Current Status:</strong> <span class="badge" [ngClass]="getStatusClass(order.status)">{{ order.status }}</span></p>
                
                <div class="form-group mt-3">
                  <label for="statusSelect">Change Status to:</label>
                  <select id="statusSelect" [(ngModel)]="newStatus" class="form-control">
                    <option value="pending">Pending</option>
                    <option value="processing">Processing</option>
                    <option value="shipped">Shipped</option>
                    <option value="delivered">Delivered</option>
                    <option value="cancelled">Cancelled</option>
                  </select>
                </div>
                
                <button class="btn btn-primary btn-block mt-3" [disabled]="isUpdating || newStatus === order.status" (click)="updateStatus()">
                  {{ isUpdating ? 'Updating...' : 'Update Status' }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
    h2 { margin: 0; color: #333; }
    h3 { margin: 0; font-size: 1.1rem; color: #333; }
    
    .order-layout { display: flex; gap: 20px; flex-wrap: wrap; }
    .order-main { flex: 2; min-width: 300px; }
    .order-sidebar { flex: 1; min-width: 250px; }
    
    .card { background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); overflow: hidden; }
    .mb-4 { margin-bottom: 20px; }
    .card-header { background: #f8f9fa; padding: 15px 20px; border-bottom: 1px solid #eee; }
    .card-body { padding: 20px; }
    
    .table { width: 100%; border-collapse: collapse; }
    .table th, .table td { padding: 12px 15px; text-align: left; border-bottom: 1px solid #eee; }
    .table th { font-weight: 600; color: #555; }
    
    .text-muted { color: #6c757d; }
    
    .summary-row { display: flex; justify-content: space-between; margin-bottom: 10px; font-size: 1.05rem; }
    .total-row { border-top: 1px solid #eee; padding-top: 10px; font-weight: bold; font-size: 1.2rem; }
    
    .form-group { margin-bottom: 15px; }
    label { display: block; margin-bottom: 8px; font-weight: 500; color: #333; }
    .form-control { width: 100%; padding: 10px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
    .mt-3 { margin-top: 15px; }
    
    .badge { padding: 5px 10px; border-radius: 20px; font-size: 0.85rem; font-weight: 500; text-transform: capitalize; }
    .badge-pending { background-color: #ffeeba; color: #856404; }
    .badge-processing { background-color: #b8daff; color: #004085; }
    .badge-shipped { background-color: #d1ecf1; color: #0c5460; }
    .badge-delivered { background-color: #d4edda; color: #155724; }
    .badge-cancelled { background-color: #f8d7da; color: #721c24; }
    
    .btn { padding: 10px 15px; border: none; border-radius: 4px; cursor: pointer; font-size: 1rem; text-decoration: none; text-align: center; }
    .btn-primary { background-color: #007bff; color: white; }
    .btn-primary:disabled { background-color: #a0cbf7; cursor: not-allowed; }
    .btn-secondary { background-color: #6c757d; color: white; }
    .btn-block { display: block; width: 100%; }
    
    .loader { text-align: center; padding: 40px; color: #666; }
    .alert { padding: 15px; border-radius: 4px; margin-bottom: 15px; }
    .alert-danger { background: #f8d7da; color: #721c24; border: 1px solid #f5c2c7; }
    .alert-success { background: #d1e7dd; color: #0f5132; border: 1px solid #badbcc; }
  `]
})
export class AdminOrderDetailComponent implements OnInit {
  private adminService = inject(AdminService);
  private route = inject(ActivatedRoute);
  private cdr = inject(ChangeDetectorRef);

  orderId: number | null = null;
  order: any = null;
  isLoading = true;
  isUpdating = false;
  error = '';
  successMsg = '';
  newStatus = '';

  ngOnInit() {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      this.orderId = +id;
      this.loadOrder(this.orderId);
    }
  }

  loadOrder(id: number) {
    this.isLoading = true;
    this.error = '';
    this.adminService.getOrder(id).subscribe({
      next: (res: any) => {
        if (res && res.data) {
          this.order = res.data;
        } else {
          this.order = res;
        }
        this.newStatus = this.order.status;
        this.isLoading = false;
        this.cdr.detectChanges();
      },
      error: () => {
        this.error = 'Failed to load order details.';
        this.isLoading = false;
        this.cdr.detectChanges();
      }
    });
  }

  updateStatus() {
    if (!this.orderId || !this.newStatus) return;
    
    this.isUpdating = true;
    this.error = '';
    this.successMsg = '';
    this.cdr.detectChanges();

    this.adminService.updateOrderStatus(this.orderId, this.newStatus).subscribe({
      next: () => {
        this.successMsg = 'Order status updated successfully.';
        this.isUpdating = false;
        this.loadOrder(this.orderId!); // reload
      },
      error: (err: any) => {
        this.error = err.error?.message || 'Failed to update status.';
        this.isUpdating = false;
        this.cdr.detectChanges();
      }
    });
  }

  getStatusClass(status: string): string {
    return `badge-${status.toLowerCase()}`;
  }
}
