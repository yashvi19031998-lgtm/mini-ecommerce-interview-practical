<?php

namespace Tests\Feature;

use App\Models\Category;
use App\Models\Product;
use App\Models\User;
use Illuminate\Foundation\Testing\DatabaseTransactions;
use Tests\TestCase;

class ProductTest extends TestCase
{
    use DatabaseTransactions;

    protected User $admin;
    protected User $customer;
    protected Category $category;

    protected function setUp(): void
    {
        parent::setUp();

        $this->admin = User::factory()->admin()->create();
        $this->customer = User::factory()->create();
        $this->category = Category::create([
            'name' => 'Test Tech Category',
            'slug' => 'test-tech-category',
            'status' => 'active',
        ]);
    }

    public function test_customer_can_browse_active_products(): void
    {
        $activeProduct = Product::create([
            'category_id' => $this->category->id,
            'name' => 'Active Gadget',
            'slug' => 'active-gadget',
            'price' => 49.99,
            'stock' => 10,
            'status' => 'active',
        ]);

        $inactiveProduct = Product::create([
            'category_id' => $this->category->id,
            'name' => 'Inactive Gadget',
            'slug' => 'inactive-gadget',
            'price' => 59.99,
            'stock' => 5,
            'status' => 'inactive',
        ]);

        $response = $this->getJson('/api/products');

        $response->assertStatus(200);
        $names = collect($response->json('data.products'))->pluck('name');
        $this->assertTrue($names->contains('Active Gadget'));
        $this->assertFalse($names->contains('Inactive Gadget'));
    }

    public function test_customer_can_search_and_filter_products_by_category(): void
    {
        $otherCategory = Category::create([
            'name' => 'Other Category',
            'slug' => 'other-category',
            'status' => 'active',
        ]);

        Product::create([
            'category_id' => $this->category->id,
            'name' => 'Gaming Laptop Ultra',
            'slug' => 'gaming-laptop-ultra',
            'price' => 1200.00,
            'stock' => 5,
            'status' => 'active',
        ]);

        Product::create([
            'category_id' => $otherCategory->id,
            'name' => 'Cotton Hoodie',
            'slug' => 'cotton-hoodie',
            'price' => 45.00,
            'stock' => 15,
            'status' => 'active',
        ]);

        $response = $this->getJson("/api/products?search=Gaming&category_id={$this->category->id}");

        $response->assertStatus(200);
        $products = collect($response->json('data.products'));
        $this->assertCount(1, $products);
        $this->assertEquals('Gaming Laptop Ultra', $products->first()['name']);
    }

    public function test_customer_can_sort_products_by_price(): void
    {
        Product::create([
            'category_id' => $this->category->id,
            'name' => 'Cheapest Item',
            'slug' => 'cheapest-item',
            'price' => 10.00,
            'stock' => 5,
            'status' => 'active',
        ]);

        Product::create([
            'category_id' => $this->category->id,
            'name' => 'Expensive Item',
            'slug' => 'expensive-item',
            'price' => 999.00,
            'stock' => 5,
            'status' => 'active',
        ]);

        $responseAsc = $this->getJson('/api/products?sort=price_asc');
        $responseAsc->assertStatus(200);
        $firstItemAsc = $responseAsc->json('data.products.0');
        $this->assertEquals(10.00, $firstItemAsc['price']);

        $responseDesc = $this->getJson('/api/products?sort=price_desc');
        $responseDesc->assertStatus(200);
        $firstItemDesc = $responseDesc->json('data.products.0');
        $this->assertEquals(999.00, $firstItemDesc['price']);
    }

    public function test_admin_can_create_product(): void
    {
        $payload = [
            'category_id' => $this->category->id,
            'name' => 'Pro Wireless Earbuds',
            'description' => 'Hi-fi sound with low latency.',
            'price' => 79.99,
            'stock' => 30,
            'status' => 'active',
        ];

        $response = $this->actingAs($this->admin, 'sanctum')
            ->postJson('/api/admin/products', $payload);

        $response->assertStatus(201)
            ->assertJson([
                'success' => true,
                'data' => [
                    'name' => 'Pro Wireless Earbuds',
                    'slug' => 'pro-wireless-earbuds',
                    'price' => 79.99,
                    'stock' => 30,
                ],
            ]);

        $this->assertDatabaseHas('products', [
            'name' => 'Pro Wireless Earbuds',
            'stock' => 30,
        ]);
    }

    public function test_product_creation_rejects_negative_price_and_stock(): void
    {
        $response = $this->actingAs($this->admin, 'sanctum')
            ->postJson('/api/admin/products', [
                'category_id' => $this->category->id,
                'name' => 'Invalid Product',
                'price' => -10.00,
                'stock' => -5,
            ]);

        $response->assertStatus(422)
            ->assertJsonValidationErrors(['price', 'stock']);
    }

    public function test_admin_can_update_product(): void
    {
        $product = Product::create([
            'category_id' => $this->category->id,
            'name' => 'Original Name',
            'slug' => 'original-name',
            'price' => 50.00,
            'stock' => 10,
            'status' => 'active',
        ]);

        $response = $this->actingAs($this->admin, 'sanctum')
            ->putJson("/api/admin/products/{$product->id}", [
                'price' => 45.00,
                'stock' => 20,
            ]);

        $response->assertStatus(200)
            ->assertJson([
                'success' => true,
                'data' => [
                    'price' => 45.00,
                    'stock' => 20,
                ],
            ]);

        $this->assertDatabaseHas('products', [
            'id' => $product->id,
            'price' => 45.00,
            'stock' => 20,
        ]);
    }

    public function test_admin_can_delete_product(): void
    {
        $product = Product::create([
            'category_id' => $this->category->id,
            'name' => 'Disposable Product',
            'slug' => 'disposable-product',
            'price' => 15.00,
            'stock' => 2,
            'status' => 'active',
        ]);

        $response = $this->actingAs($this->admin, 'sanctum')
            ->deleteJson("/api/admin/products/{$product->id}");

        $response->assertStatus(200)
            ->assertJson([
                'success' => true,
                'message' => 'Product deleted successfully.',
            ]);

        $this->assertDatabaseMissing('products', ['id' => $product->id]);
    }
}
