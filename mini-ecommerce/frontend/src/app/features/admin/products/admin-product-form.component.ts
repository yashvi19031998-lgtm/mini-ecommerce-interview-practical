import { Component, OnInit, inject, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { AdminService } from '../../../core/services/admin.service';

@Component({
  selector: 'app-admin-product-form',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterModule],
  template: `
    <div class="admin-page">
      <div class="page-header">
        <h2>{{ isEditMode ? 'Edit Product' : 'Add New Product' }}</h2>
        <a routerLink="/admin/products" class="btn btn-secondary">Back to List</a>
      </div>

      <div *ngIf="error" class="alert alert-danger">{{ error }}</div>
      <div *ngIf="isLoading" class="loader">Loading...</div>

      <div class="form-card" *ngIf="!isLoading">
        <form [formGroup]="productForm" (ngSubmit)="onSubmit()">
          
          <div class="form-row">
            <div class="form-group flex-2">
              <label for="name">Product Name <span class="required">*</span></label>
              <input type="text" id="name" formControlName="name" class="form-control" [class.is-invalid]="isInvalid('name')">
              <div class="invalid-feedback" *ngIf="isInvalid('name')">Name is required.</div>
              <small *ngIf="validationErrors?.name" class="text-danger">{{ validationErrors.name[0] }}</small>
            </div>

            <div class="form-group flex-1">
              <label for="category_id">Category <span class="required">*</span></label>
              <select id="category_id" formControlName="category_id" class="form-control" [class.is-invalid]="isInvalid('category_id')">
                <option value="" disabled>Select Category</option>
                <option *ngFor="let cat of categories" [value]="cat.id">{{ cat.name }}</option>
              </select>
              <div class="invalid-feedback" *ngIf="isInvalid('category_id')">Category is required.</div>
              <small *ngIf="validationErrors?.category_id" class="text-danger">{{ validationErrors.category_id[0] }}</small>
            </div>
          </div>

          <div class="form-group">
            <label for="description">Description</label>
            <textarea id="description" formControlName="description" class="form-control" rows="4"></textarea>
            <small *ngIf="validationErrors?.description" class="text-danger">{{ validationErrors.description[0] }}</small>
          </div>

          <div class="form-row">
            <div class="form-group flex-1">
              <label for="price">Price <span class="required">*</span></label>
              <input type="number" id="price" formControlName="price" class="form-control" step="0.01" min="0" [class.is-invalid]="isInvalid('price')">
              <div class="invalid-feedback" *ngIf="isInvalid('price')">Valid positive price is required.</div>
              <small *ngIf="validationErrors?.price" class="text-danger">{{ validationErrors.price[0] }}</small>
            </div>

            <div class="form-group flex-1">
              <label for="stock">Stock Quantity <span class="required">*</span></label>
              <input type="number" id="stock" formControlName="stock" class="form-control" min="0" [class.is-invalid]="isInvalid('stock')">
              <div class="invalid-feedback" *ngIf="isInvalid('stock')">Valid positive stock is required.</div>
              <small *ngIf="validationErrors?.stock" class="text-danger">{{ validationErrors.stock[0] }}</small>
            </div>
            
            <div class="form-group flex-1">
              <label for="status">Status <span class="required">*</span></label>
              <select id="status" formControlName="status" class="form-control" [class.is-invalid]="isInvalid('status')">
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </select>
              <div class="invalid-feedback" *ngIf="isInvalid('status')">Status is required.</div>
            </div>
          </div>

          <!-- Note: The Laravel implementation might support file upload for images or just URL string. 
               We will use a URL string input for simplicity matching the seeder, unless file upload is strictly required. -->
          <div class="form-group">
            <label for="image">Image URL</label>
            <input type="text" id="image" formControlName="image" class="form-control" placeholder="https://...">
            <small *ngIf="validationErrors?.image" class="text-danger">{{ validationErrors.image[0] }}</small>
          </div>

          <div class="form-actions">
            <button type="submit" class="btn btn-primary" [disabled]="isSaving">
              {{ isSaving ? 'Saving...' : 'Save Product' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  `,
  styles: [`
    .page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
    h2 { margin: 0; color: #333; }
    
    .form-card { background: white; padding: 25px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .form-group { margin-bottom: 20px; }
    .form-row { display: flex; gap: 20px; }
    .flex-1 { flex: 1; }
    .flex-2 { flex: 2; }
    
    label { display: block; margin-bottom: 8px; font-weight: 500; color: #333; }
    .required { color: #dc3545; }
    .form-control { width: 100%; padding: 10px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; font-family: inherit; }
    .form-control:focus { outline: none; border-color: #007bff; }
    .form-control.is-invalid { border-color: #dc3545; }
    .invalid-feedback { color: #dc3545; font-size: 0.85rem; margin-top: 5px; }
    .text-danger { color: #dc3545; font-size: 0.85rem; display: block; margin-top: 5px; }
    
    .form-actions { margin-top: 30px; display: flex; justify-content: flex-end; }
    .btn { padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; font-size: 1rem; text-decoration: none; }
    .btn-primary { background-color: #007bff; color: white; }
    .btn-primary:disabled { background-color: #a0cbf7; cursor: not-allowed; }
    .btn-secondary { background-color: #6c757d; color: white; }
    
    .loader { text-align: center; padding: 40px; color: #666; }
    .alert { padding: 15px; border-radius: 4px; margin-bottom: 15px; }
    .alert-danger { background: #f8d7da; color: #721c24; border: 1px solid #f5c2c7; }
  `]
})
export class AdminProductFormComponent implements OnInit {
  private fb = inject(FormBuilder);
  private adminService = inject(AdminService);
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private cdr = inject(ChangeDetectorRef);

