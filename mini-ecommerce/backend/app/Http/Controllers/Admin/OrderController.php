<?php

namespace App\Http\Controllers\Admin;

use App\Http\Controllers\Controller;
use App\Http\Requests\Admin\UpdateOrderStatusRequest;
use App\Http\Resources\OrderResource;
use App\Models\Order;
use App\Services\OrderService;
use App\Traits\ApiResponse;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class OrderController extends Controller
{
    use ApiResponse;

    protected OrderService $orderService;

    public function __construct(OrderService $orderService)
    {
        $this->orderService = $orderService;
    }

    /**
     * Display a listing of all orders for admin.
     */
    public function index(Request $request): JsonResponse
    {
        $query = Order::with(['user', 'items.product']);

        if ($request->filled('search')) {
            $search = $request->search;
            $query->where(function ($q) use ($search) {
                $q->where('order_number', 'like', "%{$search}%")
                  ->orWhereHas('user', function ($userQuery) use ($search) {
                      $userQuery->where('name', 'like', "%{$search}%")
                                ->orWhere('email', 'like', "%{$search}%");
                  });
            });
        }

        if ($request->filled('status')) {
            $query->where('status', $request->status);
        }

        $perPage = min((int) $request->get('per_page', 15), 100);
        $orders = $query->latest()->paginate($perPage);

        return $this->successResponse([
            'orders' => OrderResource::collection($orders),
            'pagination' => [
                'total' => $orders->total(),
                'per_page' => $orders->perPage(),
                'current_page' => $orders->currentPage(),
                'last_page' => $orders->lastPage(),
            ],
        ], 'Orders retrieved successfully.');
    }

    /**
     * Display the specified order details for admin.
     */
    public function show(int $id): JsonResponse
    {
        $order = Order::with(['user', 'items.product'])->findOrFail($id);

        return $this->successResponse(
            new OrderResource($order),
            'Order details retrieved successfully.'
        );
    }

    /**
     * Update the status of an order (e.g. processing, shipped, delivered, cancelled).
     */
    public function updateStatus(UpdateOrderStatusRequest $request, int $id): JsonResponse
    {
        $order = Order::findOrFail($id);

        $updatedOrder = $this->orderService->updateStatus(
            $order,
            $request->validated('status')
        );

        return $this->successResponse(
            new OrderResource($updatedOrder),
            'Order status updated successfully.'
        );
    }
}
