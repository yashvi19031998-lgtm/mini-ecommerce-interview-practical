<?php

namespace Tests\Feature;

use App\Models\Category;
use App\Models\Product;
use App\Models\User;
use Illuminate\Foundation\Testing\DatabaseTransactions;
use Tests\TestCase;

class CartTest extends TestCase
{
    use DatabaseTransactions;

    protected User $customer;
    protected Product $product;

    protected function setUp(): void
    {
        parent::setUp();

        $this->customer = User::factory()->create();

        $category = Category::create([
            'name' => 'Cart Test Category',
            'slug' => 'cart-test-category',
            'status' => 'active',
        ]);

        $this->product = Product::create([
            'category_id' => $category->id,
            'name' => 'Cart Product',
            'slug' => 'cart-product',
            'price' => 25.00,
            'stock' => 10,
            'status' => 'active',
        ]);
    }

    public function test_customer_can_add_product_to_cart(): void
    {
        $response = $this->actingAs($this->customer, 'sanctum')
            ->postJson('/api/cart/items', [
                'product_id' => $this->product->id,
                'quantity' => 2,
            ]);

        $response->assertStatus(201)
            ->assertJson([
                'success' => true,
                'data' => [
                    'total' => 50.00,
                    'total_items' => 2,
                ],
            ]);

        $this->assertDatabaseHas('cart_items', [
            'product_id' => $this->product->id,
            'quantity' => 2,
        ]);
    }

    public function test_adding_same_product_increases_quantity_instead_of_duplicate(): void
    {
        $this->actingAs($this->customer, 'sanctum')
            ->postJson('/api/cart/items', [
                'product_id' => $this->product->id,
                'quantity' => 2,
            ]);

        $response = $this->actingAs($this->customer, 'sanctum')
            ->postJson('/api/cart/items', [
                'product_id' => $this->product->id,
                'quantity' => 3,
            ]);

        $response->assertStatus(201)
            ->assertJson([
                'data' => [
                    'total' => 125.00,
                    'total_items' => 5,
                ],
            ]);

        // Verify only 1 cart_item row exists for this customer's cart
        $cart = \App\Models\Cart::where('user_id', $this->customer->id)->first();
        $this->assertEquals(1, $cart->items()->count());
        $this->assertDatabaseHas('cart_items', [
            'cart_id' => $cart->id,
            'product_id' => $this->product->id,
            'quantity' => 5,
        ]);
    }

    public function test_cannot_add_more_quantity_than_available_stock(): void
    {
        $response = $this->actingAs($this->customer, 'sanctum')
            ->postJson('/api/cart/items', [
                'product_id' => $this->product->id,
                'quantity' => 15, // Available is 10
            ]);

        $response->assertStatus(422)
            ->assertJsonValidationErrors(['quantity']);
    }

    public function test_customer_can_update_cart_item_quantity(): void
    {
        $addResponse = $this->actingAs($this->customer, 'sanctum')
            ->postJson('/api/cart/items', [
                'product_id' => $this->product->id,
                'quantity' => 2,
            ]);

        $cartItemId = $addResponse->json('data.items.0.id');

        $response = $this->actingAs($this->customer, 'sanctum')
            ->putJson("/api/cart/items/{$cartItemId}", [
                'quantity' => 4,
            ]);

        $response->assertStatus(200)
            ->assertJson([
                'success' => true,
                'data' => [
                    'total' => 100.00,
                    'total_items' => 4,
                ],
            ]);

        $this->assertDatabaseHas('cart_items', [
            'id' => $cartItemId,
            'quantity' => 4,
        ]);
    }

    public function test_customer_can_remove_cart_item(): void
    {
        $addResponse = $this->actingAs($this->customer, 'sanctum')
            ->postJson('/api/cart/items', [
                'product_id' => $this->product->id,
                'quantity' => 2,
            ]);

        $cartItemId = $addResponse->json('data.items.0.id');

        $response = $this->actingAs($this->customer, 'sanctum')
            ->deleteJson("/api/cart/items/{$cartItemId}");

        $response->assertStatus(200)
            ->assertJson([
                'success' => true,
                'message' => 'Item removed from cart successfully.',
            ]);

        $this->assertDatabaseMissing('cart_items', ['id' => $cartItemId]);
    }

    public function test_customer_can_clear_cart(): void
    {
        $this->actingAs($this->customer, 'sanctum')
            ->postJson('/api/cart/items', [
                'product_id' => $this->product->id,
                'quantity' => 2,
            ]);

        $response = $this->actingAs($this->customer, 'sanctum')
            ->deleteJson('/api/cart');

        $response->assertStatus(200)
            ->assertJson([
                'data' => [
                    'total' => 0,
                    'total_items' => 0,
                ],
            ]);

        $cart = \App\Models\Cart::where('user_id', $this->customer->id)->first();
        $this->assertEquals(0, $cart->items()->count());
    }
}
