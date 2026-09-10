import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { BehaviorSubject, Observable, tap } from 'rxjs';
import { environment } from '../../../environments/environment';
import { CartResponse } from '../models/cart.model';

@Injectable({
  providedIn: 'root'
})
export class CartService {
  private http = inject(HttpClient);
  private apiUrl = `${environment.apiUrl}/cart`;

  private cartItemCountSubject = new BehaviorSubject<number>(0);
  public cartItemCount$ = this.cartItemCountSubject.asObservable();

  getCart(): Observable<CartResponse> {
    return this.http.get<CartResponse>(this.apiUrl).pipe(
      tap(res => {
        if (res.success && res.data) {
          const count = res.data.items.reduce((acc, item) => acc + item.quantity, 0);
          this.cartItemCountSubject.next(count);
        }
      })
    );
  }

  addToCart(productId: number, quantity: number = 1): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}/items`, { product_id: productId, quantity }).pipe(
      tap(() => this.updateCartCount())
    );
  }

  updateItem(itemId: number, quantity: number): Observable<any> {
    return this.http.patch<any>(`${this.apiUrl}/items/${itemId}`, { quantity }).pipe(
      tap(() => this.updateCartCount())
    );
  }

  removeItem(itemId: number): Observable<any> {
    return this.http.delete<any>(`${this.apiUrl}/items/${itemId}`).pipe(
      tap(() => this.updateCartCount())
    );
  }

  clearCart(): Observable<any> {
    return this.http.delete<any>(this.apiUrl).pipe(
      tap(() => this.cartItemCountSubject.next(0))
    );
  }

  updateCartCount(): void {
    this.getCart().subscribe();
  }
}
