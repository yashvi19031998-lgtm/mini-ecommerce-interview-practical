import { Component, OnInit, inject, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { ProductService } from '../../../core/services/product.service';
import { Product } from '../../../core/models/catalog.model';

@Component({
  selector: 'app-product-list',
  standalone: true,
  imports: [CommonModule, RouterModule],
  template: `
    <div>
      <h2>Products</h2>
      <div *ngIf="isLoading" class="loader">Loading products...</div>
      
      <div *ngIf="error" class="alert alert-danger">{{ error }}</div>

      <div class="product-grid" *ngIf="!isLoading && products.length > 0">
        <div class="product-card" *ngFor="let product of products">
          <div class="product-image">
            <img *ngIf="product.image" [src]="product.image" alt="{{ product.name }}">
            <div *ngIf="!product.image" class="placeholder-image">No Image</div>
          </div>
          <div class="product-info">
            <h3>{{ product.name }}</h3>
            <p class="price">\${{ product.price }}</p>
            <a [routerLink]="['/products', product.id]" class="btn btn-primary">View Details</a>
          </div>
        </div>
      </div>

      <div *ngIf="!isLoading && products.length === 0" class="empty-state">
        No products found.
      </div>
    </div>
  `,
  styles: [`
    .product-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 20px; }
    .product-card { border: 1px solid #ddd; border-radius: 8px; overflow: hidden; background: white; }
    .product-image { height: 200px; background: #eee; display: flex; align-items: center; justify-content: center; }
    .product-image img { width: 100%; height: 100%; object-fit: cover; }
    .placeholder-image { color: #999; }
    .product-info { padding: 15px; }
    .price { font-weight: bold; font-size: 1.2rem; margin: 10px 0; color: #007bff; }
    .loader { text-align: center; padding: 20px; color: #666; }
    .empty-state { text-align: center; padding: 40px; color: #666; background: #f9f9f9; border-radius: 8px; }
  `]
})
export class ProductListComponent implements OnInit {
  private productService = inject(ProductService);

  products: Product[] = [];
  isLoading = true;
  error = '';

  ngOnInit() {
    this.loadProducts();
  }

  private cdr = inject(ChangeDetectorRef);

  loadProducts() {
    this.productService.getProducts().subscribe({
      next: (res: any) => {
        console.log('API Response:', res);
        
        // Handle different possible response structures just in case
        let productsData = [];
        if (res && res.data && Array.isArray(res.data.products)) {
          productsData = res.data.products;
        } else if (res && Array.isArray(res.data)) {
          productsData = res.data;
        } else if (res && Array.isArray(res.products)) {
          productsData = res.products;
        } else if (Array.isArray(res)) {
          productsData = res;
        }

        this.products = productsData;
        this.isLoading = false;
        this.cdr.detectChanges(); // Force view update
      },
      error: (err) => {
        console.error('API Error:', err);
        this.error = 'Failed to load products.';
        this.cdr.detectChanges();
      }
    });
  }
}
