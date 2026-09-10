<?php

namespace App\Http\Controllers;

use App\Http\Requests\Cart\AddCartItemRequest;
use App\Http\Requests\Cart\UpdateCartItemRequest;
use App\Http\Resources\CartResource;
use App\Services\CartService;
use App\Traits\ApiResponse;
use Exception;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class CartController extends Controller
{
    use ApiResponse;

    protected CartService $cartService;

    public function __construct(CartService $cartService)
    {
        $this->cartService = $cartService;
    }

    /**
     * Retrieve the customer's current active cart.
     */
    public function index(Request $request): JsonResponse
    {
        $cart = $this->cartService->getOrCreateCart($request->user());

        return $this->successResponse(
            new CartResource($cart),
            'Cart retrieved successfully.'
        );
    }

    /**
     * Add an item to the customer's cart.
     */
    public function store(AddCartItemRequest $request): JsonResponse
    {
        $cart = $this->cartService->addItem(
            $request->user(),
            (int) $request->validated('product_id'),
            (int) $request->validated('quantity')
        );

        return $this->successResponse(
            new CartResource($cart),
            'Item added to cart successfully.',
            201
        );
    }

    /**
     * Update quantity of an item in the cart.
     */
    public function update(UpdateCartItemRequest $request, int $id): JsonResponse
    {
        try {
            $cart = $this->cartService->updateItem(
                $request->user(),
                $id,
                (int) $request->validated('quantity')
            );

            return $this->successResponse(
                new CartResource($cart),
                'Cart item updated successfully.'
            );
        } catch (Exception $e) {
            return $this->errorResponse($e->getMessage(), 404);
        }
    }

    /**
     * Remove an item from the customer's cart.
     */
    public function destroy(Request $request, int $id): JsonResponse
    {
        try {
            $cart = $this->cartService->removeItem($request->user(), $id);

            return $this->successResponse(
                new CartResource($cart),
                'Item removed from cart successfully.'
            );
        } catch (Exception $e) {
            return $this->errorResponse($e->getMessage(), 404);
        }
    }

    /**
     * Clear all items from the customer's cart.
     */
    public function clear(Request $request): JsonResponse
    {
        $cart = $this->cartService->clearCart($request->user());

        return $this->successResponse(
            new CartResource($cart),
            'Cart cleared successfully.'
        );
    }
}
