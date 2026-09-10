import { Component, OnInit, inject, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { AdminService } from '../../../core/services/admin.service';

@Component({
  selector: 'app-admin-category-list',
  standalone: true,
  imports: [CommonModule, RouterModule],
  template: `
    <div class="admin-page">
      <div class="page-header">
        <h2>Manage Categories</h2>
        <a routerLink="/admin/categories/new" class="btn btn-primary">Add New Category</a>
      </div>

      <div *ngIf="error" class="alert alert-danger">{{ error }}</div>
      <div *ngIf="successMsg" class="alert alert-success">{{ successMsg }}</div>

      <div class="table-responsive" *ngIf="!isLoading && categories.length > 0">
        <table class="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Name</th>
              <th>Slug</th>
              <th>Status</th>
              <th>Products</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr *ngFor="let cat of categories">
              <td>{{ cat.id }}</td>
              <td><strong>{{ cat.name }}</strong></td>
              <td>{{ cat.slug }}</td>
              <td><span class="badge" [ngClass]="cat.status === 'active' ? 'badge-success' : 'badge-danger'">{{ cat.status }}</span></td>
              <td>{{ cat.products_count !== undefined ? cat.products_count : '-' }}</td>
              <td class="actions">
                <a [routerLink]="['/admin/categories', cat.id, 'edit']" class="btn btn-sm btn-info">Edit</a>
                <button class="btn btn-sm btn-danger" (click)="deleteCategory(cat.id)">Delete</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div *ngIf="isLoading" class="loader">Loading categories...</div>
      
      <div *ngIf="!isLoading && categories.length === 0" class="empty-state">
        No categories found.
      </div>
    </div>
  `,
  styles: [`
    .page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
    h2 { margin: 0; color: #333; }
    
    .table-responsive { background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); overflow-x: auto; }
    .table { width: 100%; border-collapse: collapse; }
    .table th, .table td { padding: 12px 15px; text-align: left; border-bottom: 1px solid #eee; }
    .table th { background-color: #f8f9fa; font-weight: 600; color: #555; }
    
    .badge { padding: 5px 10px; border-radius: 20px; font-size: 0.8rem; font-weight: 500; }
    .badge-success { background-color: #d4edda; color: #155724; }
    .badge-danger { background-color: #f8d7da; color: #721c24; }
    
    .actions { display: flex; gap: 8px; }
    .btn-sm { padding: 5px 10px; font-size: 0.85rem; }
    .btn-info { background-color: #17a2b8; color: white; border: none; border-radius: 4px; text-decoration: none; cursor: pointer; }
    .btn-danger { background-color: #dc3545; color: white; border: none; border-radius: 4px; cursor: pointer; }
    .btn-primary { background-color: #007bff; color: white; text-decoration: none; padding: 10px 20px; border-radius: 4px; }
    
    .loader { text-align: center; padding: 40px; color: #666; }
    .empty-state { text-align: center; padding: 40px; background: white; border-radius: 8px; color: #666; }
    .alert { padding: 15px; border-radius: 4px; margin-bottom: 15px; }
    .alert-danger { background: #f8d7da; color: #721c24; border: 1px solid #f5c2c7; }
    .alert-success { background: #d1e7dd; color: #0f5132; border: 1px solid #badbcc; }
  `]
})
export class AdminCategoryListComponent implements OnInit {
  private adminService = inject(AdminService);
  private cdr = inject(ChangeDetectorRef);

  categories: any[] = [];
  isLoading = true;
  error = '';
  successMsg = '';

  ngOnInit() {
    this.loadCategories();
  }

  loadCategories() {
    this.isLoading = true;
    this.error = '';
    this.adminService.getCategories().subscribe({
      next: (res: any) => {
        if (res && res.data) {
          if (Array.isArray(res.data)) this.categories = res.data;
          else if (Array.isArray(res.data.categories)) this.categories = res.data.categories;
        } else if (Array.isArray(res)) {
          this.categories = res;
        } else {
          this.categories = [];
        }
        this.isLoading = false;
        this.cdr.detectChanges();
      },
      error: () => {
        this.error = 'Failed to load categories.';
        this.isLoading = false;
        this.cdr.detectChanges();
      }
    });
  }

  deleteCategory(id: number) {
    if (confirm('Are you sure you want to delete this category? Products might be affected.')) {
      this.adminService.deleteCategory(id).subscribe({
        next: () => {
          this.successMsg = 'Category deleted successfully.';
          this.loadCategories();
          setTimeout(() => { this.successMsg = ''; this.cdr.detectChanges(); }, 3000);
        },
        error: (err: any) => {
          this.error = err.error?.message || 'Failed to delete category.';
          this.cdr.detectChanges();
        }
      });
    }
  }
}
