<?php

namespace Tests\Feature;

use App\Models\Cart;
use App\Models\CartItem;
use App\Models\Category;
use App\Models\Order;
use App\Models\OrderItem;
use App\Models\Product;
use App\Models\User;
use Illuminate\Foundation\Testing\DatabaseTransactions;
use Tests\TestCase;

class OrderTest extends TestCase
{
    use DatabaseTransactions;

    protected User $admin;
    protected User $customer;
    protected Category $category;
    protected Product $product1;
    protected Product $product2;

    protected function setUp(): void
    {
        parent::setUp();

        $this->admin = User::factory()->admin()->create();
        $this->customer = User::factory()->create();

        $this->category = Category::create([
            'name' => 'Order Test Category',
            'slug' => 'order-test-category',
            'status' => 'active',
        ]);

        $this->product1 = Product::create([
            'category_id' => $this->category->id,
            'name' => 'Order Test Product 1',
            'slug' => 'order-test-prod-1',
            'price' => 100.00,
            'stock' => 10,
            'status' => 'active',
        ]);

        $this->product2 = Product::create([
            'category_id' => $this->category->id,
            'name' => 'Order Test Product 2',
            'slug' => 'order-test-prod-2',
            'price' => 50.00,
            'stock' => 5,
            'status' => 'active',
        ]);
    }

    public function test_empty_cart_checkout_is_rejected(): void
    {
        $response = $this->actingAs($this->customer, 'sanctum')
            ->postJson('/api/orders');

        $response->assertStatus(422)
            ->assertJsonValidationErrors(['cart']);
    }

    public function test_successful_checkout_creates_order_snapshots_deducts_stock_and_clears_cart(): void
    {
        $cart = Cart::firstOrCreate(['user_id' => $this->customer->id]);
        CartItem::create(['cart_id' => $cart->id, 'product_id' => $this->product1->id, 'quantity' => 2]);
        CartItem::create(['cart_id' => $cart->id, 'product_id' => $this->product2->id, 'quantity' => 1]);

        $response = $this->actingAs($this->customer, 'sanctum')
            ->postJson('/api/orders');

        $response->assertStatus(201)
            ->assertJson([
                'success' => true,
                'message' => 'Order placed successfully.',
                'data' => [
                    'subtotal' => 250.00,
                    'total' => 250.00,
                    'status' => 'pending',
                ],
            ]);

        $orderId = $response->json('data.id');

        // Verify order exists in DB
        $this->assertDatabaseHas('orders', [
            'id' => $orderId,
            'user_id' => $this->customer->id,
            'total' => 250.00,
            'status' => 'pending',
        ]);

        // Verify order items snapshots exist
        $this->assertDatabaseHas('order_items', [
            'order_id' => $orderId,
            'product_name' => 'Order Test Product 1',
            'price' => 100.00,
            'quantity' => 2,
            'subtotal' => 200.00,
        ]);

        $this->assertDatabaseHas('order_items', [
            'order_id' => $orderId,
            'product_name' => 'Order Test Product 2',
            'price' => 50.00,
            'quantity' => 1,
            'subtotal' => 50.00,
        ]);

        // Verify product stock was reduced
        $this->assertEquals(8, $this->product1->fresh()->stock); // 10 - 2
        $this->assertEquals(4, $this->product2->fresh()->stock); // 5 - 1

        // Verify cart is cleared
        $this->assertEquals(0, $cart->fresh()->items()->count());
    }

    public function test_checkout_fails_and_rolls_back_if_product_has_insufficient_stock(): void
    {
        $cart = Cart::firstOrCreate(['user_id' => $this->customer->id]);
        CartItem::create(['cart_id' => $cart->id, 'product_id' => $this->product2->id, 'quantity' => 10]); // Available is 5

        $response = $this->actingAs($this->customer, 'sanctum')
            ->postJson('/api/orders');

        $response->assertStatus(422)
            ->assertJsonValidationErrors(['stock']);

        // Verify stock remains untouched
        $this->assertEquals(5, $this->product2->fresh()->stock);

        // Verify no order was created
        $this->assertEquals(0, Order::where('user_id', $this->customer->id)->count());

        // Verify cart is kept intact
        $this->assertEquals(1, $cart->fresh()->items()->count());
    }

