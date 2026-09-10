import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { AuthService } from '../../../core/services/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterModule],
  template: `
    <div class="auth-page">
      <div class="auth-card">
        
        <div *ngIf="isAdminMode" class="admin-notice">
          <strong>🔑 Admin Access Required</strong>
          <p>Please sign in with Admin credentials to access the Admin Panel.</p>
        </div>

        <div class="auth-header">
          <h2>{{ isAdminMode ? 'Admin Portal Login' : 'Welcome Back' }}</h2>
          <p>{{ isAdminMode ? 'Manage users, products, categories & orders' : 'Please enter your details to sign in.' }}</p>
        </div>
        
        <div *ngIf="error" class="alert alert-danger">{{ error }}</div>

        <!-- Quick Demo Accounts Helper -->
        <div class="demo-helpers">
          <span class="demo-title">Quick Demo Login:</span>
          <div class="demo-buttons">
            <button type="button" class="btn-demo btn-demo-admin" (click)="fillAdmin()">Admin Account</button>
            <button type="button" class="btn-demo btn-demo-customer" (click)="fillCustomer()">Customer Account</button>
            <button type="button" class="btn-demo btn-demo-customer" (click)="fillCustomer()">Customer </button>
          </div>
        </div>

        <form [formGroup]="loginForm" (ngSubmit)="onSubmit()">
          <div class="form-group">
            <label for="email">Email Address</label>
            <input 
              type="email" 
              id="email" 
              class="form-control" 
              formControlName="email" 
              placeholder="Enter your email"
              [class.is-invalid]="loginForm.get('email')?.invalid && loginForm.get('email')?.touched"
            >
            <div class="invalid-feedback" *ngIf="loginForm.get('email')?.errors?.['required'] && loginForm.get('email')?.touched">
              Email is required.
            </div>
            <div class="invalid-feedback" *ngIf="loginForm.get('email')?.errors?.['email'] && loginForm.get('email')?.touched">
              Please enter a valid email address.
            </div>
          </div>
          
          <div class="form-group">
            <label for="password">Password</label>
            <div class="password-input-wrapper">
              <input 
                [type]="showPassword ? 'text' : 'password'" 
                id="password" 
                class="form-control" 
                formControlName="password"
                placeholder="Enter your password"
                [class.is-invalid]="loginForm.get('password')?.invalid && loginForm.get('password')?.touched"
              >
              <button type="button" class="btn-toggle-password" (click)="togglePassword()">
                {{ showPassword ? 'Hide' : 'Show' }}
              </button>
            </div>
            <div class="invalid-feedback" *ngIf="loginForm.get('password')?.errors?.['required'] && loginForm.get('password')?.touched">
              Password is required.
            </div>
          </div>

          <button type="submit" class="btn btn-primary btn-block" [disabled]="loginForm.invalid || isLoading">
            <span *ngIf="isLoading" class="spinner"></span>
            {{ isLoading ? 'Signing In...' : (isAdminMode ? 'Sign In as Admin' : 'Sign In') }}
          </button>
        </form>
        
        <div class="auth-footer">
          <p>Don't have an account? <a routerLink="/register">Register here</a></p>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .auth-page { display: flex; justify-content: center; align-items: center; min-height: 80vh; background-color: #f4f7f6; padding: 20px; }
    .auth-card { background: white; width: 100%; max-width: 440px; padding: 40px; border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,0.05); }
    
    .admin-notice { background: #fff3cd; color: #664d03; border: 1px solid #ffecb5; padding: 12px 15px; border-radius: 6px; margin-bottom: 20px; text-align: center; }
    .admin-notice strong { display: block; font-size: 0.95rem; margin-bottom: 3px; }
    .admin-notice p { margin: 0; font-size: 0.85rem; }
    
    .auth-header { text-align: center; margin-bottom: 25px; }
    .auth-header h2 { margin: 0 0 10px; font-size: 1.8rem; color: #333; }
    .auth-header p { margin: 0; color: #666; font-size: 0.95rem; }
    
    .demo-helpers { background: #f8f9fa; border: 1px dashed #ccc; border-radius: 6px; padding: 10px; margin-bottom: 20px; text-align: center; }
    .demo-title { font-size: 0.8rem; color: #666; font-weight: 600; display: block; margin-bottom: 6px; }
    .demo-buttons { display: flex; gap: 8px; justify-content: center; }
    .btn-demo { padding: 5px 10px; font-size: 0.8rem; border-radius: 4px; border: 1px solid #ccc; background: white; cursor: pointer; font-weight: 500; transition: all 0.2s; }
    .btn-demo-admin { border-color: #ffc107; background: #fff8e1; color: #856404; }
    .btn-demo-admin:hover { background: #ffe082; }
    .btn-demo-customer { border-color: #0d6efd; background: #e7f1ff; color: #084298; }
    .btn-demo-customer:hover { background: #cfe2ff; }
    
    .form-group { margin-bottom: 20px; }
    .form-group label { display: block; margin-bottom: 8px; font-weight: 500; font-size: 0.9rem; color: #333; }
    .form-control { width: 100%; padding: 12px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 1rem; transition: border-color 0.2s; box-sizing: border-box; }
    .form-control:focus { outline: none; border-color: #007bff; box-shadow: 0 0 0 3px rgba(0,123,255,0.1); }
    .form-control.is-invalid { border-color: #dc3545; }
    .invalid-feedback { color: #dc3545; font-size: 0.85rem; margin-top: 5px; }
    
    .password-input-wrapper { position: relative; }
    .btn-toggle-password { position: absolute; right: 10px; top: 50%; transform: translateY(-50%); background: none; border: none; color: #666; cursor: pointer; font-size: 0.85rem; font-weight: 500; }
    .btn-toggle-password:hover { color: #333; }
    .btn-block { width: 100%; padding: 12px; font-size: 1rem; margin-top: 10px; }
    
    .auth-footer { margin-top: 25px; text-align: center; font-size: 0.9rem; color: #666; }
    .auth-footer a { color: #007bff; text-decoration: none; font-weight: 500; }
    .auth-footer a:hover { text-decoration: underline; }
    
    .spinner { display: inline-block; width: 14px; height: 14px; border: 2px solid rgba(255,255,255,0.3); border-radius: 50%; border-top-color: white; animation: spin 1s ease-in-out infinite; margin-right: 8px; vertical-align: middle; }
    @keyframes spin { to { transform: rotate(360deg); } }
    .alert { padding: 12px; border-radius: 6px; margin-bottom: 20px; font-size: 0.9rem; }
  `]
})
export class LoginComponent implements OnInit {
  private fb = inject(FormBuilder);
  private authService = inject(AuthService);
  private router = inject(Router);
  private route = inject(ActivatedRoute);

