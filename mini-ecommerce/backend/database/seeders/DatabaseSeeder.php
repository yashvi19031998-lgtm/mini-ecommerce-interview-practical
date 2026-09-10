<?php

namespace Database\Seeders;

use App\Models\Cart;
use App\Models\CartItem;
use App\Models\Category;
use App\Models\Order;
use App\Models\OrderItem;
use App\Models\Product;
use App\Models\User;
use Illuminate\Database\Seeder;
use Illuminate\Support\Facades\Hash;
use Illuminate\Support\Str;

class DatabaseSeeder extends Seeder
{
    /**
     * Seed the application's database.
     */
    public function run(): void
    {
        $defaultPassword = Hash::make('password123');

        // 1. Create Admin User
        $admin = User::create([
            'name' => 'System Administrator',
            'email' => 'admin@example.com',
            'password' => $defaultPassword,
            'role' => 'admin',
            'status' => 'active',
        ]);

        // 2. Create 5 Active Customers + 1 Inactive Customer
        $customer1 = User::create([
            'name' => 'John Doe',
            'email' => 'customer1@example.com',
            'password' => $defaultPassword,
            'role' => 'customer',
            'status' => 'active',
        ]);

        $customer2 = User::create([
            'name' => 'Jane Smith',
            'email' => 'customer2@example.com',
            'password' => $defaultPassword,
            'role' => 'customer',
            'status' => 'active',
        ]);

        $customer3 = User::create([
            'name' => 'Alex Johnson',
            'email' => 'customer3@example.com',
            'password' => $defaultPassword,
            'role' => 'customer',
            'status' => 'active',
        ]);

        $customer4 = User::create([
            'name' => 'Emily Davis',
            'email' => 'customer4@example.com',
            'password' => $defaultPassword,
            'role' => 'customer',
            'status' => 'active',
        ]);

        $customer5 = User::create([
            'name' => 'Michael Brown',
            'email' => 'customer5@example.com',
            'password' => $defaultPassword,
            'role' => 'customer',
            'status' => 'active',
        ]);

        User::create([
            'name' => 'Inactive User',
            'email' => 'inactive@example.com',
            'password' => $defaultPassword,
            'role' => 'customer',
            'status' => 'inactive',
        ]);

        // 3. Create 5 Categories
        $categoriesData = [
            [
                'name' => 'Electronics',
                'slug' => 'electronics',
                'description' => 'Gadgets, computers, smartphones, audio devices, and electronic accessories.',
                'status' => 'active',
            ],
            [
                'name' => 'Fashion & Apparel',
                'slug' => 'fashion-apparel',
                'description' => 'Modern clothing, comfortable footwear, and trendsetting seasonal style.',
                'status' => 'active',
            ],
            [
                'name' => 'Home & Kitchen',
                'slug' => 'home-kitchen',
                'description' => 'Premium cookware, home essentials, appliances, and decorative accents.',
                'status' => 'active',
            ],
            [
                'name' => 'Books & Stationery',
                'slug' => 'books-stationery',
                'description' => 'Best-selling literature, tech guidebooks, and curated office stationery.',
                'status' => 'active',
            ],
            [
                'name' => 'Sports & Fitness',
                'slug' => 'sports-fitness',
                'description' => 'Workout gear, training accessories, yoga equipment, and athletic essentials.',
                'status' => 'active',
            ],
        ];

        $categories = [];
        foreach ($categoriesData as $cat) {
            $categories[$cat['slug']] = Category::create($cat);
        }

        // 4. Create 16 Products across the 5 categories
        $productsData = [
            // Electronics
            [
                'category_id' => $categories['electronics']->id,
                'name' => 'Wireless Noise-Canceling Headphones',
                'slug' => 'wireless-noise-canceling-headphones',
                'description' => 'Over-ear Bluetooth headphones with active noise cancellation, 30h battery life, and crystal-clear acoustic clarity.',
                'price' => 149.99,
                'stock' => 25,
                'image' => 'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=600&auto=format&fit=crop',
                'status' => 'active',
            ],
            [
                'category_id' => $categories['electronics']->id,
                'name' => 'Smartwatch Series 8',
                'slug' => 'smartwatch-series-8',
                'description' => 'Water-resistant health and fitness smartwatch with AMOLED display, heart-rate tracking, and GPS.',
                'price' => 199.99,
                'stock' => 15,
                'image' => 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&auto=format&fit=crop',
                'status' => 'active',
            ],
            [
                'category_id' => $categories['electronics']->id,
                'name' => 'Ultra-Slim Mechanical Keyboard',
                'slug' => 'ultra-slim-mechanical-keyboard',
                'description' => 'RGB backlit mechanical keyboard with hot-swappable switches and dual wireless connectivity.',
                'price' => 89.99,
                'stock' => 40,
                'image' => 'https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=600&auto=format&fit=crop',
                'status' => 'active',
            ],
            [
                'category_id' => $categories['electronics']->id,
                'name' => 'Ergonomic Wireless Mouse',
                'slug' => 'ergonomic-wireless-mouse',
                'description' => 'Precision optical mouse with silent clicks, customizable thumb buttons, and ergonomic hand support.',
                'price' => 39.99,
                'stock' => 50,
                'image' => 'https://images.unsplash.com/photo-1615663245857-ac93bb7c39e7?w=600&auto=format&fit=crop',
                'status' => 'active',
            ],

            // Fashion & Apparel
            [
                'category_id' => $categories['fashion-apparel']->id,
                'name' => 'Classic Denim Jacket',
                'slug' => 'classic-denim-jacket',
                'description' => 'Durable vintage washed blue denim jacket with button flap chest pockets and adjustable waist tabs.',
                'price' => 69.99,
                'stock' => 30,
                'image' => 'https://images.unsplash.com/photo-1576995853123-5a10305d93c0?w=600&auto=format&fit=crop',
                'status' => 'active',
            ],
            [
                'category_id' => $categories['fashion-apparel']->id,
                'name' => 'Breathable Cotton Crewneck T-Shirt',
                'slug' => 'breathable-cotton-crewneck-t-shirt',
                'description' => '100% combed organic ring-spun cotton t-shirt with pre-shrunk fabric and tailored casual fit.',
                'price' => 24.99,
                'stock' => 100,
                'image' => 'https://images.unsplash.com/photo-1521572267360-ee0c2909d518?w=600&auto=format&fit=crop',
                'status' => 'active',
            ],
            [
                'category_id' => $categories['fashion-apparel']->id,
                'name' => 'Running Sneaker Pro',
                'slug' => 'running-sneaker-pro',
                'description' => 'Lightweight athletic running shoes with responsive foam cushioning and breathable engineered mesh.',
                'price' => 119.50,
                'stock' => 20,
                'image' => 'https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600&auto=format&fit=crop',
                'status' => 'active',
            ],

            // Home & Kitchen
            [
                'category_id' => $categories['home-kitchen']->id,
                'name' => 'Stainless Steel Espresso Maker',
                'slug' => 'stainless-steel-espresso-maker',
                'description' => '15-bar Italian pump espresso and cappuccino maker with integrated manual milk frothing steam wand.',
                'price' => 129.00,
                'stock' => 12,
                'image' => 'https://images.unsplash.com/photo-1517668808822-9ebb02f2a0e6?w=600&auto=format&fit=crop',
                'status' => 'active',
            ],
            [
                'category_id' => $categories['home-kitchen']->id,
                'name' => 'Ceramic Non-Stick Frying Pan Set',
                'slug' => 'ceramic-non-stick-frying-pan-set',
                'description' => 'Toxin-free mineral ceramic skillet set with stay-cool silicone handles and induction compatibility.',
                'price' => 79.99,
                'stock' => 18,
                'image' => 'https://images.unsplash.com/photo-1584269600464-37b1b58a9fe7?w=600&auto=format&fit=crop',
                'status' => 'active',
            ],
            [
                'category_id' => $categories['home-kitchen']->id,
                'name' => 'Smart HEPA Air Purifier',
                'slug' => 'smart-hepa-air-purifier',
                'description' => 'True HEPA filtration capturing 99.97% of airborne particles with quiet sleep mode and air quality indicator.',
                'price' => 159.99,
                'stock' => 10,
                'image' => 'https://images.unsplash.com/photo-1585771724684-38269d6639fd?w=600&auto=format&fit=crop',
                'status' => 'active',
            ],

            // Books & Stationery
            [
                'category_id' => $categories['books-stationery']->id,
                'name' => 'Clean Code: Handbook of Software Craftsmanship',
                'slug' => 'clean-code-handbook',
                'description' => 'Essential guide to writing maintainable, readable, and robust software principles by Robert C. Martin.',
                'price' => 44.99,
                'stock' => 35,
                'image' => 'https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?w=600&auto=format&fit=crop',
                'status' => 'active',
            ],
            [
                'category_id' => $categories['books-stationery']->id,
                'name' => 'Design Patterns: Elements of Reusable Software',
                'slug' => 'design-patterns-elements',
                'description' => 'Classic architectural patterns reference catalog by the legendary Gang of Four (GoF).',
                'price' => 54.99,
                'stock' => 22,
                'image' => 'https://images.unsplash.com/photo-1532012164546-f432f2e3777a?w=600&auto=format&fit=crop',
                'status' => 'active',
            ],
            [
                'category_id' => $categories['books-stationery']->id,
                'name' => 'Hardcover Dotted Bullet Journal',
                'slug' => 'hardcover-dotted-bullet-journal',
                'description' => 'Faux leather A5 journal with 160gsm bleed-proof bamboo paper, dual bookmarks, and inner pocket.',
                'price' => 16.50,
                'stock' => 60,
                'image' => 'https://images.unsplash.com/photo-1544816155-12df9643f363?w=600&auto=format&fit=crop',
                'status' => 'active',
            ],

            // Sports & Fitness
            [
                'category_id' => $categories['sports-fitness']->id,
                'name' => 'Adjustable Dumbbell Set (50 lbs)',
                'slug' => 'adjustable-dumbbell-set-50-lbs',
                'description' => 'Rapid-change dial adjustable dumbbell pair replacing 10 individual weights for home gym workouts.',
                'price' => 189.99,
                'stock' => 8,
                'image' => 'https://images.unsplash.com/photo-1583454110551-21f2fa2afe61?w=600&auto=format&fit=crop',
                'status' => 'active',
            ],
            [
                'category_id' => $categories['sports-fitness']->id,
                'name' => 'Non-Slip Eco Yoga Mat',
                'slug' => 'non-slip-eco-yoga-mat',
                'description' => '6mm dual-layer alignment line yoga mat made from biodegradable TPE material with carrying strap.',
                'price' => 29.99,
                'stock' => 45,
                'image' => 'https://images.unsplash.com/photo-1601925260368-ae2f83cf8b7f?w=600&auto=format&fit=crop',
                'status' => 'active',
            ],
            [
                'category_id' => $categories['sports-fitness']->id,
                'name' => 'Insulated Stainless Steel Water Bottle 1L',
                'slug' => 'insulated-stainless-steel-water-bottle-1l',
                'description' => 'Double-walled vacuum insulated thermal flask keeping liquids cold for 24h or hot for 12h.',
                'price' => 22.50,
                'stock' => 70,
                'image' => 'https://images.unsplash.com/photo-1602143407151-7111542de6e8?w=600&auto=format&fit=crop',
                'status' => 'active',
            ],
        ];

        $createdProducts = [];
        foreach ($productsData as $prod) {
            $createdProducts[] = Product::create($prod);
        }

        // 5. Create Sample Orders for Demonstration
        // Order 1: Delivered order for Customer 1
        $order1Product1 = $createdProducts[0]; // Headphones (149.99)
        $order1Product2 = $createdProducts[3]; // Mouse (39.99)
        $item1Subtotal = round(1 * $order1Product1->price, 2);
        $item2Subtotal = round(2 * $order1Product2->price, 2);
        $order1Total = round($item1Subtotal + $item2Subtotal, 2);

        $order1 = Order::create([
            'user_id' => $customer1->id,
            'order_number' => 'ORD-' . strtoupper(Str::random(6)) . '-20260901',
            'subtotal' => $order1Total,
            'total' => $order1Total,
            'status' => Order::STATUS_DELIVERED,
            'created_at' => now()->subDays(5),
            'updated_at' => now()->subDays(2),
        ]);

        OrderItem::create([
            'order_id' => $order1->id,
            'product_id' => $order1Product1->id,
            'product_name' => $order1Product1->name,
            'quantity' => 1,
            'price' => $order1Product1->price,
            'subtotal' => $item1Subtotal,
        ]);

        OrderItem::create([
            'order_id' => $order1->id,
            'product_id' => $order1Product2->id,
            'product_name' => $order1Product2->name,
            'quantity' => 2,
            'price' => $order1Product2->price,
            'subtotal' => $item2Subtotal,
        ]);

        // Order 2: Pending order for Customer 2
        $order2Product = $createdProducts[1]; // Smartwatch (199.99)
        $order2 = Order::create([
            'user_id' => $customer2->id,
            'order_number' => 'ORD-' . strtoupper(Str::random(6)) . '-20260909',
            'subtotal' => $order2Product->price,
            'total' => $order2Product->price,
            'status' => Order::STATUS_PENDING,
            'created_at' => now()->subHours(6),
            'updated_at' => now()->subHours(6),
        ]);

        OrderItem::create([
            'order_id' => $order2->id,
            'product_id' => $order2Product->id,
            'product_name' => $order2Product->name,
            'quantity' => 1,
            'price' => $order2Product->price,
            'subtotal' => $order2Product->price,
        ]);

        // 6. Create active Cart for Customer 3 with 1 item
        $cart3 = Cart::create(['user_id' => $customer3->id]);
        CartItem::create([
            'cart_id' => $cart3->id,
            'product_id' => $createdProducts[4]->id, // Denim jacket
            'quantity' => 1,
        ]);
    }
}
