import { Component, OnInit, inject, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterModule } from '@angular/router';
import { CartService } from '../../core/services/cart.service';
import { OrderService } from '../../core/services/order.service';
import { Cart } from '../../core/models/cart.model';

@Component({
  selector: 'app-checkout',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterModule],
  template: `
    <div class="checkout-page">
      <h2>Checkout</h2>

      <div *ngIf="isLoading" class="loader">Loading...</div>
      <div *ngIf="error" class="alert alert-danger">{{ error }}</div>

      <div class="checkout-container" *ngIf="!isLoading && cart && cart.items.length > 0">
        <!-- Billing Details -->
        <div class="billing-section">
          <h3>Billing Details</h3>
          <form [formGroup]="checkoutForm" (ngSubmit)="placeOrder()">
            <div class="form-group">
              <label for="address">Shipping Address <span class="required">*</span></label>
              <input type="text" id="address" formControlName="address" class="form-control" [class.is-invalid]="isInvalid('address')">
              <div class="invalid-feedback" *ngIf="isInvalid('address')">Shipping address is required.</div>
            </div>

            <div class="form-row">
              <div class="form-group flex-1">
                <label for="city">City <span class="required">*</span></label>
                <input type="text" id="city" formControlName="city" class="form-control" [class.is-invalid]="isInvalid('city')">
                <div class="invalid-feedback" *ngIf="isInvalid('city')">City is required.</div>
              </div>
              <div class="form-group flex-1">
                <label for="postal_code">Postal Code <span class="required">*</span></label>
                <input type="text" id="postal_code" formControlName="postal_code" class="form-control" [class.is-invalid]="isInvalid('postal_code')">
                <div class="invalid-feedback" *ngIf="isInvalid('postal_code')">Postal Code is required.</div>
              </div>
            </div>

            <div class="form-group">
              <label for="country">Country <span class="required">*</span></label>
              <input type="text" id="country" formControlName="country" class="form-control" [class.is-invalid]="isInvalid('country')">
              <div class="invalid-feedback" *ngIf="isInvalid('country')">Country is required.</div>
            </div>

            <!-- Payment Information (Mock UI) -->
            <h3 class="mt-4">Payment Method</h3>
            <div class="payment-box">
              <p>Cash on Delivery (COD) is selected by default for this practical.</p>
            </div>

            <button type="submit" class="btn btn-primary btn-block mt-4" [disabled]="checkoutForm.invalid || isPlacingOrder">
              {{ isPlacingOrder ? 'Placing Order...' : 'Place Order' }}
            </button>
          </form>
        </div>

        <!-- Order Summary -->
        <div class="summary-section">
          <h3>Order Summary</h3>
          <div class="summary-card">
            <div class="summary-item" *ngFor="let item of cart.items">
              <div class="item-info">
                <strong>{{ item.product?.name || 'Product ' + item.product_id }}</strong>
                <span class="item-qty">x{{ item.quantity }}</span>
              </div>
              <div class="item-price">\${{ item.subtotal }}</div>
            </div>
            
            <div class="summary-divider"></div>
            
            <div class="summary-row">
              <span>Subtotal</span>
              <span>\${{ cart.total }}</span>
            </div>
            <div class="summary-row total-row">
              <span>Total</span>
              <span>\${{ cart.total }}</span>
            </div>
          </div>
        </div>
      </div>

      <div *ngIf="!isLoading && (!cart || cart.items.length === 0)" class="empty-state">
        Your cart is empty. Please add items before checking out.
        <br><br>
        <a routerLink="/products" class="btn btn-primary">Browse Products</a>
      </div>
    </div>
  `,
  styles: [`
    .checkout-page { padding-bottom: 40px; }
    h2 { color: #333; margin-bottom: 25px; }
    h3 { color: #333; margin-bottom: 15px; font-size: 1.2rem; }
    .mt-4 { margin-top: 25px; }
    
    .checkout-container { display: flex; gap: 30px; flex-wrap: wrap; align-items: flex-start; }
    .billing-section { flex: 2; min-width: 300px; background: white; padding: 25px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
    .summary-section { flex: 1; min-width: 300px; position: sticky; top: 20px; }
    
    .form-group { margin-bottom: 15px; }
    .form-row { display: flex; gap: 15px; }
    .flex-1 { flex: 1; }
    
    label { display: block; margin-bottom: 8px; font-weight: 500; color: #555; }
    .required { color: #dc3545; }
    .form-control { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; font-size: 1rem; }
    .form-control:focus { outline: none; border-color: #007bff; }
    .form-control.is-invalid { border-color: #dc3545; }
    .invalid-feedback { color: #dc3545; font-size: 0.85rem; margin-top: 5px; }
    
    .payment-box { background: #f8f9fa; padding: 15px; border-radius: 4px; border: 1px solid #eee; color: #666; font-size: 0.9rem; }
    
    .summary-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
    .summary-item { display: flex; justify-content: space-between; margin-bottom: 15px; }
    .item-info { display: flex; flex-direction: column; }
    .item-qty { color: #666; font-size: 0.85rem; margin-top: 3px; }
    .summary-divider { height: 1px; background: #eee; margin: 15px 0; }
    .summary-row { display: flex; justify-content: space-between; margin-bottom: 10px; font-size: 1.05rem; }
    .total-row { font-weight: bold; font-size: 1.25rem; margin-top: 15px; border-top: 1px solid #eee; padding-top: 15px; }
    
    .btn { padding: 12px 20px; border: none; border-radius: 4px; cursor: pointer; font-size: 1rem; text-decoration: none; text-align: center; font-weight: 500; transition: background 0.2s; }
    .btn-primary { background-color: #007bff; color: white; }
    .btn-primary:hover { background-color: #0056b3; }
    .btn-primary:disabled { background-color: #a0cbf7; cursor: not-allowed; }
    .btn-block { display: block; width: 100%; }
    
    .loader { text-align: center; padding: 40px; color: #666; }
    .empty-state { text-align: center; padding: 40px; background: white; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); color: #666; line-height: 1.6; }
    .alert { padding: 15px; border-radius: 4px; margin-bottom: 20px; }
    .alert-danger { background: #f8d7da; color: #721c24; border: 1px solid #f5c2c7; }
  `]
})
export class CheckoutComponent implements OnInit {
  private cartService = inject(CartService);
  private orderService = inject(OrderService);
  private fb = inject(FormBuilder);
  private router = inject(Router);
  private cdr = inject(ChangeDetectorRef);

