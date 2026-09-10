<?php

namespace App\Http\Controllers\Admin;

use App\Http\Controllers\Controller;
use App\Models\Category;
use App\Models\Order;
use App\Models\Product;
use App\Models\User;
use App\Traits\ApiResponse;
use Illuminate\Http\JsonResponse;

class DashboardController extends Controller
{
    use ApiResponse;

    /**
     * Retrieve aggregate dashboard statistics for the administrator.
     */
    public function index(): JsonResponse
    {
        $totalUsers = User::count();
        $totalCustomers = User::where('role', 'customer')->count();
        $totalProducts = Product::count();
        $totalCategories = Category::count();
        $totalOrders = Order::count();
        $pendingOrders = Order::where('status', Order::STATUS_PENDING)->count();
        $deliveredOrders = Order::where('status', Order::STATUS_DELIVERED)->count();
        $cancelledOrders = Order::where('status', Order::STATUS_CANCELLED)->count();

        // Total sales from non-cancelled orders
        $totalSales = (float) Order::where('status', '!=', Order::STATUS_CANCELLED)->sum('total');

        // Recent orders
        $recentOrders = Order::with('user')
            ->latest()
            ->take(5)
            ->get(['id', 'user_id', 'order_number', 'total', 'status', 'created_at']);

        // Low stock products (stock <= 5)
        $lowStockProducts = Product::where('stock', '<=', 5)
            ->take(5)
            ->get(['id', 'name', 'stock', 'price']);

        return $this->successResponse([
            'total_users' => $totalUsers,
            'total_customers' => $totalCustomers,
            'total_products' => $totalProducts,
            'total_categories' => $totalCategories,
            'total_orders' => $totalOrders,
            'pending_orders' => $pendingOrders,
            'delivered_orders' => $deliveredOrders,
            'cancelled_orders' => $cancelledOrders,
            'total_sales' => round($totalSales, 2),
            'recent_orders' => $recentOrders,
            'low_stock_products' => $lowStockProducts,
        ], 'Dashboard statistics retrieved successfully.');
    }
}
