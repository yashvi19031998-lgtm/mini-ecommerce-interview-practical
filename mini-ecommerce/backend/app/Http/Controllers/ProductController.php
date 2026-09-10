<?php

namespace App\Http\Controllers;

use App\Http\Resources\ProductResource;
use App\Models\Product;
use App\Traits\ApiResponse;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class ProductController extends Controller
{
    use ApiResponse;

    /**
     * Display a listing of active products for customers.
     */
    public function index(Request $request): JsonResponse
    {
        $query = Product::active()->with('category');

        if ($request->filled('search')) {
            $search = $request->search;
            $query->where(function ($q) use ($search) {
                $q->where('name', 'like', "%{$search}%")
                  ->orWhere('description', 'like', "%{$search}%");
            });
        }

        if ($request->filled('category_id')) {
            $query->where('category_id', $request->category_id);
        }

        if ($request->filled('sort')) {
            $sort = strtolower($request->sort);
            if ($sort === 'price_asc' || $sort === 'price_low') {
                $query->orderBy('price', 'asc');
            } elseif ($sort === 'price_desc' || $sort === 'price_high') {
                $query->orderBy('price', 'desc');
            } elseif ($sort === 'newest') {
                $query->latest();
            } else {
                $query->latest();
            }
        } else {
            $query->latest();
        }

        $perPage = min((int) $request->get('per_page', 12), 60);
        $products = $query->paginate($perPage);

        return $this->successResponse([
            'products' => ProductResource::collection($products),
            'pagination' => [
                'total' => $products->total(),
                'per_page' => $products->perPage(),
                'current_page' => $products->currentPage(),
                'last_page' => $products->lastPage(),
            ],
        ], 'Products retrieved successfully.');
    }

    /**
     * Display the specified active product.
     */
    public function show(int $id): JsonResponse
    {
        $product = Product::active()
            ->with('category')
            ->findOrFail($id);

        return $this->successResponse(
            new ProductResource($product),
            'Product retrieved successfully.'
        );
    }
}
