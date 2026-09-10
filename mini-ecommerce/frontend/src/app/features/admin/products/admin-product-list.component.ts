import { Component, OnInit, inject, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { AdminService } from '../../../core/services/admin.service';

@Component({
  selector: 'app-admin-product-list',
  standalone: true,
  imports: [CommonModule, RouterModule, FormsModule],
  template: `
    <div class="admin-page">
      <div class="page-header">
        <h2>Manage Products</h2>
        <a routerLink="/admin/products/new" class="btn btn-primary">Add New Product</a>
      </div>

      <div class="filters-card">
        <div class="filter-group">
          <input type="text" [(ngModel)]="search" placeholder="Search products..." class="form-control" (keyup.enter)="loadProducts()">
        </div>
        <div class="filter-group">
          <select [(ngModel)]="category_id" class="form-control" (change)="loadProducts()">
            <option value="">All Categories</option>
            <option *ngFor="let cat of categories" [value]="cat.id">{{ cat.name }}</option>
          </select>
        </div>
        <div class="filter-group">
          <select [(ngModel)]="status" class="form-control" (change)="loadProducts()">
            <option value="">All Statuses</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </div>
        <button class="btn btn-secondary" (click)="loadProducts()">Apply</button>
      </div>

      <div *ngIf="error" class="alert alert-danger">{{ error }}</div>
      <div *ngIf="successMsg" class="alert alert-success">{{ successMsg }}</div>

      <div class="table-responsive" *ngIf="!isLoading && products.length > 0">
        <table class="table">
          <thead>
            <tr>
              <th>Image</th>
              <th>Name</th>
              <th>Category</th>
              <th>Price</th>
              <th>Stock</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr *ngFor="let prod of products">
              <td>
                <img *ngIf="prod.image" [src]="prod.image" alt="{{ prod.name }}" width="50" height="50" style="object-fit: cover; border-radius: 4px;">
                <div *ngIf="!prod.image" class="no-img">No Img</div>
              </td>
              <td><strong>{{ prod.name }}</strong></td>
              <td>{{ prod.category?.name || '-' }}</td>
              <td>\${{ prod.price }}</td>
              <td>
                <span [class.text-danger]="prod.stock < 10">{{ prod.stock }}</span>
              </td>
              <td><span class="badge" [ngClass]="prod.status === 'active' ? 'badge-success' : 'badge-danger'">{{ prod.status }}</span></td>
              <td class="actions">
                <a [routerLink]="['/admin/products', prod.id, 'edit']" class="btn btn-sm btn-info">Edit</a>
                <button class="btn btn-sm btn-danger" (click)="deleteProduct(prod.id)">Delete</button>
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

      <div *ngIf="isLoading" class="loader">Loading products...</div>
      
      <div *ngIf="!isLoading && products.length === 0" class="empty-state">
        No products found matching your criteria.
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
    
    .no-img { width: 50px; height: 50px; background: #eee; color: #999; display: flex; align-items: center; justify-content: center; font-size: 0.7rem; border-radius: 4px; }
    
    .badge { padding: 5px 10px; border-radius: 20px; font-size: 0.8rem; font-weight: 500; }
    .badge-success { background-color: #d4edda; color: #155724; }
    .badge-danger { background-color: #f8d7da; color: #721c24; }
    .text-danger { color: #dc3545; font-weight: bold; }
    
    .actions { display: flex; gap: 8px; }
    .btn-sm { padding: 5px 10px; font-size: 0.85rem; }
    .btn-info { background-color: #17a2b8; color: white; border: none; border-radius: 4px; text-decoration: none; cursor: pointer; }
    .btn-danger { background-color: #dc3545; color: white; border: none; border-radius: 4px; cursor: pointer; }
    .btn-primary { background-color: #007bff; color: white; text-decoration: none; padding: 10px 20px; border-radius: 4px; }
    .btn-secondary { background-color: #6c757d; color: white; padding: 10px 15px; border: none; border-radius: 4px; cursor: pointer; }
    
    .pagination { display: flex; justify-content: center; align-items: center; gap: 15px; margin-top: 20px; }
    .loader { text-align: center; padding: 40px; color: #666; }
    .empty-state { text-align: center; padding: 40px; background: white; border-radius: 8px; color: #666; }
    .alert { padding: 15px; border-radius: 4px; margin-bottom: 15px; }
    .alert-danger { background: #f8d7da; color: #721c24; border: 1px solid #f5c2c7; }
    .alert-success { background: #d1e7dd; color: #0f5132; border: 1px solid #badbcc; }
  `]
})
export class AdminProductListComponent implements OnInit {
  private adminService = inject(AdminService);
  private cdr = inject(ChangeDetectorRef);

  products: any[] = [];
  categories: any[] = [];
  pagination: any = null;
  isLoading = true;
  error = '';
  successMsg = '';

  // Filters
  search = '';
  category_id = '';
  status = '';
  page = 1;

  ngOnInit() {
    this.loadCategories();
    this.loadProducts();
  }

  loadCategories() {
    this.adminService.getCategories().subscribe({
      next: (res: any) => {
        if (res && res.data) {
          if (Array.isArray(res.data)) this.categories = res.data;
          else if (Array.isArray(res.data.categories)) this.categories = res.data.categories;
        } else if (Array.isArray(res)) {
          this.categories = res;
        }
      }
    });
  }

  loadProducts() {
    this.isLoading = true;
    this.error = '';

    const params: any = { page: this.page };
    if (this.search) params.search = this.search;
    if (this.category_id) params.category = this.category_id;
    if (this.status) params.status = this.status;

    this.adminService.getProducts(params).subscribe({
      next: (res: any) => {
        if (res && res.data) {
          if (Array.isArray(res.data)) this.products = res.data;
          else if (res.data.products && Array.isArray(res.data.products)) this.products = res.data.products;
          else if (res.data.data && Array.isArray(res.data.data)) this.products = res.data.data;

          this.pagination = res.data.pagination || res.pagination || res.meta || null;
        } else {
          this.products = [];
        }
        this.isLoading = false;
        this.cdr.detectChanges();
      },
      error: () => {
        this.error = 'Failed to load products.';
        this.isLoading = false;
        this.cdr.detectChanges();
      }
    });
  }

  changePage(newPage: number) {
    this.page = newPage;
    this.loadProducts();
  }

  deleteProduct(id: number) {
    if (confirm('Are you sure you want to delete this product?')) {
      this.adminService.deleteProduct(id).subscribe({
        next: () => {
          this.successMsg = 'Product deleted successfully.';
          this.loadProducts();
          setTimeout(() => { this.successMsg = ''; this.cdr.detectChanges(); }, 3000);
        },
        error: (err: any) => {
          this.error = err.error?.message || 'Failed to delete product.';
          this.cdr.detectChanges();
        }
      });
    }
  }
}
