import { Component, OnInit, inject, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterModule } from '@angular/router';
import { ProductService } from '../../../core/services/product.service';
import { CartService } from '../../../core/services/cart.service';
import { Product } from '../../../core/models/catalog.model';

@Component({
  selector: 'app-product-detail',
  standalone: true,
  imports: [CommonModule, RouterModule],
  template: `
    <div class="product-detail-container">
      <div *ngIf="isLoading" class="loader">Loading product details...</div>
      <div *ngIf="error" class="alert alert-danger">{{ error }}</div>

      <div *ngIf="!isLoading && product" class="product-detail">
        <div class="product-image">
          <img *ngIf="product.image" [src]="product.image" alt="{{ product.name }}">
          <div *ngIf="!product.image" class="placeholder-image">No Image Available</div>
        </div>
        
        <div class="product-info">
          <h2>{{ product.name }}</h2>
          <p class="category-badge" *ngIf="product.category">{{ product.category.name }}</p>
          <p class="price">\${{ product.price }}</p>
          
          <div class="description">
            <h3>Description</h3>
            <p>{{ product.description }}</p>
          </div>

          <div class="stock-status" [ngClass]="{'in-stock': product.stock > 0, 'out-of-stock': product.stock === 0}">
            {{ product.stock > 0 ? 'In Stock (' + product.stock + ' available)' : 'Out of Stock' }}
          </div>

          <div class="actions" *ngIf="product.stock > 0">
            <button class="btn btn-primary" (click)="addToCart()" [disabled]="isAddingToCart">
              {{ isAddingToCart ? 'Adding...' : 'Add to Cart' }}
            </button>
            <span *ngIf="addedSuccess" class="text-success ml-2">Added successfully!</span>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .product-detail-container { max-width: 1000px; margin: 0 auto; padding: 20px; }
    .product-detail { display: flex; gap: 40px; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
    .product-image { flex: 1; background: #f9f9f9; display: flex; align-items: center; justify-content: center; border-radius: 8px; min-height: 400px; }
    .product-image img { max-width: 100%; height: auto; border-radius: 8px; }
    .placeholder-image { color: #999; font-size: 1.2rem; }
    .product-info { flex: 1; }
    .category-badge { display: inline-block; background: #e9ecef; padding: 5px 10px; border-radius: 15px; font-size: 0.9rem; color: #495057; margin-bottom: 15px; }
    .price { font-size: 2rem; color: #007bff; font-weight: bold; margin-bottom: 20px; }
    .description { margin-bottom: 20px; line-height: 1.6; color: #555; }
    .stock-status { font-weight: bold; margin-bottom: 20px; }
    .in-stock { color: #28a745; }
    .out-of-stock { color: #dc3545; }
    .actions { display: flex; align-items: center; gap: 15px; }
    .ml-2 { margin-left: 10px; }
    .text-success { color: #28a745; font-weight: bold; }
    .loader { text-align: center; padding: 40px; font-size: 1.2rem; color: #666; }
    
    @media (max-width: 768px) {
      .product-detail { flex-direction: column; }
    }
  `]
})
export class ProductDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private productService = inject(ProductService);
  private cartService = inject(CartService);
  private cdr = inject(ChangeDetectorRef);

  product: Product | null = null;
  isLoading = true;
  error = '';
  isAddingToCart = false;
  addedSuccess = false;

  ngOnInit() {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      this.loadProduct(+id);
    }
  }

  loadProduct(id: number) {
    this.isLoading = true;
    this.productService.getProduct(id).subscribe({
      next: (res: any) => {
        if (res && res.data) {
          this.product = res.data;
        } else if (res && !res.success) {
          this.product = res; // Fallback if backend returned product directly
        }
        this.isLoading = false;
        this.cdr.detectChanges();
      },
      error: (err) => {
        this.error = 'Failed to load product details.';
        this.isLoading = false;
        this.cdr.detectChanges();
      }
    });
  }

  addToCart() {
    if (!this.product) return;
    this.isAddingToCart = true;
    this.addedSuccess = false;
    this.cdr.detectChanges();

    this.cartService.addToCart(this.product.id, 1).subscribe({
      next: () => {
        this.isAddingToCart = false;
        this.addedSuccess = true;
        this.cdr.detectChanges();
        setTimeout(() => {
          this.addedSuccess = false;
          this.cdr.detectChanges();
        }, 3000);
      },
      error: (err) => {
        this.isAddingToCart = false;
        if (err.status === 401) {
          this.error = 'You must be logged in to add items to the cart.';
        } else {
          this.error = 'Failed to add item to cart.';
        }
        this.cdr.detectChanges();
      }
    });
  }
}