  cart: Cart | null = null;
  isLoading = true;
  isPlacingOrder = false;
  error = '';

  checkoutForm = this.fb.group({
    address: ['', Validators.required],
    city: ['', Validators.required],
    postal_code: ['', Validators.required],
    country: ['', Validators.required]
  });

  ngOnInit() {
    this.loadCart();
  }

  loadCart() {
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
      error: () => {
        this.error = 'Failed to load cart for checkout.';
        this.isLoading = false;
        this.cdr.detectChanges();
      }
    });
  }

  isInvalid(field: string): boolean {
    const control = this.checkoutForm.get(field);
    return !!(control && control.invalid && (control.dirty || control.touched));
  }

  placeOrder() {
    if (this.checkoutForm.invalid) {
      this.checkoutForm.markAllAsTouched();
      return;
    }

    this.isPlacingOrder = true;
    this.error = '';
    this.cdr.detectChanges();

    const orderData = {
      shipping_address: this.checkoutForm.value.address,
      billing_address: this.checkoutForm.value.address, // Same for simplicity
      city: this.checkoutForm.value.city,
      postal_code: this.checkoutForm.value.postal_code,
      country: this.checkoutForm.value.country
    };

    this.orderService.createOrder(orderData).subscribe({
      next: (res: any) => {
        // Clear cart count natively
        this.cartService.clearCart().subscribe(() => {
          this.router.navigate(['/orders']);
        });
      },
      error: (err) => {
        this.error = err.error?.message || 'Failed to place order. Please try again.';
        this.isPlacingOrder = false;
        this.cdr.detectChanges();
      }
    });
  }
}
