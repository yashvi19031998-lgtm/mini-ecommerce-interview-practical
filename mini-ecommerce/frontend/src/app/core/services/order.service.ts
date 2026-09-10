import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { Order } from '../models/order.model';
import { PaginatedResponse } from '../models/catalog.model';

@Injectable({
  providedIn: 'root'
})
export class OrderService {
  private http = inject(HttpClient);
  private apiUrl = `${environment.apiUrl}/orders`;

  createOrder(data: any): Observable<{success: boolean, message: string, data: Order}> {
    return this.http.post<{success: boolean, message: string, data: Order}>(this.apiUrl, data);
  }

  getOrders(page: number = 1): Observable<any> {
    return this.http.get<any>(`${this.apiUrl}?page=${page}`);
  }

  getOrder(id: number): Observable<{success: boolean, data: Order}> {
    return this.http.get<{success: boolean, data: Order}>(`${this.apiUrl}/${id}`);
  }
}