    public function test_customer_can_view_own_orders_and_order_details(): void
    {
        $order = Order::create([
            'user_id' => $this->customer->id,
            'order_number' => 'ORD-MY-ORDER-123',
            'subtotal' => 100.00,
            'total' => 100.00,
            'status' => 'pending',
        ]);

        $response = $this->actingAs($this->customer, 'sanctum')
            ->getJson('/api/orders');

        $response->assertStatus(200)
            ->assertJson(['success' => true]);

        $orderNumbers = collect($response->json('data.orders'))->pluck('order_number');
        $this->assertTrue($orderNumbers->contains('ORD-MY-ORDER-123'));

        $detailResponse = $this->actingAs($this->customer, 'sanctum')
            ->getJson("/api/orders/{$order->id}");

        $detailResponse->assertStatus(200)
            ->assertJson([
                'success' => true,
                'data' => [
                    'order_number' => 'ORD-MY-ORDER-123',
                    'total' => 100.00,
                ],
            ]);
    }

    public function test_admin_can_list_and_search_orders(): void
    {
        $order = Order::create([
            'user_id' => $this->customer->id,
            'order_number' => 'ORD-ADMIN-SEARCH-999',
            'subtotal' => 150.00,
            'total' => 150.00,
            'status' => 'confirmed',
        ]);

        $response = $this->actingAs($this->admin, 'sanctum')
            ->getJson('/api/admin/orders?search=SEARCH-999');

        $response->assertStatus(200);
        $orders = collect($response->json('data.orders'));
        $this->assertTrue($orders->contains('order_number', 'ORD-ADMIN-SEARCH-999'));
    }

    public function test_admin_can_update_order_status_and_cancellation_restores_stock(): void
    {
        $order = Order::create([
            'user_id' => $this->customer->id,
            'order_number' => 'ORD-STATUS-TEST',
            'subtotal' => 200.00,
            'total' => 200.00,
            'status' => 'processing',
        ]);

        OrderItem::create([
            'order_id' => $order->id,
            'product_id' => $this->product1->id,
            'product_name' => $this->product1->name,
            'quantity' => 3,
            'price' => 100.00,
            'subtotal' => 300.00,
        ]);

        // Stock was 10. When cancelled, stock should increase by 3 to 13
        $initialStock = $this->product1->fresh()->stock;

        $response = $this->actingAs($this->admin, 'sanctum')
            ->patchJson("/api/admin/orders/{$order->id}/status", [
                'status' => 'cancelled',
            ]);

        $response->assertStatus(200)
            ->assertJson([
                'success' => true,
                'data' => [
                    'status' => 'cancelled',
                ],
            ]);

        $this->assertEquals($initialStock + 3, $this->product1->fresh()->stock);
    }

    public function test_admin_updating_order_with_invalid_status_is_rejected(): void
    {
        $order = Order::create([
            'user_id' => $this->customer->id,
            'order_number' => 'ORD-INVALID-STATUS',
            'subtotal' => 50.00,
            'total' => 50.00,
            'status' => 'pending',
        ]);

        $response = $this->actingAs($this->admin, 'sanctum')
            ->patchJson("/api/admin/orders/{$order->id}/status", [
                'status' => 'not_a_real_status',
            ]);

        $response->assertStatus(422)
            ->assertJsonValidationErrors(['status']);
    }

    public function test_admin_dashboard_returns_real_database_metrics(): void
    {
        $response = $this->actingAs($this->admin, 'sanctum')
            ->getJson('/api/admin/dashboard');

        $response->assertStatus(200)
            ->assertJson([
                'success' => true,
            ])
            ->assertJsonStructure([
                'data' => [
                    'total_users',
                    'total_customers',
                    'total_products',
                    'total_categories',
                    'total_orders',
                    'pending_orders',
                    'delivered_orders',
                    'cancelled_orders',
                    'total_sales',
                    'recent_orders',
                    'low_stock_products',
                ],
            ]);

        $this->assertIsNumeric($response->json('data.total_sales'));
        $this->assertGreaterThanOrEqual(1, $response->json('data.total_users'));
    }
}
