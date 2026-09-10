<?php

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\DatabaseTransactions;
use Tests\TestCase;

class AdminUserTest extends TestCase
{
    use DatabaseTransactions;

    protected User $admin;
    protected User $customer;

    protected function setUp(): void
    {
        parent::setUp();

        $this->admin = User::factory()->admin()->create();
        $this->customer = User::factory()->create();
    }

    public function test_admin_can_list_users_with_search_and_role_filter(): void
    {
        $response = $this->actingAs($this->admin, 'sanctum')
            ->getJson('/api/admin/users?role=customer');

        $response->assertStatus(200)
            ->assertJson(['success' => true]);

        $roles = collect($response->json('data.users'))->pluck('role')->unique();
        $this->assertTrue($roles->contains('customer'));
    }

    public function test_admin_can_create_new_user(): void
    {
        $payload = [
            'name' => 'New Staff Admin',
            'email' => 'newstaff@example.com',
            'password' => 'staffpass123',
            'role' => 'admin',
            'status' => 'active',
        ];

        $response = $this->actingAs($this->admin, 'sanctum')
            ->postJson('/api/admin/users', $payload);

        $response->assertStatus(201)
            ->assertJson([
                'success' => true,
                'data' => [
                    'email' => 'newstaff@example.com',
                    'role' => 'admin',
                ],
            ]);

        $this->assertDatabaseHas('users', ['email' => 'newstaff@example.com', 'role' => 'admin']);
    }

    public function test_admin_cannot_demote_or_deactivate_self(): void
    {
        $demoteResponse = $this->actingAs($this->admin, 'sanctum')
            ->putJson("/api/admin/users/{$this->admin->id}", [
                'role' => 'customer',
            ]);

        $demoteResponse->assertStatus(422)
            ->assertJson(['success' => false]);

        $deactivateResponse = $this->actingAs($this->admin, 'sanctum')
            ->putJson("/api/admin/users/{$this->admin->id}", [
                'status' => 'inactive',
            ]);

        $deactivateResponse->assertStatus(422)
            ->assertJson(['success' => false]);
    }

    public function test_admin_cannot_delete_self(): void
    {
        $response = $this->actingAs($this->admin, 'sanctum')
            ->deleteJson("/api/admin/users/{$this->admin->id}");

        $response->assertStatus(422)
            ->assertJson([
                'success' => false,
                'message' => 'You cannot delete your own account.',
            ]);

        $this->assertDatabaseHas('users', ['id' => $this->admin->id]);
    }

    public function test_admin_can_delete_another_user(): void
    {
        $response = $this->actingAs($this->admin, 'sanctum')
            ->deleteJson("/api/admin/users/{$this->customer->id}");

        $response->assertStatus(200)
            ->assertJson([
                'success' => true,
                'message' => 'User deleted successfully.',
            ]);

        $this->assertDatabaseMissing('users', ['id' => $this->customer->id]);
    }
}
