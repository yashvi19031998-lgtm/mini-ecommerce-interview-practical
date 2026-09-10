<?php

namespace App\Http\Controllers\Admin;

use App\Http\Controllers\Controller;
use App\Http\Requests\Admin\StoreProductRequest;
use App\Http\Requests\Admin\UpdateProductRequest;
use App\Http\Resources\ProductResource;
use App\Models\Product;
use App\Traits\ApiResponse;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Str;

class ProductController extends Controller
{
    use ApiResponse;

    /**
     * Display a listing of all products for admin.
     */
    public function index(Request $request): JsonResponse
    {
        $query = Product::with('category');

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

        if ($request->filled('status')) {
            $query->where('status', $request->status);
        }

        if ($request->filled('sort')) {
            $sort = strtolower($request->sort);
            if ($sort === 'price_asc') {
                $query->orderBy('price', 'asc');
            } elseif ($sort === 'price_desc') {
                $query->orderBy('price', 'desc');
            } elseif ($sort === 'stock_asc') {
                $query->orderBy('stock', 'asc');
            } else {
                $query->latest();
            }
        } else {
            $query->latest();
        }

        $perPage = min((int) $request->get('per_page', 15), 100);
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
     * Store a newly created product.
     */
    public function store(StoreProductRequest $request): JsonResponse
    {
        $data = $request->validated();

        if (empty($data['slug'])) {
            $data['slug'] = Str::slug($data['name']);
        }

        if (empty($data['status'])) {
            $data['status'] = 'active';
        }

        $product = Product::create($data);

        return $this->successResponse(
            new ProductResource($product->load('category')),
            'Product created successfully.',
            201
        );
    }

    /**
     * Display the specified product.
     */
    public function show(mixed $product): JsonResponse
    {
        $model = $product instanceof Product ? $product->load('category') : Product::with('category')->findOrFail($product);

        return $this->successResponse(
            new ProductResource($model),
            'Product retrieved successfully.'
        );
    }

    /**
     * Update the specified product.
     */
    public function update(UpdateProductRequest $request, mixed $product): JsonResponse
    {
        $model = $product instanceof Product ? $product : Product::findOrFail($product);
        $data = $request->validated();

        if (isset($data['name']) && empty($data['slug'])) {
            $data['slug'] = Str::slug($data['name']);
        }

        $model->update($data);

        return $this->successResponse(
            new ProductResource($model->fresh()->load('category')),
            'Product updated successfully.'
        );
    }

    /**
     * Remove the specified product.
     */
    public function destroy(mixed $product): JsonResponse
    {
        $model = $product instanceof Product ? $product : Product::findOrFail($product);
        $model->delete();

        return $this->successResponse(null, 'Product deleted successfully.');
    }
}
