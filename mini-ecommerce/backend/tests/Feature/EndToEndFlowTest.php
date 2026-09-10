<?php

namespace Tests\Feature;

use App\Models\Order;
use App\Models\Product;
use App\Models\User;
use Illuminate\Foundation\Testing\DatabaseTransactions;
use Tests\TestCase;

class EndToEndFlowTest extends TestCase
{
    use DatabaseTransactions;

    /**
     * Test the exact 21-step complete end-to-end backend flow:
     * 1. Seed admin/customer accounts
     * 2. Customer logs in
     * 3. Receive Sanctum token
     * 4. Customer requests products
     * 5. Customer adds product to cart
     * 6. Customer views cart
     * 7. Backend calculates cart total
     * 8. Customer updates quantity
     * 9. Customer places order
     * 10. Backend validates stock
     * 11. Backend creates order in transaction
     * 12. Backend creates order items
     * 13. Backend stores product price/name snapshots
     * 14. Backend decreases product stock
     * 15. Backend clears cart
     * 16. Customer views order
     * 17. Admin logs in
     * 18. Admin views dashboard
     * 19. Admin views orders
     * 20. Admin updates order status
     * 21. Customer sees updated status
     */
    public function test_complete_end_to_end_flow(): void
    {
        // Step 1: Using seeded accounts (admin@example.com, customer1@example.com with password123)
        // Step 2 & 3: Customer logs in and receives Sanctum token
        $loginResponse = $this->postJson('/api/login', [
            'email' => 'customer1@example.com',
            'password' => 'password123',
        ]);

        $loginResponse->assertStatus(200);
        $customerToken = $loginResponse->json('data.token');
        $this->assertNotEmpty($customerToken);

        $customerHeaders = [
            'Authorization' => "Bearer {$customerToken}",
            'Accept' => 'application/json',
        ];

        // Step 4: Customer requests products
        $productsResponse = $this->withHeaders($customerHeaders)->getJson('/api/products');
        $productsResponse->assertStatus(200);
        $firstProduct = $productsResponse->json('data.products.0');
        $productId = $firstProduct['id'];
        $productPrice = (float) $firstProduct['price'];
        $initialStock = (int) $firstProduct['stock'];
        $productName = $firstProduct['name'];

        // Step 5: Customer adds product to cart (quantity: 1)
        $addToCartResponse = $this->withHeaders($customerHeaders)->postJson('/api/cart/items', [
            'product_id' => $productId,
            'quantity' => 1,
        ]);
        $addToCartResponse->assertStatus(201);
        $cartItemId = $addToCartResponse->json('data.items.0.id');

        // Step 6 & 7: Customer views cart; backend calculates total
        $viewCartResponse = $this->withHeaders($customerHeaders)->getJson('/api/cart');
        $viewCartResponse->assertStatus(200);
        $this->assertEquals($productPrice, $viewCartResponse->json('data.total'));
        $this->assertEquals(1, $viewCartResponse->json('data.total_items'));

        // Step 8: Customer updates quantity to 2
        $updateCartResponse = $this->withHeaders($customerHeaders)->putJson("/api/cart/items/{$cartItemId}", [
            'quantity' => 2,
        ]);
        $updateCartResponse->assertStatus(200);
        $this->assertEquals(round(2 * $productPrice, 2), $updateCartResponse->json('data.total'));
        $this->assertEquals(2, $updateCartResponse->json('data.total_items'));

        // Step 9, 10, 11, 12, 13, 14, 15: Customer places order
        $checkoutResponse = $this->withHeaders($customerHeaders)->postJson('/api/orders');
        $checkoutResponse->assertStatus(201)
            ->assertJson([
                'success' => true,
                'data' => [
                    'subtotal' => round(2 * $productPrice, 2),
                    'total' => round(2 * $productPrice, 2),
                    'status' => 'pending',
                ],
            ]);

        $orderId = $checkoutResponse->json('data.id');
        $orderNumber = $checkoutResponse->json('data.order_number');

        // Step 13: Verify snapshots
        $this->assertDatabaseHas('order_items', [
            'order_id' => $orderId,
            'product_id' => $productId,
            'product_name' => $productName,
            'quantity' => 2,
            'price' => $productPrice,
            'subtotal' => round(2 * $productPrice, 2),
        ]);

        // Step 14: Verify stock decreased
        $productInDb = Product::find($productId);
        $this->assertEquals($initialStock - 2, $productInDb->stock);

        // Step 15: Verify cart cleared
        $cartCheckResponse = $this->withHeaders($customerHeaders)->getJson('/api/cart');
        $this->assertEquals(0, $cartCheckResponse->json('data.total_items'));

        // Step 16: Customer views order
        $customerOrderResponse = $this->withHeaders($customerHeaders)->getJson("/api/orders/{$orderId}");
        $customerOrderResponse->assertStatus(200)
            ->assertJson([
                'data' => [
                    'id' => $orderId,
                    'order_number' => $orderNumber,
                    'status' => 'pending',
                ],
            ]);

        // Step 17: Admin logs in (flush prior guard cache)
        $this->app['auth']->forgetGuards();

        $adminLoginResponse = $this->postJson('/api/login', [
            'email' => 'admin@example.com',
            'password' => 'password123',
        ]);
        $adminLoginResponse->assertStatus(200);
        $adminToken = $adminLoginResponse->json('data.token');
        $adminHeaders = [
            'Authorization' => "Bearer {$adminToken}",
            'Accept' => 'application/json',
        ];

        // Step 18: Admin views dashboard
        auth()->forgetGuards();
        $this->app['auth']->forgetGuards();

        $dashboardResponse = $this->withHeaders($adminHeaders)->getJson('/api/admin/dashboard');
        $dashboardResponse->assertStatus(200)
            ->assertJson(['success' => true]);
        $this->assertGreaterThanOrEqual(1, $dashboardResponse->json('data.total_orders'));

        // Step 19: Admin views orders
        $adminOrdersResponse = $this->withHeaders($adminHeaders)->getJson("/api/admin/orders?search={$orderNumber}");
        $adminOrdersResponse->assertStatus(200);
        $foundOrders = collect($adminOrdersResponse->json('data.orders'));
        $this->assertTrue($foundOrders->contains('order_number', $orderNumber));

        // Step 20: Admin updates order status to 'shipped'
        $updateStatusResponse = $this->withHeaders($adminHeaders)->patchJson("/api/admin/orders/{$orderId}/status", [
            'status' => 'shipped',
        ]);
        $updateStatusResponse->assertStatus(200)
            ->assertJson([
                'data' => [
                    'status' => 'shipped',
                ],
            ]);

        // Step 21: Customer sees updated status ('shipped')
        $this->app['auth']->forgetGuards();

        $customerUpdatedOrderResponse = $this->withHeaders($customerHeaders)->getJson("/api/orders/{$orderId}");
        $customerUpdatedOrderResponse->assertStatus(200)
            ->assertJson([
                'data' => [
                    'id' => $orderId,
                    'status' => 'shipped',
                ],
            ]);
    }
}
