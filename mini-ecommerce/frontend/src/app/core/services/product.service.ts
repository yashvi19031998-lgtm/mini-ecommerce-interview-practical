import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { Product, ProductPaginatedResponse } from '../models/catalog.model';

@Injectable({
  providedIn: 'root'
})
export class ProductService {
  private http = inject(HttpClient);
  private apiUrl = `${environment.apiUrl}/products`;

  getProducts(params?: any): Observable<ProductPaginatedResponse> {
    let httpParams = new HttpParams();
    if (params) {
      Object.keys(params).forEach(key => {
        if (params[key] !== null && params[key] !== undefined && params[key] !== '') {
          httpParams = httpParams.set(key, params[key]);
        }
      });
    }
    return this.http.get<ProductPaginatedResponse>(this.apiUrl, { params: httpParams });
  }

  getProduct(id: number): Observable<{success: boolean, data: Product}> {
    return this.http.get<{success: boolean, data: Product}>(`${this.apiUrl}/${id}`);
  }
}
