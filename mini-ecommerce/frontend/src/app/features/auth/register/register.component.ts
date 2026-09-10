import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { Router, RouterModule } from '@angular/router';
import { AuthService } from '../../../core/services/auth.service';

@Component({
  selector: 'app-register',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterModule],
  template: `
    <div class="auth-page">
      <div class="auth-card">
        <div class="auth-header">
          <h2>Create Account</h2>
          <p>Sign up to start shopping today.</p>
        </div>
        
        <div *ngIf="error" class="alert alert-danger">{{ error }}</div>

        <form [formGroup]="registerForm" (ngSubmit)="onSubmit()">
          <div class="form-group">
            <label for="name">Full Name</label>
            <input 
              type="text" 
              id="name" 
              class="form-control" 
              formControlName="name" 
              placeholder="Enter your full name"
              [class.is-invalid]="registerForm.get('name')?.invalid && registerForm.get('name')?.touched"
            >
            <div class="invalid-feedback" *ngIf="registerForm.get('name')?.errors?.['required'] && registerForm.get('name')?.touched">
              Full name is required.
            </div>
            <small *ngIf="validationErrors?.name" class="text-danger">{{ validationErrors.name[0] }}</small>
          </div>

          <div class="form-group">
            <label for="email">Email Address</label>
            <input 
              type="email" 
              id="email" 
              class="form-control" 
              formControlName="email" 
              placeholder="Enter your email address"
              [class.is-invalid]="registerForm.get('email')?.invalid && registerForm.get('email')?.touched"
            >
            <div class="invalid-feedback" *ngIf="registerForm.get('email')?.errors?.['required'] && registerForm.get('email')?.touched">
              Email is required.
            </div>
            <div class="invalid-feedback" *ngIf="registerForm.get('email')?.errors?.['email'] && registerForm.get('email')?.touched">
              Please enter a valid email address.
            </div>
            <small *ngIf="validationErrors?.email" class="text-danger">{{ validationErrors.email[0] }}</small>
          </div>
          
          <div class="form-group">
            <label for="password">Password</label>
            <div class="password-input-wrapper">
              <input 
                [type]="showPassword ? 'text' : 'password'" 
                id="password" 
                class="form-control" 
                formControlName="password"
                placeholder="Create a password (min 6 characters)"
                [class.is-invalid]="registerForm.get('password')?.invalid && registerForm.get('password')?.touched"
              >
              <button type="button" class="btn-toggle-password" (click)="togglePassword()">
                {{ showPassword ? 'Hide' : 'Show' }}
              </button>
            </div>
            <div class="invalid-feedback" *ngIf="registerForm.get('password')?.errors?.['required'] && registerForm.get('password')?.touched">
              Password is required.
            </div>
            <div class="invalid-feedback" *ngIf="registerForm.get('password')?.errors?.['minlength'] && registerForm.get('password')?.touched">
              Password must be at least 6 characters long.
            </div>
            <small *ngIf="validationErrors?.password" class="text-danger">{{ validationErrors.password[0] }}</small>
          </div>

          <div class="form-group">
            <label for="password_confirmation">Confirm Password</label>
            <input 
              [type]="showPassword ? 'text' : 'password'" 
              id="password_confirmation" 
              class="form-control" 
              formControlName="password_confirmation"
              placeholder="Re-enter your password"
              [class.is-invalid]="registerForm.get('password_confirmation')?.invalid && registerForm.get('password_confirmation')?.touched"
            >
            <div class="invalid-feedback" *ngIf="registerForm.get('password_confirmation')?.errors?.['required'] && registerForm.get('password_confirmation')?.touched">
              Please confirm your password.
            </div>
          </div>

          <button type="submit" class="btn btn-primary btn-block" [disabled]="registerForm.invalid || isLoading">
            <span *ngIf="isLoading" class="spinner"></span>
            {{ isLoading ? 'Creating Account...' : 'Register' }}
          </button>
        </form>
        
        <div class="auth-footer">
          <p>Already have an account? <a routerLink="/login">Sign in here</a></p>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .auth-page { display: flex; justify-content: center; align-items: center; min-height: 80vh; background-color: #f4f7f6; padding: 20px; }
    .auth-card { background: white; width: 100%; max-width: 440px; padding: 40px; border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,0.05); }
    .auth-header { text-align: center; margin-bottom: 30px; }
    .auth-header h2 { margin: 0 0 10px; font-size: 1.8rem; color: #333; }
    .auth-header p { margin: 0; color: #666; font-size: 0.95rem; }
    .form-group { margin-bottom: 20px; }
    .form-group label { display: block; margin-bottom: 8px; font-weight: 500; font-size: 0.9rem; color: #333; }
    .form-control { width: 100%; padding: 12px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 1rem; transition: border-color 0.2s; box-sizing: border-box; }
    .form-control:focus { outline: none; border-color: #007bff; box-shadow: 0 0 0 3px rgba(0,123,255,0.1); }
    .form-control.is-invalid { border-color: #dc3545; }
    .invalid-feedback { color: #dc3545; font-size: 0.85rem; margin-top: 5px; }
    .text-danger { color: #dc3545; font-size: 0.85rem; display: block; margin-top: 5px; }
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
    .alert-danger { background-color: #f8d7da; color: #721c24; border: 1px solid #f5c2c7; }
  `]
})
export class RegisterComponent {
  private fb = inject(FormBuilder);
  private authService = inject(AuthService);
  private router = inject(Router);

  registerForm = this.fb.group({
    name: ['', Validators.required],
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required, Validators.minLength(6)]],
    password_confirmation: ['', Validators.required]
  });

  isLoading = false;
  showPassword = false;
  error = '';
  validationErrors: any = null;

  togglePassword() {
    this.showPassword = !this.showPassword;
  }

  onSubmit() {
    if (this.registerForm.invalid) {
      this.registerForm.markAllAsTouched();
      return;
    }

    if (this.registerForm.value.password !== this.registerForm.value.password_confirmation) {
      this.error = 'Passwords do not match.';
      return;
    }

    this.isLoading = true;
    this.error = '';
    this.validationErrors = null;

    this.authService.register(this.registerForm.value as any).subscribe({
      next: (res: any) => {
        if (res && res.success) {
          this.router.navigate(['/']);
        } else {
          this.error = res?.message || 'Registration failed';
          this.isLoading = false;
        }
      },
      error: (err: any) => {
        this.isLoading = false;
        if (err.status === 422) {
          this.validationErrors = err.error.errors;
        } else {
          this.error = err.error?.message || 'An error occurred during registration.';
        }
      }
    });
  }
}