  loginForm = this.fb.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', Validators.required]
  });

  isLoading = false;
  error = '';
  showPassword = false;
  isAdminMode = false;
  returnUrl = '';

  ngOnInit() {
    const qp = this.route.snapshot.queryParams;
    if (qp['admin'] === '1' || (qp['returnUrl'] && qp['returnUrl'].includes('/admin'))) {
      this.isAdminMode = true;
    }
    if (qp['returnUrl']) {
      this.returnUrl = qp['returnUrl'];
    }
  }

  fillAdmin() {
    this.loginForm.patchValue({
      email: 'admin@example.com',
      password: 'password123'
    });
  }

  fillCustomer() {
    this.loginForm.patchValue({
      email: 'customer1@example.com',
      password: 'password123'
    });
  }

  togglePassword() {
    this.showPassword = !this.showPassword;
  }

  onSubmit() {
    if (this.loginForm.invalid) {
      this.loginForm.markAllAsTouched();
      return;
    }

    this.isLoading = true;
    this.error = '';

    this.authService.login(this.loginForm.value as any).subscribe({
      next: (res: any) => {
        if (res && (res.success || (res.data && res.data.token))) {
          if (this.returnUrl) {
            this.router.navigateByUrl(this.returnUrl);
          } else if (this.authService.isAdmin()) {
            this.router.navigate(['/admin/dashboard']);
          } else {
            this.router.navigate(['/']);
          }
        } else {
          this.error = res?.message || 'Login failed';
          this.isLoading = false;
        }
      },
      error: (err) => {
        this.error = err.error?.message || 'An error occurred during login.';
        this.isLoading = false;
      }
    });
  }
}

