<?php

namespace App\Http\Controllers;

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
     * Checkout: Place a new order from current active cart.
     */
    public function store(Request $request): JsonResponse
    {
        $order = $this->orderService->checkout($request->user());

        return $this->successResponse(
            new OrderResource($order),
            'Order placed successfully.',
            201
        );
    }

    /**
     * Display a listing of orders for the authenticated customer.
     */
    public function index(Request $request): JsonResponse
    {
        $perPage = min((int) $request->get('per_page', 10), 50);

        $orders = Order::where('user_id', $request->user()->id)
            ->with(['items.product'])
            ->latest()
            ->paginate($perPage);

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
     * Display the specified order for the customer.
     * Enforces ownership: customer cannot access another customer's order.
     */
    public function show(Request $request, int $id): JsonResponse
    {
        $order = Order::with(['items.product', 'user'])->findOrFail($id);

        $this->authorize('view', $order);

        return $this->successResponse(
            new OrderResource($order),
            'Order details retrieved successfully.'
        );
    }
}
