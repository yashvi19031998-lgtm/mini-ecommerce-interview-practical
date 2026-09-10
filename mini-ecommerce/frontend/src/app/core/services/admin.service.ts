import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { User } from '../models/user.model';
import { Product, Category, PaginatedResponse } from '../models/catalog.model';
import { Order } from '../models/order.model';

@Injectable({
  providedIn: 'root'
})
export class AdminService {
  private http = inject(HttpClient);
  private apiUrl = `${environment.apiUrl}/admin`;

  // Dashboard
  getDashboard(): Observable<{success: boolean, data: any}> {
    return this.http.get<{success: boolean, data: any}>(`${this.apiUrl}/dashboard`);
  }

  // Users
  getUsers(params?: any): Observable<PaginatedResponse<User, 'users'>> {
    let httpParams = new HttpParams();
    if (params) {
      Object.keys(params).forEach(key => {
        if (params[key] !== null && params[key] !== undefined) {
          httpParams = httpParams.set(key, params[key]);
        }
      });
    }
    return this.http.get<PaginatedResponse<User, 'users'>>(`${this.apiUrl}/users`, { params: httpParams });
  }

  getUser(id: number): Observable<{success: boolean, data: User}> {
    return this.http.get<{success: boolean, data: User}>(`${this.apiUrl}/users/${id}`);
  }

  createUser(user: any): Observable<any> {
    return this.http.post(`${this.apiUrl}/users`, user);
  }

  updateUser(id: number, user: any): Observable<any> {
    return this.http.put(`${this.apiUrl}/users/${id}`, user);
  }

  deleteUser(id: number): Observable<any> {
    return this.http.delete(`${this.apiUrl}/users/${id}`);
  }

  // Orders
  getOrders(params?: any): Observable<PaginatedResponse<Order, 'orders'>> {
    let httpParams = new HttpParams();
    if (params) {
      Object.keys(params).forEach(key => {
        if (params[key] !== null && params[key] !== undefined) {
          httpParams = httpParams.set(key, params[key]);
        }
      });
    }
    return this.http.get<PaginatedResponse<Order, 'orders'>>(`${this.apiUrl}/orders`, { params: httpParams });
  }

  getOrder(id: number): Observable<{success: boolean, data: Order}> {
    return this.http.get<{success: boolean, data: Order}>(`${this.apiUrl}/orders/${id}`);
  }

  updateOrderStatus(id: number, status: string): Observable<any> {
    return this.http.patch(`${this.apiUrl}/orders/${id}/status`, { status });
  }

  // Categories CRUD
  getCategories(): Observable<{success: boolean, data: Category[]}> {
    return this.http.get<{success: boolean, data: Category[]}>(`${this.apiUrl}/categories`);
  }

  getCategory(id: number): Observable<{success: boolean, data: Category}> {
    return this.http.get<{success: boolean, data: Category}>(`${this.apiUrl}/categories/${id}`);
  }

  createCategory(category: any): Observable<any> {
    return this.http.post(`${this.apiUrl}/categories`, category);
  }

  updateCategory(id: number, category: any): Observable<any> {
    return this.http.put(`${this.apiUrl}/categories/${id}`, category);
  }

  deleteCategory(id: number): Observable<any> {
    return this.http.delete(`${this.apiUrl}/categories/${id}`);
  }

  // Products CRUD
  getProducts(params?: any): Observable<PaginatedResponse<Product, 'products'>> {
    let httpParams = new HttpParams();
    if (params) {
      Object.keys(params).forEach(key => {
        if (params[key] !== null && params[key] !== undefined) {
          httpParams = httpParams.set(key, params[key]);
        }
      });
    }
    return this.http.get<PaginatedResponse<Product, 'products'>>(`${this.apiUrl}/products`, { params: httpParams });
  }

  getProduct(id: number): Observable<{success: boolean, data: Product}> {
    return this.http.get<{success: boolean, data: Product}>(`${this.apiUrl}/products/${id}`);
  }

  createProduct(data: FormData | any): Observable<any> {
    return this.http.post(`${this.apiUrl}/products`, data);
  }

  updateProduct(id: number, data: FormData | any): Observable<any> {
    // For FormData, we often use POST with _method=PUT in Laravel
    return this.http.post(`${this.apiUrl}/products/${id}`, data);
  }

  deleteProduct(id: number): Observable<any> {
    return this.http.delete(`${this.apiUrl}/products/${id}`);
  }
}
