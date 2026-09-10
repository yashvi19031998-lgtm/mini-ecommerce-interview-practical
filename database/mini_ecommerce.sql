-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Host: 127.0.0.1
-- Generation Time: Sep 10, 2026 at 12:46 PM
-- Server version: 10.4.32-MariaDB
-- PHP Version: 8.1.25

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `mini_ecommerce`
--

-- --------------------------------------------------------

--
-- Table structure for table `carts`
--

CREATE TABLE `carts` (
  `id` bigint(20) UNSIGNED NOT NULL,
  `user_id` bigint(20) UNSIGNED NOT NULL,
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `carts`
--

INSERT INTO `carts` (`id`, `user_id`, `created_at`, `updated_at`) VALUES
(1, 4, '2026-09-10 02:52:10', '2026-09-10 02:52:10'),
(2, 8, '2026-09-10 03:45:27', '2026-09-10 03:45:27'),
(3, 10, '2026-09-10 04:57:26', '2026-09-10 04:57:26');

-- --------------------------------------------------------

--
-- Table structure for table `cart_items`
--

CREATE TABLE `cart_items` (
  `id` bigint(20) UNSIGNED NOT NULL,
  `cart_id` bigint(20) UNSIGNED NOT NULL,
  `product_id` bigint(20) UNSIGNED NOT NULL,
  `quantity` int(10) UNSIGNED NOT NULL DEFAULT 1,
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `cart_items`
--

INSERT INTO `cart_items` (`id`, `cart_id`, `product_id`, `quantity`, `created_at`, `updated_at`) VALUES
(1, 1, 5, 1, '2026-09-10 02:52:10', '2026-09-10 02:52:10');

-- --------------------------------------------------------

--
-- Table structure for table `categories`
--

CREATE TABLE `categories` (
  `id` bigint(20) UNSIGNED NOT NULL,
  `name` varchar(255) NOT NULL,
  `slug` varchar(255) NOT NULL,
  `description` text DEFAULT NULL,
  `status` enum('active','inactive') NOT NULL DEFAULT 'active',
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `categories`
--

INSERT INTO `categories` (`id`, `name`, `slug`, `description`, `status`, `created_at`, `updated_at`) VALUES
(1, 'Electronics', 'electronics', 'Gadgets, computers, smartphones, audio devices, and electronic accessories.', 'active', '2026-09-10 02:52:10', '2026-09-10 02:52:10'),
(2, 'Fashion & Apparel', 'fashion-apparel', 'Modern clothing, comfortable footwear, and trendsetting seasonal style.', 'active', '2026-09-10 02:52:10', '2026-09-10 02:52:10'),
(3, 'Home & Kitchen', 'home-kitchen', 'Premium cookware, home essentials, appliances, and decorative accents.', 'active', '2026-09-10 02:52:10', '2026-09-10 02:52:10'),
(4, 'Books & Stationery', 'books-stationery', 'Best-selling literature, tech guidebooks, and curated office stationery.', 'active', '2026-09-10 02:52:10', '2026-09-10 02:52:10'),
(5, 'Sports & Fitness', 'sports-fitness', 'Workout gear, training accessories, yoga equipment, and athletic essentials.', 'active', '2026-09-10 02:52:10', '2026-09-10 02:52:10');

-- --------------------------------------------------------

--
-- Table structure for table `failed_jobs`
--

CREATE TABLE `failed_jobs` (
  `id` bigint(20) UNSIGNED NOT NULL,
  `uuid` varchar(255) NOT NULL,
  `connection` text NOT NULL,
  `queue` text NOT NULL,
  `payload` longtext NOT NULL,
  `exception` longtext NOT NULL,
  `failed_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Table structure for table `migrations`
--

CREATE TABLE `migrations` (
  `id` int(10) UNSIGNED NOT NULL,
  `migration` varchar(255) NOT NULL,
  `batch` int(11) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `migrations`
--

INSERT INTO `migrations` (`id`, `migration`, `batch`) VALUES
(1, '2014_10_12_000000_create_users_table', 1),
(2, '2014_10_12_100000_create_password_reset_tokens_table', 1),
(3, '2019_08_19_000000_create_failed_jobs_table', 1),
(4, '2019_12_14_000001_create_personal_access_tokens_table', 1),
(5, '2026_09_10_000001_create_categories_table', 1),
(6, '2026_09_10_000002_create_products_table', 1),
(7, '2026_09_10_000003_create_carts_table', 1),
(8, '2026_09_10_000004_create_cart_items_table', 1),
(9, '2026_09_10_000005_create_orders_table', 1),
(10, '2026_09_10_000006_create_order_items_table', 1);

-- --------------------------------------------------------

--
-- Table structure for table `orders`
--

CREATE TABLE `orders` (
  `id` bigint(20) UNSIGNED NOT NULL,
  `user_id` bigint(20) UNSIGNED NOT NULL,
  `order_number` varchar(255) NOT NULL,
  `subtotal` decimal(10,2) UNSIGNED NOT NULL,
  `total` decimal(10,2) UNSIGNED NOT NULL,
  `status` enum('pending','confirmed','processing','shipped','delivered','cancelled') NOT NULL DEFAULT 'pending',
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `orders`
--

INSERT INTO `orders` (`id`, `user_id`, `order_number`, `subtotal`, `total`, `status`, `created_at`, `updated_at`) VALUES
(1, 2, 'ORD-FI2MOX-20260901', 229.97, 229.97, 'delivered', '2026-09-05 02:52:10', '2026-09-08 02:52:10'),
(2, 3, 'ORD-N6TZSR-20260909', 199.99, 199.99, 'pending', '2026-09-09 20:52:10', '2026-09-09 20:52:10'),
(3, 8, 'ORD-PCIWOQ-20260910102238', 149.99, 149.99, 'delivered', '2026-09-10 04:52:38', '2026-09-10 04:52:59'),
(4, 10, 'ORD-IPNHDO-20260910102758', 449.97, 449.97, 'delivered', '2026-09-10 04:57:58', '2026-09-10 04:59:50');

-- --------------------------------------------------------

--
-- Table structure for table `order_items`
--

CREATE TABLE `order_items` (
  `id` bigint(20) UNSIGNED NOT NULL,
  `order_id` bigint(20) UNSIGNED NOT NULL,
  `product_id` bigint(20) UNSIGNED DEFAULT NULL,
  `product_name` varchar(255) NOT NULL,
  `quantity` int(10) UNSIGNED NOT NULL,
  `price` decimal(10,2) UNSIGNED NOT NULL,
  `subtotal` decimal(10,2) UNSIGNED NOT NULL,
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `order_items`
--

INSERT INTO `order_items` (`id`, `order_id`, `product_id`, `product_name`, `quantity`, `price`, `subtotal`, `created_at`, `updated_at`) VALUES
(1, 1, 1, 'Wireless Noise-Canceling Headphones', 1, 149.99, 149.99, '2026-09-10 02:52:10', '2026-09-10 02:52:10'),
(2, 1, 4, 'Ergonomic Wireless Mouse', 2, 39.99, 79.98, '2026-09-10 02:52:10', '2026-09-10 02:52:10'),
(3, 2, 2, 'Smartwatch Series 8', 1, 199.99, 199.99, '2026-09-10 02:52:10', '2026-09-10 02:52:10'),
(4, 3, 1, 'Wireless Noise-Canceling Headphones', 1, 149.99, 149.99, '2026-09-10 04:52:38', '2026-09-10 04:52:38'),
(5, 4, 1, 'Wireless Noise-Canceling Headphones', 3, 149.99, 449.97, '2026-09-10 04:57:58', '2026-09-10 04:57:58');

-- --------------------------------------------------------

--
-- Table structure for table `password_reset_tokens`
--

CREATE TABLE `password_reset_tokens` (
  `email` varchar(255) NOT NULL,
  `token` varchar(255) NOT NULL,
  `created_at` timestamp NULL DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Table structure for table `personal_access_tokens`
--

CREATE TABLE `personal_access_tokens` (
  `id` bigint(20) UNSIGNED NOT NULL,
  `tokenable_type` varchar(255) NOT NULL,
  `tokenable_id` bigint(20) UNSIGNED NOT NULL,
  `name` varchar(255) NOT NULL,
  `token` varchar(64) NOT NULL,
  `abilities` text DEFAULT NULL,
  `last_used_at` timestamp NULL DEFAULT NULL,
  `expires_at` timestamp NULL DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Table structure for table `products`
--

CREATE TABLE `products` (
  `id` bigint(20) UNSIGNED NOT NULL,
  `category_id` bigint(20) UNSIGNED NOT NULL,
  `name` varchar(255) NOT NULL,
  `slug` varchar(255) NOT NULL,
  `description` text DEFAULT NULL,
  `price` decimal(10,2) UNSIGNED NOT NULL,
  `stock` int(10) UNSIGNED NOT NULL DEFAULT 0,
  `image` varchar(255) DEFAULT NULL,
  `status` enum('active','inactive') NOT NULL DEFAULT 'active',
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `products`
--

INSERT INTO `products` (`id`, `category_id`, `name`, `slug`, `description`, `price`, `stock`, `image`, `status`, `created_at`, `updated_at`) VALUES
(1, 1, 'Wireless Noise-Canceling Headphones', 'wireless-noise-canceling-headphones', 'Over-ear Bluetooth headphones with active noise cancellation, 30h battery life, and crystal-clear acoustic clarity.', 149.99, 21, 'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=600&auto=format&fit=crop', 'active', '2026-09-10 02:52:10', '2026-09-10 04:57:58'),
(2, 1, 'Smartwatch Series 8', 'smartwatch-series-8', 'Water-resistant health and fitness smartwatch with AMOLED display, heart-rate tracking, and GPS.', 199.99, 15, 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&auto=format&fit=crop', 'active', '2026-09-10 02:52:10', '2026-09-10 02:52:10'),
(3, 1, 'Ultra-Slim Mechanical Keyboard', 'ultra-slim-mechanical-keyboard', 'RGB backlit mechanical keyboard with hot-swappable switches and dual wireless connectivity.', 89.99, 40, 'https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=600&auto=format&fit=crop', 'active', '2026-09-10 02:52:10', '2026-09-10 02:52:10'),
(4, 1, 'Ergonomic Wireless Mouse', 'ergonomic-wireless-mouse', 'Precision optical mouse with silent clicks, customizable thumb buttons, and ergonomic hand support.', 39.99, 50, 'https://images.unsplash.com/photo-1615663245857-ac93bb7c39e7?w=600&auto=format&fit=crop', 'active', '2026-09-10 02:52:10', '2026-09-10 02:52:10'),
(5, 2, 'Classic Denim Jacket', 'classic-denim-jacket', 'Durable vintage washed blue denim jacket with button flap chest pockets and adjustable waist tabs.', 69.99, 30, 'https://images.unsplash.com/photo-1576995853123-5a10305d93c0?w=600&auto=format&fit=crop', 'active', '2026-09-10 02:52:10', '2026-09-10 02:52:10'),
(6, 2, 'Breathable Cotton Crewneck T-Shirt', 'breathable-cotton-crewneck-t-shirt', '100% combed organic ring-spun cotton t-shirt with pre-shrunk fabric and tailored casual fit.', 24.99, 100, 'https://images.unsplash.com/photo-1521572267360-ee0c2909d518?w=600&auto=format&fit=crop', 'active', '2026-09-10 02:52:10', '2026-09-10 02:52:10'),
(7, 2, 'Running Sneaker Pro', 'running-sneaker-pro', 'Lightweight athletic running shoes with responsive foam cushioning and breathable engineered mesh.', 119.50, 20, 'https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600&auto=format&fit=crop', 'active', '2026-09-10 02:52:10', '2026-09-10 02:52:10'),
(8, 3, 'Stainless Steel Espresso Maker', 'stainless-steel-espresso-maker', '15-bar Italian pump espresso and cappuccino maker with integrated manual milk frothing steam wand.', 129.00, 12, 'https://images.unsplash.com/photo-1517668808822-9ebb02f2a0e6?w=600&auto=format&fit=crop', 'active', '2026-09-10 02:52:10', '2026-09-10 02:52:10'),
(9, 3, 'Ceramic Non-Stick Frying Pan Set', 'ceramic-non-stick-frying-pan-set', 'Toxin-free mineral ceramic skillet set with stay-cool silicone handles and induction compatibility.', 79.99, 18, 'https://images.unsplash.com/photo-1584269600464-37b1b58a9fe7?w=600&auto=format&fit=crop', 'active', '2026-09-10 02:52:10', '2026-09-10 02:52:10'),
(10, 3, 'Smart HEPA Air Purifier', 'smart-hepa-air-purifier', 'True HEPA filtration capturing 99.97% of airborne particles with quiet sleep mode and air quality indicator.', 159.99, 10, 'https://images.unsplash.com/photo-1585771724684-38269d6639fd?w=600&auto=format&fit=crop', 'active', '2026-09-10 02:52:10', '2026-09-10 02:52:10'),
(11, 4, 'Clean Code: Handbook of Software Craftsmanship', 'clean-code-handbook', 'Essential guide to writing maintainable, readable, and robust software principles by Robert C. Martin.', 44.99, 35, 'https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?w=600&auto=format&fit=crop', 'active', '2026-09-10 02:52:10', '2026-09-10 02:52:10'),
(12, 4, 'Design Patterns: Elements of Reusable Software', 'design-patterns-elements', 'Classic architectural patterns reference catalog by the legendary Gang of Four (GoF).', 54.99, 22, 'https://images.unsplash.com/photo-1532012164546-f432f2e3777a?w=600&auto=format&fit=crop', 'active', '2026-09-10 02:52:10', '2026-09-10 02:52:10'),
(13, 4, 'Hardcover Dotted Bullet Journal', 'hardcover-dotted-bullet-journal', 'Faux leather A5 journal with 160gsm bleed-proof bamboo paper, dual bookmarks, and inner pocket.', 16.50, 60, 'https://images.unsplash.com/photo-1544816155-12df9643f363?w=600&auto=format&fit=crop', 'active', '2026-09-10 02:52:10', '2026-09-10 02:52:10'),
(14, 5, 'Adjustable Dumbbell Set (50 lbs)', 'adjustable-dumbbell-set-50-lbs', 'Rapid-change dial adjustable dumbbell pair replacing 10 individual weights for home gym workouts.', 189.99, 8, 'https://images.unsplash.com/photo-1583454110551-21f2fa2afe61?w=600&auto=format&fit=crop', 'active', '2026-09-10 02:52:10', '2026-09-10 02:52:10'),
(15, 5, 'Non-Slip Eco Yoga Mat', 'non-slip-eco-yoga-mat', '6mm dual-layer alignment line yoga mat made from biodegradable TPE material with carrying strap.', 29.99, 45, 'https://images.unsplash.com/photo-1601925260368-ae2f83cf8b7f?w=600&auto=format&fit=crop', 'active', '2026-09-10 02:52:10', '2026-09-10 02:52:10'),
(16, 5, 'Insulated Stainless Steel Water Bottle 1L', 'insulated-stainless-steel-water-bottle-1l', 'Double-walled vacuum insulated thermal flask keeping liquids cold for 24h or hot for 12h.', 22.50, 70, 'https://images.unsplash.com/photo-1602143407151-7111542de6e8?w=600&auto=format&fit=crop', 'active', '2026-09-10 02:52:10', '2026-09-10 02:52:10'),
(17, 2, 'yashvi', 'yashvi', 'asfasdasda', 500.00, 0, 'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=600&auto=format&fit=crop', 'active', '2026-09-10 04:51:36', '2026-09-10 04:51:36');

-- --------------------------------------------------------

--
-- Table structure for table `users`
--

CREATE TABLE `users` (
  `id` bigint(20) UNSIGNED NOT NULL,
  `name` varchar(255) NOT NULL,
  `email` varchar(255) NOT NULL,
  `email_verified_at` timestamp NULL DEFAULT NULL,
  `password` varchar(255) NOT NULL,
  `role` enum('admin','customer') NOT NULL DEFAULT 'customer',
  `status` enum('active','inactive') NOT NULL DEFAULT 'active',
  `remember_token` varchar(100) DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `users`
--

INSERT INTO `users` (`id`, `name`, `email`, `email_verified_at`, `password`, `role`, `status`, `remember_token`, `created_at`, `updated_at`) VALUES
(1, 'System Administrator', 'admin@example.com', NULL, '$2y$10$j0dZ8362A6iQibqpAtbVy.udWNU6OR8vJhj0ezWLHTFuDWsfRJ/lq', 'admin', 'active', NULL, '2026-09-10 02:52:10', '2026-09-10 02:52:10'),
(2, 'John Doe', 'customer1@example.com', NULL, '$2y$10$j0dZ8362A6iQibqpAtbVy.udWNU6OR8vJhj0ezWLHTFuDWsfRJ/lq', 'customer', 'active', NULL, '2026-09-10 02:52:10', '2026-09-10 02:52:10'),
(3, 'Jane Smith', 'customer2@example.com', NULL, '$2y$10$j0dZ8362A6iQibqpAtbVy.udWNU6OR8vJhj0ezWLHTFuDWsfRJ/lq', 'customer', 'active', NULL, '2026-09-10 02:52:10', '2026-09-10 02:52:10'),
(4, 'Alex Johnson', 'customer3@example.com', NULL, '$2y$10$j0dZ8362A6iQibqpAtbVy.udWNU6OR8vJhj0ezWLHTFuDWsfRJ/lq', 'customer', 'active', NULL, '2026-09-10 02:52:10', '2026-09-10 02:52:10'),
(5, 'Emily Davis', 'customer4@example.com', NULL, '$2y$10$j0dZ8362A6iQibqpAtbVy.udWNU6OR8vJhj0ezWLHTFuDWsfRJ/lq', 'customer', 'active', NULL, '2026-09-10 02:52:10', '2026-09-10 02:52:10'),
(6, 'Michael Brown', 'customer5@example.com', NULL, '$2y$10$j0dZ8362A6iQibqpAtbVy.udWNU6OR8vJhj0ezWLHTFuDWsfRJ/lq', 'customer', 'active', NULL, '2026-09-10 02:52:10', '2026-09-10 02:52:10'),
(7, 'Inactive User', 'inactive@example.com', NULL, '$2y$10$j0dZ8362A6iQibqpAtbVy.udWNU6OR8vJhj0ezWLHTFuDWsfRJ/lq', 'customer', 'inactive', NULL, '2026-09-10 02:52:10', '2026-09-10 02:52:10'),
(8, 'yashvi shah', 'yashvi19031998@gmail.com', NULL, '$2y$10$xx34kMFY/J8VPuUql5JeseJPvOUCL68jMMKN8/RubCSVRyff6w2Gm', 'customer', 'active', NULL, '2026-09-10 03:40:33', '2026-09-10 03:40:33'),
(10, 'kamal', 'lplp@yopmail.com', NULL, '$2y$10$zPgMhJqq6WoomAll4BwGBO1wOHRZtlaYhWQkTFZ4/jOypZVGLA3uq', 'customer', 'active', NULL, '2026-09-10 04:57:13', '2026-09-10 04:57:13');

--
-- Indexes for dumped tables
--

--
-- Indexes for table `carts`
--
ALTER TABLE `carts`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `carts_user_id_unique` (`user_id`);

--
-- Indexes for table `cart_items`
--
ALTER TABLE `cart_items`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `cart_items_cart_id_product_id_unique` (`cart_id`,`product_id`),
  ADD KEY `cart_items_product_id_foreign` (`product_id`);

--
-- Indexes for table `categories`
--
ALTER TABLE `categories`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `categories_slug_unique` (`slug`),
  ADD KEY `categories_status_index` (`status`);

--
-- Indexes for table `failed_jobs`
--
ALTER TABLE `failed_jobs`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `failed_jobs_uuid_unique` (`uuid`);

--
-- Indexes for table `migrations`
--
ALTER TABLE `migrations`
  ADD PRIMARY KEY (`id`);

--
-- Indexes for table `orders`
--
ALTER TABLE `orders`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `orders_order_number_unique` (`order_number`),
  ADD KEY `orders_user_id_index` (`user_id`),
  ADD KEY `orders_status_index` (`status`),
  ADD KEY `orders_created_at_index` (`created_at`);

--
-- Indexes for table `order_items`
--
ALTER TABLE `order_items`
  ADD PRIMARY KEY (`id`),
  ADD KEY `order_items_product_id_foreign` (`product_id`),
  ADD KEY `order_items_order_id_index` (`order_id`);

--
-- Indexes for table `password_reset_tokens`
--
ALTER TABLE `password_reset_tokens`
  ADD PRIMARY KEY (`email`);

--
-- Indexes for table `personal_access_tokens`
--
ALTER TABLE `personal_access_tokens`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `personal_access_tokens_token_unique` (`token`),
  ADD KEY `personal_access_tokens_tokenable_type_tokenable_id_index` (`tokenable_type`,`tokenable_id`);

--
-- Indexes for table `products`
--
ALTER TABLE `products`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `products_slug_unique` (`slug`),
  ADD KEY `products_category_id_index` (`category_id`),
  ADD KEY `products_status_index` (`status`),
  ADD KEY `products_price_index` (`price`);

--
-- Indexes for table `users`
--
ALTER TABLE `users`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `users_email_unique` (`email`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `carts`
--
ALTER TABLE `carts`
  MODIFY `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=4;

--
-- AUTO_INCREMENT for table `cart_items`
--
ALTER TABLE `cart_items`
  MODIFY `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=9;

--
-- AUTO_INCREMENT for table `categories`
--
ALTER TABLE `categories`
  MODIFY `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=6;

--
-- AUTO_INCREMENT for table `failed_jobs`
--
ALTER TABLE `failed_jobs`
  MODIFY `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `migrations`
--
ALTER TABLE `migrations`
  MODIFY `id` int(10) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=11;

--
-- AUTO_INCREMENT for table `orders`
--
ALTER TABLE `orders`
  MODIFY `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=5;

--
-- AUTO_INCREMENT for table `order_items`
--
ALTER TABLE `order_items`
  MODIFY `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=6;

--
-- AUTO_INCREMENT for table `personal_access_tokens`
--
ALTER TABLE `personal_access_tokens`
  MODIFY `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=12;

--
-- AUTO_INCREMENT for table `products`
--
ALTER TABLE `products`
  MODIFY `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=18;

--
-- AUTO_INCREMENT for table `users`
--
ALTER TABLE `users`
  MODIFY `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=11;

--
-- Constraints for dumped tables
--

--
-- Constraints for table `carts`
--
ALTER TABLE `carts`
  ADD CONSTRAINT `carts_user_id_foreign` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE;

--
-- Constraints for table `cart_items`
--
ALTER TABLE `cart_items`
  ADD CONSTRAINT `cart_items_cart_id_foreign` FOREIGN KEY (`cart_id`) REFERENCES `carts` (`id`) ON DELETE CASCADE,
  ADD CONSTRAINT `cart_items_product_id_foreign` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`) ON DELETE CASCADE;

--
-- Constraints for table `orders`
--
ALTER TABLE `orders`
  ADD CONSTRAINT `orders_user_id_foreign` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE;

--
-- Constraints for table `order_items`
--
ALTER TABLE `order_items`
  ADD CONSTRAINT `order_items_order_id_foreign` FOREIGN KEY (`order_id`) REFERENCES `orders` (`id`) ON DELETE CASCADE,
  ADD CONSTRAINT `order_items_product_id_foreign` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`) ON DELETE SET NULL;

--
-- Constraints for table `products`
--
ALTER TABLE `products`
  ADD CONSTRAINT `products_category_id_foreign` FOREIGN KEY (`category_id`) REFERENCES `categories` (`id`);
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