  productId: number | null = null;
  isEditMode = false;
  isLoading = true;
  isSaving = false;
  error = '';
  validationErrors: any = null;
  categories: any[] = [];

  productForm = this.fb.group({
    name: ['', Validators.required],
    category_id: ['', Validators.required],
    description: [''],
    price: [0, [Validators.required, Validators.min(0)]],
    stock: [0, [Validators.required, Validators.min(0)]],
    status: ['active', Validators.required],
    image: ['']
  });

  ngOnInit() {
    this.loadCategories();

    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      this.isEditMode = true;
      this.productId = +id;
      this.loadProduct(this.productId);
    } else {
      this.isLoading = false;
    }
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
        this.cdr.detectChanges();
      }
    });
  }

  loadProduct(id: number) {
    this.adminService.getProduct(id).subscribe({
      next: (res: any) => {
        let prodData = res.data || res;
        this.productForm.patchValue({
          name: prodData.name,
          category_id: prodData.category_id,
          description: prodData.description || '',
          price: prodData.price,
          stock: prodData.stock,
          status: prodData.status,
          image: prodData.image || ''
        });
        this.isLoading = false;
        this.cdr.detectChanges();
      },
      error: () => {
        this.error = 'Failed to load product data.';
        this.isLoading = false;
        this.cdr.detectChanges();
      }
    });
  }

  isInvalid(field: string): boolean {
    const control = this.productForm.get(field);
    return !!(control && control.invalid && (control.dirty || control.touched));
  }

  onSubmit() {
    if (this.productForm.invalid) {
      this.productForm.markAllAsTouched();
      return;
    }

    this.isSaving = true;
    this.error = '';
    this.validationErrors = null;
    this.cdr.detectChanges();

    const formData = this.productForm.value;

    const request$ = this.isEditMode
      ? this.adminService.updateProduct(this.productId!, formData)
      : this.adminService.createProduct(formData);

    request$.subscribe({
      next: () => {
        this.router.navigate(['/admin/products']);
      },
      error: (err: any) => {
        this.isSaving = false;
        if (err.status === 422) {
          this.validationErrors = err.error.errors;
        } else {
          this.error = err.error?.message || 'Failed to save product.';
        }
        this.cdr.detectChanges();
      }
    });
  }
}
