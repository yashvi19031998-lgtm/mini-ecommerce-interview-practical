<?php

namespace App\Services;

use App\Models\Cart;
use App\Models\CartItem;
use App\Models\Product;
use App\Models\User;
use Exception;
use Illuminate\Validation\ValidationException;

class CartService
{
    /**
     * Get or create active cart for the user with eager loaded relationships.
     */
    public function getOrCreateCart(User $user): Cart
    {
        $cart = Cart::firstOrCreate(['user_id' => $user->id]);
        $cart->load(['items.product.category']);

        return $cart;
    }

    /**
     * Add a product to user's cart.
     *
     * @throws ValidationException
     */
    public function addItem(User $user, int $productId, int $quantity): Cart
    {
        $cart = $this->getOrCreateCart($user);

        $product = Product::find($productId);

        if (!$product) {
            throw ValidationException::withMessages([
                'product_id' => ['Product not found.'],
            ]);
        }

        if ($product->status !== 'active') {
            throw ValidationException::withMessages([
                'product_id' => ['This product is currently inactive and cannot be added to the cart.'],
            ]);
        }

        if ($product->stock < 1) {
            throw ValidationException::withMessages([
                'product_id' => ['Product is out of stock.'],
            ]);
        }

        $cartItem = CartItem::where('cart_id', $cart->id)
            ->where('product_id', $productId)
            ->first();

        $currentQuantityInCart = $cartItem ? $cartItem->quantity : 0;
        $newQuantity = $currentQuantityInCart + $quantity;

        if ($newQuantity > $product->stock) {
            throw ValidationException::withMessages([
                'quantity' => ["Cannot add {$quantity} items. Only {$product->stock} available in stock (you already have {$currentQuantityInCart} in cart)."],
            ]);
        }

        if ($cartItem) {
            $cartItem->update(['quantity' => $newQuantity]);
        } else {
            CartItem::create([
                'cart_id' => $cart->id,
                'product_id' => $productId,
                'quantity' => $quantity,
            ]);
        }

        return $this->getOrCreateCart($user);
    }

    /**
     * Update quantity of a cart item.
     *
     * @throws ValidationException|Exception
     */
    public function updateItem(User $user, int $cartItemId, int $quantity): Cart
    {
        $cart = $this->getOrCreateCart($user);

        $cartItem = CartItem::where('id', $cartItemId)
            ->where('cart_id', $cart->id)
            ->first();

        if (!$cartItem) {
            throw new Exception('Cart item not found or does not belong to you.');
        }

        $product = $cartItem->product;

        if (!$product || $product->status !== 'active') {
            throw ValidationException::withMessages([
                'cart_item' => ['The selected product is no longer active.'],
            ]);
        }

        if ($quantity > $product->stock) {
            throw ValidationException::withMessages([
                'quantity' => ["Cannot set quantity to {$quantity}. Only {$product->stock} available in stock."],
            ]);
        }

        $cartItem->update(['quantity' => $quantity]);

        return $this->getOrCreateCart($user);
    }

    /**
     * Remove a cart item.
     *
     * @throws Exception
     */
    public function removeItem(User $user, int $cartItemId): Cart
    {
        $cart = $this->getOrCreateCart($user);

        $cartItem = CartItem::where('id', $cartItemId)
            ->where('cart_id', $cart->id)
            ->first();

        if (!$cartItem) {
            throw new Exception('Cart item not found or does not belong to you.');
        }

        $cartItem->delete();

        return $this->getOrCreateCart($user);
    }

    /**
     * Clear all items from user's cart.
     */
    public function clearCart(User $user): Cart
    {
        $cart = $this->getOrCreateCart($user);
        $cart->items()->delete();

        return $this->getOrCreateCart($user);
    }
}
