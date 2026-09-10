import { Component, OnInit, inject, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { AdminService } from '../../../core/services/admin.service';

@Component({
  selector: 'app-admin-user-form',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterModule],
  template: `
    <div class="admin-page">
      <div class="page-header">
        <h2>{{ isEditMode ? 'Edit User' : 'Add New User' }}</h2>
        <a routerLink="/admin/users" class="btn btn-secondary">Back to List</a>
      </div>

      <div *ngIf="error" class="alert alert-danger">{{ error }}</div>
      <div *ngIf="isLoading" class="loader">Loading...</div>

      <div class="form-card" *ngIf="!isLoading">
        <form [formGroup]="userForm" (ngSubmit)="onSubmit()">
          
          <div class="form-group">
            <label for="name">Full Name <span class="required">*</span></label>
            <input type="text" id="name" formControlName="name" class="form-control" [class.is-invalid]="isInvalid('name')">
            <div class="invalid-feedback" *ngIf="isInvalid('name')">Name is required.</div>
          </div>

          <div class="form-group">
            <label for="email">Email Address <span class="required">*</span></label>
            <input type="email" id="email" formControlName="email" class="form-control" [class.is-invalid]="isInvalid('email')">
            <div class="invalid-feedback" *ngIf="isInvalid('email')">A valid email is required.</div>
            <small *ngIf="validationErrors?.email" class="text-danger">{{ validationErrors.email[0] }}</small>
          </div>

          <div class="form-group" *ngIf="!isEditMode">
            <label for="password">Password <span class="required">*</span></label>
            <input type="password" id="password" formControlName="password" class="form-control" [class.is-invalid]="isInvalid('password')">
            <div class="invalid-feedback" *ngIf="isInvalid('password')">Password is required (min 6 chars).</div>
            <small *ngIf="validationErrors?.password" class="text-danger">{{ validationErrors.password[0] }}</small>
          </div>

          <div class="form-group" *ngIf="isEditMode">
            <label for="password">Password (Leave blank to keep current)</label>
            <input type="password" id="password" formControlName="password" class="form-control">
          </div>

          <div class="form-row">
            <div class="form-group flex-1">
              <label for="role">Role <span class="required">*</span></label>
              <select id="role" formControlName="role" class="form-control" [class.is-invalid]="isInvalid('role')">
                <option value="customer">Customer</option>
                <option value="admin">Admin</option>
              </select>
            </div>

            <div class="form-group flex-1">
              <label for="status">Status <span class="required">*</span></label>
              <select id="status" formControlName="status" class="form-control" [class.is-invalid]="isInvalid('status')">
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </select>
            </div>
          </div>

          <div class="form-actions">
            <button type="submit" class="btn btn-primary" [disabled]="isSaving">
              {{ isSaving ? 'Saving...' : 'Save User' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  `,
  styles: [`
    .page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
    h2 { margin: 0; color: #333; }
    
    .form-card { background: white; padding: 25px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); max-width: 600px; }
    .form-group { margin-bottom: 20px; }
    .form-row { display: flex; gap: 20px; }
    .flex-1 { flex: 1; }
    
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
export class AdminUserFormComponent implements OnInit {
  private fb = inject(FormBuilder);
  private adminService = inject(AdminService);
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private cdr = inject(ChangeDetectorRef);

  userId: number | null = null;
  isEditMode = false;
  isLoading = false;
  isSaving = false;
  error = '';
  validationErrors: any = null;

  userForm = this.fb.group({
    name: ['', Validators.required],
    email: ['', [Validators.required, Validators.email]],
    password: [''],
    role: ['customer', Validators.required],
    status: ['active', Validators.required]
  });

  ngOnInit() {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      this.isEditMode = true;
      this.userId = +id;
      this.loadUser(this.userId);
    } else {
      // Set password as required for new users
      this.userForm.get('password')?.setValidators([Validators.required, Validators.minLength(6)]);
      this.userForm.get('password')?.updateValueAndValidity();
    }
  }

  loadUser(id: number) {
    this.isLoading = true;
    this.adminService.getUser(id).subscribe({
      next: (res: any) => {
        let userData = res.data || res;
        this.userForm.patchValue({
          name: userData.name,
          email: userData.email,
          role: userData.role,
          status: userData.status
        });
        this.isLoading = false;
        this.cdr.detectChanges();
      },
      error: () => {
        this.error = 'Failed to load user data.';
        this.isLoading = false;
        this.cdr.detectChanges();
      }
    });
  }

  isInvalid(field: string): boolean {
    const control = this.userForm.get(field);
    return !!(control && control.invalid && (control.dirty || control.touched));
  }

  onSubmit() {
    if (this.userForm.invalid) {
      this.userForm.markAllAsTouched();
      return;
    }

    this.isSaving = true;
    this.error = '';
    this.validationErrors = null;
    this.cdr.detectChanges();

    const formData = { ...this.userForm.value };
    if (this.isEditMode && !formData.password) {
      delete formData.password; // Don't send empty password on edit
    }

    const request$ = this.isEditMode
      ? this.adminService.updateUser(this.userId!, formData)
      : this.adminService.createUser(formData);

    request$.subscribe({
      next: () => {
        this.router.navigate(['/admin/users']);
      },
      error: (err: any) => {
        this.isSaving = false;
        if (err.status === 422) {
          this.validationErrors = err.error.errors;
        } else {
          this.error = err.error?.message || 'Failed to save user.';
        }
        this.cdr.detectChanges();
      }
    });
  }
}
