import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';

export interface Alert {
  type: 'success' | 'error' | 'info' | 'warning';
  message: string;
  timeout?: number;
}

@Injectable({
  providedIn: 'root'
})
export class AlertService {
  private alertSubject = new BehaviorSubject<Alert | null>(null);
  public alert$ = this.alertSubject.asObservable();

  show(alert: Alert) {
    this.alertSubject.next(alert);
    if (alert.timeout !== 0) {
      setTimeout(() => this.clear(), alert.timeout || 3000);
    }
  }

  success(message: string, timeout?: number) {
    this.show({ type: 'success', message, timeout });
  }

  error(message: string, timeout?: number) {
    this.show({ type: 'error', message, timeout });
  }

  info(message: string, timeout?: number) {
    this.show({ type: 'info', message, timeout });
  }

  warning(message: string, timeout?: number) {
    this.show({ type: 'warning', message, timeout });
  }

  clear() {
    this.alertSubject.next(null);
  }
}
