import { Component, OnInit, inject, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { AdminService } from '../../../core/services/admin.service';

@Component({
  selector: 'app-admin-user-list',
  standalone: true,
  imports: [CommonModule, RouterModule, FormsModule],
  template: `
    <div class="admin-page">
      <div class="page-header">
        <h2>Manage Users</h2>
        <a routerLink="/admin/users/new" class="btn btn-primary">Add New User</a>
      </div>

      <div class="filters-card">
        <div class="filter-group">
          <input type="text" [(ngModel)]="search" placeholder="Search name or email..." class="form-control" (keyup.enter)="loadUsers()">
        </div>
        <div class="filter-group">
          <select [(ngModel)]="role" class="form-control" (change)="loadUsers()">
            <option value="">All Roles</option>
            <option value="admin">Admin</option>
            <option value="customer">Customer</option>
          </select>
        </div>
        <div class="filter-group">
          <select [(ngModel)]="status" class="form-control" (change)="loadUsers()">
            <option value="">All Statuses</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </div>
        <button class="btn btn-secondary" (click)="loadUsers()">Apply</button>
      </div>

      <div *ngIf="error" class="alert alert-danger">{{ error }}</div>

      <div class="table-responsive" *ngIf="!isLoading && users.length > 0">
        <table class="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Name</th>
              <th>Email</th>
              <th>Role</th>
              <th>Status</th>
              <th>Created</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr *ngFor="let user of users">
              <td>{{ user.id }}</td>
              <td>{{ user.name }}</td>
              <td>{{ user.email }}</td>
              <td><span class="badge" [ngClass]="user.role === 'admin' ? 'badge-primary' : 'badge-secondary'">{{ user.role }}</span></td>
              <td><span class="badge" [ngClass]="user.status === 'active' ? 'badge-success' : 'badge-danger'">{{ user.status }}</span></td>
              <td>{{ user.created_at | date:'shortDate' }}</td>
              <td class="actions">
                <a [routerLink]="['/admin/users', user.id, 'edit']" class="btn btn-sm btn-info">Edit</a>
                <button class="btn btn-sm btn-danger" (click)="deleteUser(user.id)">Delete</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Pagination -->
      <div class="pagination" *ngIf="!isLoading && pagination && pagination.last_page > 1">
        <button class="btn btn-sm" [disabled]="pagination.current_page === 1" (click)="changePage(pagination.current_page - 1)">Previous</button>
        <span>Page {{ pagination.current_page }} of {{ pagination.last_page }}</span>
        <button class="btn btn-sm" [disabled]="pagination.current_page === pagination.last_page" (click)="changePage(pagination.current_page + 1)">Next</button>
      </div>

      <div *ngIf="isLoading" class="loader">Loading users...</div>
      
      <div *ngIf="!isLoading && users.length === 0" class="empty-state">
        No users found matching your criteria.
      </div>
    </div>
  `,
  styles: [`
    .page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
    h2 { margin: 0; color: #333; }
    
    .filters-card { background: white; padding: 15px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); display: flex; gap: 15px; flex-wrap: wrap; align-items: center; }
    .filter-group { flex: 1; min-width: 200px; }
    .form-control { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
    
    .table-responsive { background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); overflow-x: auto; }
    .table { width: 100%; border-collapse: collapse; }
    .table th, .table td { padding: 12px 15px; text-align: left; border-bottom: 1px solid #eee; }
    .table th { background-color: #f8f9fa; font-weight: 600; color: #555; }
    
    .badge { padding: 5px 10px; border-radius: 20px; font-size: 0.8rem; font-weight: 500; }
    .badge-primary { background-color: #cce5ff; color: #004085; }
    .badge-secondary { background-color: #e2e3e5; color: #383d41; }
    .badge-success { background-color: #d4edda; color: #155724; }
    .badge-danger { background-color: #f8d7da; color: #721c24; }
    
    .actions { display: flex; gap: 8px; }
    .btn-sm { padding: 5px 10px; font-size: 0.85rem; }
    .btn-info { background-color: #17a2b8; color: white; border: none; border-radius: 4px; text-decoration: none; cursor: pointer; }
    .btn-danger { background-color: #dc3545; color: white; border: none; border-radius: 4px; cursor: pointer; }
    .btn-secondary { background-color: #6c757d; color: white; padding: 10px 15px; border: none; border-radius: 4px; cursor: pointer; }
    
    .pagination { display: flex; justify-content: center; align-items: center; gap: 15px; margin-top: 20px; }
    .loader { text-align: center; padding: 40px; color: #666; }
    .empty-state { text-align: center; padding: 40px; background: white; border-radius: 8px; color: #666; }
    .alert { padding: 15px; border-radius: 4px; margin-bottom: 15px; }
    .alert-danger { background: #f8d7da; color: #721c24; border: 1px solid #f5c2c7; }
  `]
})
export class AdminUserListComponent implements OnInit {
  private adminService = inject(AdminService);
  private cdr = inject(ChangeDetectorRef);

  users: any[] = [];
  pagination: any = null;
  isLoading = true;
  error = '';

  // Filters
  search = '';
  role = '';
  status = '';
  page = 1;

  ngOnInit() {
    this.loadUsers();
  }

  loadUsers() {
    this.isLoading = true;
    this.error = '';

    const params: any = { page: this.page };
    if (this.search) params.search = this.search;
    if (this.role) params.role = this.role;
    if (this.status) params.status = this.status;

    this.adminService.getUsers(params).subscribe({
      next: (res: any) => {
        if (res && res.data) {
          // Check if data contains an inner array (Laravel Pagination usually does)
          if (Array.isArray(res.data)) {
            this.users = res.data;
          } else if (res.data.users && Array.isArray(res.data.users)) {
            this.users = res.data.users;
          } else if (res.data.data && Array.isArray(res.data.data)) {
            this.users = res.data.data;
          }
          this.pagination = res.data.pagination || res.pagination || res.meta || null;
        } else {
          this.users = [];
        }
        this.isLoading = false;
        this.cdr.detectChanges();
      },
      error: (err: any) => {
        this.error = 'Failed to load users.';
        this.isLoading = false;
        this.cdr.detectChanges();
      }
    });
  }

  changePage(newPage: number) {
    this.page = newPage;
    this.loadUsers();
  }

  deleteUser(id: number) {
    if (confirm('Are you sure you want to delete this user?')) {
      this.adminService.deleteUser(id).subscribe({
        next: () => {
          this.loadUsers();
        },
        error: (err: any) => {
          this.error = err.error?.message || 'Failed to delete user. You may not have permission.';
          this.cdr.detectChanges();
        }
      });
    }
  }
}
