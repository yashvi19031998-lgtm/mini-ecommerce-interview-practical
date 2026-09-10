import { Routes } from '@angular/router';
import { HomeComponent } from './features/home/home.component';
import { LoginComponent } from './features/auth/login/login.component';
import { RegisterComponent } from './features/auth/register/register.component';
import { ProductListComponent } from './features/products/product-list/product-list.component';
import { ProductDetailComponent } from './features/products/product-detail/product-detail.component';
import { CartComponent } from './features/cart/cart.component';
import { guestGuard } from './core/guards/guest.guard';
import { authGuard } from './core/guards/auth.guard';

import { adminGuard } from './core/guards/admin.guard';
import { AdminLayoutComponent } from './features/admin/admin-layout/admin-layout.component';
import { AdminDashboardComponent } from './features/admin/dashboard/admin-dashboard.component';
import { AdminUserListComponent } from './features/admin/users/admin-user-list.component';
import { AdminUserFormComponent } from './features/admin/users/admin-user-form.component';
import { AdminCategoryListComponent } from './features/admin/categories/admin-category-list.component';
import { AdminCategoryFormComponent } from './features/admin/categories/admin-category-form.component';
import { AdminProductListComponent } from './features/admin/products/admin-product-list.component';
import { AdminProductFormComponent } from './features/admin/products/admin-product-form.component';
import { AdminOrderListComponent } from './features/admin/orders/admin-order-list.component';
import { AdminOrderDetailComponent } from './features/admin/orders/admin-order-detail.component';

import { CheckoutComponent } from './features/checkout/checkout.component';
import { OrderListComponent } from './features/orders/order-list.component';
import { OrderDetailComponent } from './features/orders/order-detail.component';

export const routes: Routes = [
  { path: '', component: HomeComponent },
  { path: 'login', component: LoginComponent, canActivate: [guestGuard] },
  { path: 'register', component: RegisterComponent, canActivate: [guestGuard] },
  { path: 'products', component: ProductListComponent },
  { path: 'products/:id', component: ProductDetailComponent },
  { path: 'cart', component: CartComponent, canActivate: [authGuard] },
  { path: 'checkout', component: CheckoutComponent, canActivate: [authGuard] },
  { path: 'orders', component: OrderListComponent, canActivate: [authGuard] },
  { path: 'orders/:id', component: OrderDetailComponent, canActivate: [authGuard] },

  // Admin Routes
  {
    path: 'admin',
    component: AdminLayoutComponent,
    canActivate: [adminGuard],
    children: [
      { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
      { path: 'dashboard', component: AdminDashboardComponent },

      { path: 'users', component: AdminUserListComponent },
      { path: 'users/new', component: AdminUserFormComponent },
      { path: 'users/:id/edit', component: AdminUserFormComponent },

      { path: 'categories', component: AdminCategoryListComponent },
      { path: 'categories/new', component: AdminCategoryFormComponent },
      { path: 'categories/:id/edit', component: AdminCategoryFormComponent },

      { path: 'products', component: AdminProductListComponent },
      { path: 'products/new', component: AdminProductFormComponent },
      { path: 'products/:id/edit', component: AdminProductFormComponent },

      { path: 'orders', component: AdminOrderListComponent },
      { path: 'orders/:id', component: AdminOrderDetailComponent }
    ]
  },

  // fallback route
  { path: '**', redirectTo: '' }
];
