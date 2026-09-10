<?php

namespace Tests\Feature;

use App\Models\Category;
use App\Models\Product;
use App\Models\User;
use Illuminate\Foundation\Testing\DatabaseTransactions;
use Tests\TestCase;

class CategoryTest extends TestCase
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

    public function test_anyone_can_view_active_categories(): void
    {
        Category::create([
            'name' => 'Active Test Category',
            'slug' => 'active-test-category',
            'status' => 'active',
        ]);

        Category::create([
            'name' => 'Inactive Test Category',
            'slug' => 'inactive-test-category',
            'status' => 'inactive',
        ]);

        $response = $this->getJson('/api/categories');

        $response->assertStatus(200)
            ->assertJson(['success' => true]);

        $names = collect($response->json('data'))->pluck('name');
        $this->assertTrue($names->contains('Active Test Category'));
        $this->assertFalse($names->contains('Inactive Test Category'));
    }

    public function test_admin_can_list_all_categories_including_inactive(): void
    {
        Category::create([
            'name' => 'Admin Inactive Category',
            'slug' => 'admin-inactive-category',
            'status' => 'inactive',
        ]);

        $response = $this->actingAs($this->admin, 'sanctum')
            ->getJson('/api/admin/categories?search=Admin+Inactive');

        $response->assertStatus(200)
            ->assertJson(['success' => true]);

        $names = collect($response->json('data.categories'))->pluck('name');
        $this->assertTrue($names->contains('Admin Inactive Category'));
    }

    public function test_admin_can_create_category(): void
    {
        $response = $this->actingAs($this->admin, 'sanctum')
            ->postJson('/api/admin/categories', [
                'name' => 'Smart Home Appliances',
                'description' => 'Automated devices for home convenience.',
                'status' => 'active',
            ]);

        $response->assertStatus(201)
            ->assertJson([
                'success' => true,
                'data' => [
                    'name' => 'Smart Home Appliances',
                    'slug' => 'smart-home-appliances',
                ],
            ]);

        $this->assertDatabaseHas('categories', [
            'name' => 'Smart Home Appliances',
            'slug' => 'smart-home-appliances',
        ]);
    }

    public function test_admin_can_update_category(): void
    {
        $category = Category::create([
            'name' => 'Old Category Name',
            'slug' => 'old-category-name',
            'status' => 'active',
        ]);

        $response = $this->actingAs($this->admin, 'sanctum')
            ->putJson("/api/admin/categories/{$category->id}", [
                'name' => 'Updated Category Name',
                'status' => 'inactive',
            ]);

        $response->assertStatus(200)
            ->assertJson([
                'success' => true,
                'data' => [
                    'name' => 'Updated Category Name',
                    'status' => 'inactive',
                ],
            ]);

        $this->assertDatabaseHas('categories', [
            'id' => $category->id,
            'name' => 'Updated Category Name',
            'status' => 'inactive',
        ]);
    }

    public function test_admin_cannot_delete_category_with_associated_products(): void
    {
        $category = Category::create([
            'name' => 'Protected Category',
            'slug' => 'protected-category',
            'status' => 'active',
        ]);

        Product::create([
            'category_id' => $category->id,
            'name' => 'Child Product',
            'slug' => 'child-product',
            'price' => 19.99,
            'stock' => 5,
            'status' => 'active',
        ]);

        $response = $this->actingAs($this->admin, 'sanctum')
            ->deleteJson("/api/admin/categories/{$category->id}");

        $response->assertStatus(422)
            ->assertJson([
                'success' => false,
            ]);

        $this->assertDatabaseHas('categories', ['id' => $category->id]);
    }

    public function test_admin_can_delete_category_without_products(): void
    {
        $category = Category::create([
            'name' => 'Empty Category',
            'slug' => 'empty-category',
            'status' => 'active',
        ]);

        $response = $this->actingAs($this->admin, 'sanctum')
            ->deleteJson("/api/admin/categories/{$category->id}");

        $response->assertStatus(200)
            ->assertJson([
                'success' => true,
                'message' => 'Category deleted successfully.',
            ]);

        $this->assertDatabaseMissing('categories', ['id' => $category->id]);
    }
}
