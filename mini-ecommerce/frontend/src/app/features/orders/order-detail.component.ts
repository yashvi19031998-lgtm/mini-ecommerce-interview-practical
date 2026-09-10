import { Component, OnInit, inject, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterModule } from '@angular/router';
import { OrderService } from '../../core/services/order.service';

@Component({
  selector: 'app-order-detail',
  standalone: true,
  imports: [CommonModule, RouterModule],
  template: `
    <div class="order-detail-page">
      <div class="page-header">
        <a routerLink="/orders" class="back-link">&larr; Back to Orders</a>
        <h2>Order Details</h2>
      </div>

      <div *ngIf="isLoading" class="loader">Loading order...</div>
      <div *ngIf="error" class="alert alert-danger">{{ error }}</div>

      <div *ngIf="!isLoading && order" class="order-container">
        
        <!-- Status Banner -->
        <div class="status-banner" [ngClass]="'banner-' + order.status">
          <div class="status-info">
            <h3>Order #{{ order.id }}</h3>
            <p>Placed on {{ order.created_at | date:'medium' }}</p>
          </div>
          <div class="status-badge">
            <span class="badge" [ngClass]="getStatusClass(order.status)">{{ order.status }}</span>
          </div>
        </div>

        <div class="layout-grid">
          <!-- Items List -->
          <div class="items-section">
            <div class="card">
              <div class="card-header">
                <h3>Items in your order</h3>
              </div>
              <div class="card-body p-0">
                <table class="table">
                  <thead>
                    <tr>
                      <th>Product</th>
                      <th class="text-center">Price</th>
                      <th class="text-center">Qty</th>
                      <th class="text-right">Subtotal</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr *ngFor="let item of order.items">
                      <td>
                        <div class="product-info">
                          <img *ngIf="item.product?.image" [src]="item.product.image" width="50" height="50" alt="{{ item.product_name }}">
                          <div *ngIf="!item.product?.image" class="no-img">No Img</div>
                          <div>
                            <strong>{{ item.product_name }}</strong>
                          </div>
                        </div>
                      </td>
                      <td class="text-center">\${{ item.price }}</td>
                      <td class="text-center">{{ item.quantity }}</td>
                      <td class="text-right">\${{ item.price * item.quantity | number:'1.2-2' }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <!-- Summary & Shipping -->
          <div class="sidebar-section">
            <div class="card mb-20">
              <div class="card-header">
                <h3>Order Summary</h3>
              </div>
              <div class="card-body">
                <div class="summary-row">
                  <span>Subtotal</span>
                  <span>\${{ order.subtotal }}</span>
                </div>
                <div class="summary-row">
                  <span>Shipping</span>
                  <span>\$0.00</span>
                </div>
                <div class="summary-row total-row">
                  <span>Total</span>
                  <span>\${{ order.total }}</span>
                </div>
              </div>
            </div>

            <div class="card">
              <div class="card-header">
                <h3>Shipping Details</h3>
              </div>
              <div class="card-body">
                <address class="shipping-address">
                  {{ order.shipping_address }}<br>
                  {{ order.city }}, {{ order.postal_code }}<br>
                  {{ order.country }}
                </address>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .order-detail-page { padding-bottom: 40px; max-width: 1000px; margin: 0 auto; }
    .page-header { margin-bottom: 20px; }
    .back-link { color: #007bff; text-decoration: none; font-size: 0.95rem; margin-bottom: 10px; display: inline-block; }
    .back-link:hover { text-decoration: underline; }
    h2 { color: #333; margin: 0; }
    
    .status-banner { display: flex; justify-content: space-between; align-items: center; padding: 25px; border-radius: 8px; margin-bottom: 25px; color: white; }
    .banner-pending { background-color: #6c757d; }
    .banner-processing { background-color: #0dcaf0; color: #000; }
    .banner-shipped { background-color: #0d6efd; }
    .banner-delivered { background-color: #198754; }
    .banner-cancelled { background-color: #dc3545; }
    
    .status-info h3 { margin: 0 0 5px 0; font-size: 1.4rem; color: inherit; }
    .status-info p { margin: 0; opacity: 0.9; }
    
    .badge { padding: 8px 16px; border-radius: 20px; font-size: 1rem; font-weight: 600; text-transform: uppercase; background: rgba(255,255,255,0.9); }
    .badge-pending { color: #6c757d; }
    .badge-processing { color: #0dcaf0; }
    .badge-shipped { color: #0d6efd; }
    .badge-delivered { color: #198754; }
    .badge-cancelled { color: #dc3545; }
    
    .layout-grid { display: flex; gap: 25px; flex-wrap: wrap; align-items: flex-start; }
    .items-section { flex: 2; min-width: 300px; }
    .sidebar-section { flex: 1; min-width: 250px; }
    
    .card { background: white; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); overflow: hidden; }
    .mb-20 { margin-bottom: 20px; }
    .card-header { background: #f8f9fa; padding: 15px 20px; border-bottom: 1px solid #eaeaea; }
    .card-header h3 { margin: 0; font-size: 1.1rem; color: #333; }
    .card-body { padding: 20px; }
    .p-0 { padding: 0; }
    
    .table { width: 100%; border-collapse: collapse; }
    .table th, .table td { padding: 15px; border-bottom: 1px solid #eaeaea; }
    .table th { font-weight: 600; color: #555; background: #fcfcfc; text-align: left; }
    .text-center { text-align: center !important; }
    .text-right { text-align: right !important; }
    
    .product-info { display: flex; align-items: center; gap: 15px; }
    .product-info img { object-fit: cover; border-radius: 4px; border: 1px solid #eee; }
    .no-img { width: 50px; height: 50px; background: #f4f4f4; border-radius: 4px; display: flex; align-items: center; justify-content: center; font-size: 0.7rem; color: #999; }
    
    .summary-row { display: flex; justify-content: space-between; margin-bottom: 12px; font-size: 1.05rem; color: #555; }
    .total-row { border-top: 1px solid #eaeaea; padding-top: 15px; margin-top: 10px; font-weight: bold; font-size: 1.25rem; color: #333; }
    
    .shipping-address { font-style: normal; line-height: 1.6; color: #555; }
    
    .loader { text-align: center; padding: 40px; color: #666; }
    .alert { padding: 15px; border-radius: 4px; margin-bottom: 20px; }
    .alert-danger { background: #f8d7da; color: #721c24; border: 1px solid #f5c2c7; }
    
    @media (max-width: 768px) {
      .status-banner { flex-direction: column; align-items: flex-start; gap: 15px; }
    }
  `]
})
export class OrderDetailComponent implements OnInit {
  private orderService = inject(OrderService);
  private route = inject(ActivatedRoute);
  private cdr = inject(ChangeDetectorRef);

  orderId: number | null = null;
  order: any = null;
  isLoading = true;
  error = '';

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
    this.orderService.getOrder(id).subscribe({
      next: (res: any) => {
        if (res && res.data) {
          this.order = res.data;
        } else {
          this.order = res;
        }
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

  getStatusClass(status: string): string {
    if (!status) return '';
    return `badge-${status.toLowerCase()}`;
  }
}
