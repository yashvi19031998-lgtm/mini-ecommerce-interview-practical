import { Component, OnInit, inject, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { CartService } from '../../core/services/cart.service';
import { Cart } from '../../core/models/cart.model';

@Component({
  selector: 'app-cart',
  standalone: true,
  imports: [CommonModule, RouterModule],
  template: `
    <div>
      <h2>Your Cart</h2>
      
      <div *ngIf="isLoading" class="loader">Loading cart...</div>

      <div *ngIf="error" class="alert alert-danger">{{ error }}</div>

      <div *ngIf="!isLoading && cart?.items?.length">
        <table class="table">
          <thead>
            <tr>
              <th>Product</th>
              <th>Price</th>
              <th>Quantity</th>
              <th>Subtotal</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            <tr *ngFor="let item of cart?.items">
              <td>{{ item.product?.name || item.product_id }}</td>
              <td>\${{ item.product?.price }}</td>
              <td>{{ item.quantity }}</td>
              <td>\${{ item.subtotal }}</td>
              <td>
                <button class="btn btn-sm btn-danger" (click)="removeItem(item.id)">Remove</button>
              </td>
            </tr>
          </tbody>
          <tfoot>
            <tr>
              <td colspan="3" class="text-right"><strong>Total:</strong></td>
              <td colspan="2"><strong>\${{ cart?.total }}</strong></td>
            </tr>
          </tfoot>
        </table>

        <div class="cart-actions">
          <button class="btn btn-danger" (click)="clearCart()">Clear Cart</button>
          <a routerLink="/checkout" class="btn btn-primary">Proceed to Checkout</a>
        </div>
      </div>

      <div *ngIf="!isLoading && (!cart || !cart.items || cart.items.length === 0)" class="empty-state">
        Your cart is empty. <a routerLink="/products">Browse products</a>
      </div>
    </div>
  `,
  styles: [`
    .table { width: 100%; border-collapse: collapse; margin-top: 20px; }
    .table th, .table td { padding: 12px; border-bottom: 1px solid #ddd; text-align: left; }
    .text-right { text-align: right; }
    .cart-actions { display: flex; justify-content: space-between; margin-top: 20px; }
    .btn-sm { padding: 5px 10px; font-size: 0.8rem; }
    .btn-danger { background-color: #dc3545; color: white; }
    .btn-danger:hover { background-color: #c82333; }
    .loader { text-align: center; padding: 20px; }
    .empty-state { text-align: center; padding: 40px; background: #f9f9f9; border-radius: 8px; }
  `]
})
export class CartComponent implements OnInit {
  private cartService = inject(CartService);
  private cdr = inject(ChangeDetectorRef);

  cart: Cart | null = null;
  error = '';
  isLoading = true;

  ngOnInit() {
    this.loadCart();
  }

  loadCart() {
    this.isLoading = true;
    this.cdr.detectChanges();
    this.cartService.getCart().subscribe({
      next: (res: any) => {
        if (res && res.data) {
          this.cart = res.data;
        } else {
          this.cart = res;
        }
        this.isLoading = false;
        this.cdr.detectChanges();
      },
      error: (err) => {
        this.error = 'Failed to load cart.';
        this.isLoading = false;
        this.cdr.detectChanges();
      }
    });
  }

  updateQuantity(itemId: number, quantity: number) {
    if (quantity < 1) return;
    this.cartService.updateItem(itemId, quantity).subscribe(() => this.loadCart());
  }

  removeItem(itemId: number) {
    if (confirm('Are you sure you want to remove this item?')) {
      this.cartService.removeItem(itemId).subscribe(() => this.loadCart());
    }
  }

  clearCart() {
    if (confirm('Are you sure you want to clear your entire cart?')) {
      this.cartService.clearCart().subscribe(() => this.loadCart());
    }
  }
}
