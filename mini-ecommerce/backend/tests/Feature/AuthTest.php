<?php

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\DatabaseTransactions;
use Illuminate\Support\Facades\Hash;
use Tests\TestCase;

class AuthTest extends TestCase
{
    use DatabaseTransactions;

    public function test_customer_can_register_successfully(): void
    {
        $payload = [
            'name' => 'Alice Wonder',
            'email' => 'alice@example.com',
            'password' => 'secret123',
            'password_confirmation' => 'secret123',
        ];

        $response = $this->postJson('/api/register', $payload);

        $response->assertStatus(201)
            ->assertJson([
                'success' => true,
                'message' => 'Registration successful.',
            ])
            ->assertJsonStructure([
                'data' => [
                    'user' => ['id', 'name', 'email', 'role', 'status'],
                    'token',
                    'role',
                ],
            ]);

        $this->assertDatabaseHas('users', [
            'email' => 'alice@example.com',
            'role' => 'customer',
            'status' => 'active',
        ]);
    }

    public function test_public_registration_cannot_create_admin(): void
    {
        $payload = [
            'name' => 'Hacker Admin',
            'email' => 'hacker@example.com',
            'password' => 'secret123',
            'password_confirmation' => 'secret123',
            'role' => 'admin', // Attempted role escalation
        ];

        $response = $this->postJson('/api/register', $payload);

        $response->assertStatus(201);
        $this->assertDatabaseHas('users', [
            'email' => 'hacker@example.com',
            'role' => 'customer', // Must remain customer
        ]);
    }

    public function test_registration_validation_fails_with_invalid_data(): void
    {
        $response = $this->postJson('/api/register', [
            'name' => '',
            'email' => 'not-an-email',
            'password' => '123',
            'password_confirmation' => 'mismatch',
        ]);

        $response->assertStatus(422)
            ->assertJson([
                'success' => false,
                'message' => 'Validation failed.',
            ])
            ->assertJsonValidationErrors(['name', 'email', 'password']);
    }

    public function test_user_can_login_with_valid_credentials(): void
    {
        $user = User::create([
            'name' => 'Test Login User',
            'email' => 'testlogin@example.com',
            'password' => Hash::make('password123'),
            'role' => 'customer',
            'status' => 'active',
        ]);

        $response = $this->postJson('/api/login', [
            'email' => 'testlogin@example.com',
            'password' => 'password123',
        ]);

        $response->assertStatus(200)
            ->assertJson([
                'success' => true,
                'message' => 'Login successful.',
            ])
            ->assertJsonStructure([
                'data' => [
                    'user',
                    'token',
                    'role',
                ],
            ]);
    }

    public function test_login_fails_with_invalid_password(): void
    {
        $user = User::create([
            'name' => 'Wrong Password User',
            'email' => 'wrongpass@example.com',
            'password' => Hash::make('correct123'),
            'role' => 'customer',
            'status' => 'active',
        ]);

        $response = $this->postJson('/api/login', [
            'email' => 'wrongpass@example.com',
            'password' => 'wrongpass',
        ]);

        $response->assertStatus(422)
            ->assertJson([
                'success' => false,
                'message' => 'Validation failed.',
            ])
            ->assertJsonValidationErrors(['email']);
    }

    public function test_inactive_user_cannot_login(): void
    {
        User::create([
            'name' => 'Deactivated User',
            'email' => 'deactivated@example.com',
            'password' => Hash::make('password123'),
            'role' => 'customer',
            'status' => 'inactive',
        ]);

        $response = $this->postJson('/api/login', [
            'email' => 'deactivated@example.com',
            'password' => 'password123',
        ]);

        $response->assertStatus(403)
            ->assertJson([
                'success' => false,
                'message' => 'Your account is currently inactive. Please contact administrator.',
            ]);
    }

    public function test_authenticated_user_can_access_me_endpoint(): void
    {
        $user = User::create([
            'name' => 'Me User',
            'email' => 'me@example.com',
            'password' => Hash::make('password123'),
            'role' => 'customer',
            'status' => 'active',
        ]);

        $token = $user->createToken('test_token')->plainTextToken;

        $response = $this->withHeader('Authorization', "Bearer {$token}")
            ->getJson('/api/me');

        $response->assertStatus(200)
            ->assertJson([
                'success' => true,
                'data' => [
                    'id' => $user->id,
                    'name' => 'Me User',
                    'email' => 'me@example.com',
                    'role' => 'customer',
                    'status' => 'active',
                ],
            ]);
    }

    public function test_authenticated_user_can_logout(): void
    {
        $user = User::create([
            'name' => 'Logout User',
            'email' => 'logout@example.com',
            'password' => Hash::make('password123'),
            'role' => 'customer',
            'status' => 'active',
        ]);

        $token = $user->createToken('test_token')->plainTextToken;

        $response = $this->withHeader('Authorization', "Bearer {$token}")
            ->postJson('/api/logout');

        $response->assertStatus(200)
            ->assertJson([
                'success' => true,
                'message' => 'Successfully logged out.',
            ]);

        $this->assertDatabaseCount('personal_access_tokens', 0);
    }
}
