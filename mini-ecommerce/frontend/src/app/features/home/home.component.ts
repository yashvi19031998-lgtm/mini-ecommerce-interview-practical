import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [CommonModule, RouterModule],
  template: `
    <div class="home-container">
      <header class="hero">
        <h1>Welcome to Mini E-Commerce</h1>
        <p>Your one-stop shop for everything you need.</p>
        <a routerLink="/products" class="btn btn-primary">Browse Products</a>
      </header>
    </div>
  `,
  styles: [`
    .home-container {
      display: flex;
      justify-content: center;
      align-items: center;
      height: 80vh;
      text-align: center;
    }
    .hero h1 {
      font-size: 3rem;
      margin-bottom: 1rem;
      color: #333;
    }
    .hero p {
      font-size: 1.2rem;
      color: #666;
      margin-bottom: 2rem;
    }
    .btn {
      padding: 10px 20px;
      text-decoration: none;
      border-radius: 5px;
      font-weight: bold;
    }
    .btn-primary {
      background-color: #007bff;
      color: white;
    }
    .btn-primary:hover {
      background-color: #0056b3;
    }
  `]
})
export class HomeComponent {}
