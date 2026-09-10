<?php

namespace Tests\Feature;

use App\Models\Order;
use App\Models\User;
use Illuminate\Foundation\Testing\DatabaseTransactions;
use Tests\TestCase;

class AuthorizationTest extends TestCase
{
    use DatabaseTransactions;

    public function test_customer_cannot_access_admin_dashboard_receiving_403(): void
    {
        $customer = User::factory()->create([
            'role' => 'customer',
            'status' => 'active',
        ]);

        $response = $this->actingAs($customer, 'sanctum')
            ->getJson('/api/admin/dashboard');

        $response->assertStatus(403)
            ->assertJson([
                'success' => false,
                'message' => 'Access denied. Administrator privileges required.',
            ]);
    }

    public function test_customer_cannot_access_admin_user_management(): void
    {
        $customer = User::factory()->create([
            'role' => 'customer',
            'status' => 'active',
        ]);

        $response = $this->actingAs($customer, 'sanctum')
            ->getJson('/api/admin/users');

        $response->assertStatus(403);
    }

    public function test_admin_can_access_admin_endpoints(): void
    {
        $admin = User::factory()->create([
            'role' => 'admin',
            'status' => 'active',
        ]);

        $response = $this->actingAs($admin, 'sanctum')
            ->getJson('/api/admin/dashboard');

        $response->assertStatus(200)
            ->assertJson(['success' => true]);
    }

    public function test_unauthenticated_request_to_protected_routes_returns_401(): void
    {
        $response = $this->getJson('/api/cart');
        $response->assertStatus(401);

        $response = $this->getJson('/api/orders');
        $response->assertStatus(401);

        $response = $this->getJson('/api/admin/dashboard');
        $response->assertStatus(401);
    }

    public function test_customer_cannot_access_another_customer_order(): void
    {
        $customerA = User::factory()->create(['role' => 'customer', 'status' => 'active']);
        $customerB = User::factory()->create(['role' => 'customer', 'status' => 'active']);

        $orderA = Order::create([
            'user_id' => $customerA->id,
            'order_number' => 'ORD-TEST-OWNERSHIP-1',
            'subtotal' => 50.00,
            'total' => 50.00,
            'status' => Order::STATUS_PENDING,
        ]);

        // Customer B attempts to view Customer A's order
        $response = $this->actingAs($customerB, 'sanctum')
            ->getJson("/api/orders/{$orderA->id}");

        $response->assertStatus(403);
    }
}
