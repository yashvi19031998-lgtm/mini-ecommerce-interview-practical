# Mini E-Commerce Management System — Backend API

RESTful API backend for the Mini E-Commerce Management System built with **Laravel 10**, **PHP 8.1**, **MySQL**, and **Laravel Sanctum**.

---

## Technology Stack

* **Framework**: Laravel 10.50.3
* **Language**: PHP 8.1.34
* **Database**: MySQL (`mini_ecommerce`)
* **Authentication**: Laravel Sanctum (Token-based)
* **Architecture**: Service-oriented with Form Requests, API Resources, and Policies

---

## Seeded Demo Credentials

| Role | Name | Email | Password | Status |
|---|---|---|---|---|
| **Admin** | System Administrator | `admin@example.com` | `password123` | Active |
| **Customer** | John Doe | `customer1@example.com` | `password123` | Active |
| **Customer** | Jane Smith | `customer2@example.com` | `password123` | Active |
| **Customer** | Alex Johnson | `customer3@example.com` | `password123` | Active |
| **Customer** | Emily Davis | `customer4@example.com` | `password123` | Active |
| **Customer** | Michael Brown | `customer5@example.com` | `password123` | Active |
| **Customer** | Inactive User | `inactive@example.com` | `password123` | Inactive |

---

## Database Schema & Tables

1. **`users`**: `id`, `name`, `email`, `password`, `role` (admin, customer), `status` (active, inactive), `timestamps`
2. **`categories`**: `id`, `name`, `slug` (unique), `description`, `status` (active, inactive), `timestamps`
3. **`products`**: `id`, `category_id` (FK categories), `name`, `slug` (unique), `description`, `price` (decimal 10,2), `stock` (unsigned int), `image`, `status`, `timestamps`
4. **`carts`**: `id`, `user_id` (FK users, unique), `timestamps`
5. **`cart_items`**: `id`, `cart_id` (FK carts), `product_id` (FK products), `quantity`, `timestamps`, unique(`cart_id`, `product_id`)
6. **`orders`**: `id`, `user_id` (FK users), `order_number` (unique), `subtotal`, `total`, `status` (pending, confirmed, processing, shipped, delivered, cancelled), `timestamps`
7. **`order_items`**: `id`, `order_id` (FK orders), `product_id` (FK products, nullable), `product_name` (snapshot), `quantity`, `price` (snapshot), `subtotal`, `timestamps`
8. **`personal_access_tokens`**: Sanctum API tokens table

---

## API Response Format

### Success Response (`HTTP 200 / 201`)
```json
{
  "success": true,
  "message": "Operation description",
  "data": {}
}
```

### Error Response (`HTTP 400 / 401 / 403 / 404 / 422 / 500`)
```json
{
  "success": false,
  "message": "Error description message",
  "errors": {}
}
```

---

## API Endpoints Reference

### 1. Public Authentication
* `POST /api/register` — Register a new customer (`name`, `email`, `password`, `password_confirmation`).
* `POST /api/login` — Log in and receive Sanctum bearer token (`email`, `password`).

### 2. Public Catalog Browsing
* `GET /api/categories` — Browse active categories with product counts.
* `GET /api/categories/{id}` — View single active category.
* `GET /api/products` — Browse active products with search (`?search=`), category filter (`?category_id=`), sort (`?sort=price_asc|price_desc`), and pagination (`?per_page=`).
* `GET /api/products/{id}` — View single product details.

### 3. Authenticated User (`auth:sanctum`, `active`)
* `GET /api/me` or `/api/user` — Authenticated user's profile.
* `POST /api/logout` — Revoke the current bearer token.

### 4. Customer Cart (`auth:sanctum`)
* `GET /api/cart` — View current active cart with dynamically calculated item subtotals and order total.
* `POST /api/cart/items` — Add product to cart (`product_id`, `quantity`). If product already exists in cart, increments quantity.
* `PUT|PATCH /api/cart/items/{id}` — Update item quantity (`quantity`).
* `DELETE /api/cart/items/{id}` — Remove item from cart.
* `DELETE /api/cart` — Clear all items from cart.

### 5. Customer Orders & Checkout (`auth:sanctum`)
* `POST /api/orders` — Place order from current active cart.
  * Runs in atomic database transaction with row locks.
  * Validates stock and product status.
  * Decrements inventory.
  * Creates order & order items with historical price snapshots.
  * Clears customer's cart.
* `GET /api/orders` — Customer's paginated order history.
* `GET /api/orders/{id}` — Customer's order details with strict ownership policy (403 if accessing another customer's order).

### 6. Admin Management (`auth:sanctum`, `admin`)
* `GET /api/admin/dashboard` — Live database analytics (`total_users`, `total_customers`, `total_products`, `total_categories`, `total_orders`, `pending_orders`, `delivered_orders`, `total_sales`, `recent_orders`, `low_stock_products`).
* `GET /api/admin/users` — List users with search, role, status filters, and pagination.
* `POST /api/admin/users` — Create user (admin or customer).
* `GET /api/admin/users/{id}` — View user details.
* `PUT|PATCH /api/admin/users/{id}` — Update user details (includes safeguard against admin demoting or deactivating themselves).
* `DELETE /api/admin/users/{id}` — Delete user (includes safeguard against deleting self or sole admin).
* `apiResource('admin/categories')` — Full category CRUD with FK protection preventing deletion of categories containing products.
* `apiResource('admin/products')` — Full product CRUD with validation preventing negative prices or negative stock.
* `GET /api/admin/orders` — Search orders by order number, customer name, email, or status filter.
* `GET /api/admin/orders/{id}` — View full order details with customer and items.
* `PATCH /api/admin/orders/{id}/status` — Update order status. Cancelling an order automatically restores reserved stock to inventory.

---

## Running Setup & Tests

```bash
# Run fresh migrations with realistic seed data
php artisan migrate:fresh --seed

# Run automated test suite
php artisan test
```
