import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { Category } from '../models/catalog.model';

@Injectable({
  providedIn: 'root'
})
export class CategoryService {
  private http = inject(HttpClient);
  private apiUrl = `${environment.apiUrl}/categories`;

  getCategories(): Observable<{success: boolean, data: Category[]}> {
    return this.http.get<{success: boolean, data: Category[]}>(this.apiUrl);
  }

  getCategory(id: number): Observable<{success: boolean, data: Category}> {
    return this.http.get<{success: boolean, data: Category}>(`${this.apiUrl}/${id}`);
  }
}
