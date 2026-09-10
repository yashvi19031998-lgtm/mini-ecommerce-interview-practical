<?php

namespace App\Services;

use App\Models\Cart;
use App\Models\Order;
use App\Models\OrderItem;
use App\Models\Product;
use App\Models\User;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Illuminate\Validation\ValidationException;

class OrderService
{
    /**
     * Place an order from the user's active cart.
     * Executes entirely inside a database transaction with row locking.
     *
     * @throws ValidationException
     */
    public function checkout(User $user): Order
    {
        return DB::transaction(function () use ($user) {
            $cart = Cart::where('user_id', $user->id)
                ->with('items')
                ->first();

            if (!$cart || $cart->items->isEmpty()) {
                throw ValidationException::withMessages([
                    'cart' => ['Your cart is empty. Please add items before placing an order.'],
                ]);
            }

            $orderItemsData = [];
            $orderSubtotal = 0.00;

            // Validate all products, check stock with lock, calculate DB prices
            foreach ($cart->items as $item) {
                $product = Product::where('id', $item->product_id)
                    ->lockForUpdate()
                    ->first();

                if (!$product) {
                    throw ValidationException::withMessages([
                        'cart' => ["A product in your cart (ID: {$item->product_id}) no longer exists."],
                    ]);
                }

                if ($product->status !== 'active') {
                    throw ValidationException::withMessages([
                        'cart' => ["Product '{$product->name}' is no longer active."],
                    ]);
                }

                if ($product->stock < $item->quantity) {
                    throw ValidationException::withMessages([
                        'stock' => ["Insufficient stock for '{$product->name}'. Available: {$product->stock}, in cart: {$item->quantity}."],
                    ]);
                }

                $price = (float) $product->price;
                $itemSubtotal = round($item->quantity * $price, 2);
                $orderSubtotal += $itemSubtotal;

                $orderItemsData[] = [
                    'product' => $product,
                    'product_id' => $product->id,
                    'product_name' => $product->name,
                    'quantity' => $item->quantity,
                    'price' => $price,
                    'subtotal' => $itemSubtotal,
                ];
            }

            $orderSubtotal = round($orderSubtotal, 2);
            $orderTotal = $orderSubtotal; // Can accommodate taxes or shipping if needed

            // Generate unique order number
            $orderNumber = 'ORD-' . strtoupper(Str::random(6)) . '-' . date('YmdHis');

            // Create order
            $order = Order::create([
                'user_id' => $user->id,
                'order_number' => $orderNumber,
                'subtotal' => $orderSubtotal,
                'total' => $orderTotal,
                'status' => Order::STATUS_PENDING,
            ]);

            // Create order items with snapshots and decrement stock
            foreach ($orderItemsData as $itemData) {
                OrderItem::create([
                    'order_id' => $order->id,
                    'product_id' => $itemData['product_id'],
                    'product_name' => $itemData['product_name'],
                    'quantity' => $itemData['quantity'],
                    'price' => $itemData['price'],
                    'subtotal' => $itemData['subtotal'],
                ]);

                $itemData['product']->decrement('stock', $itemData['quantity']);
            }

            // Clear the cart
            $cart->items()->delete();

            return $order->load(['items.product', 'user']);
        });
    }

    /**
     * Update order status with stock adjustment if cancelled/restored.
     *
     * @throws ValidationException
     */
    public function updateStatus(Order $order, string $newStatus): Order
    {
        return DB::transaction(function () use ($order, $newStatus) {
            $oldStatus = $order->status;

            if ($oldStatus === $newStatus) {
                return $order->load(['items.product', 'user']);
            }

            // If cancelling an order, return reserved stock back to products
            if ($newStatus === Order::STATUS_CANCELLED && $oldStatus !== Order::STATUS_CANCELLED) {
                foreach ($order->items as $item) {
                    if ($item->product_id) {
                        $product = Product::where('id', $item->product_id)->lockForUpdate()->first();
                        if ($product) {
                            $product->increment('stock', $item->quantity);
                        }
                    }
                }
            }

            // If reactivating a cancelled order, re-check and decrement stock
            if ($oldStatus === Order::STATUS_CANCELLED && $newStatus !== Order::STATUS_CANCELLED) {
                foreach ($order->items as $item) {
                    if ($item->product_id) {
                        $product = Product::where('id', $item->product_id)->lockForUpdate()->first();
                        if (!$product || $product->stock < $item->quantity) {
                            throw ValidationException::withMessages([
                                'status' => ["Cannot reactivate order. Insufficient stock for product '{$item->product_name}'."],
                            ]);
                        }
                        $product->decrement('stock', $item->quantity);
                    }
                }
            }

            $order->update(['status' => $newStatus]);

            return $order->fresh(['items.product', 'user']);
        });
    }
}
