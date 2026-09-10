<?php

namespace App\Http\Controllers\Admin;

use App\Http\Controllers\Controller;
use App\Http\Requests\Admin\StoreCategoryRequest;
use App\Http\Requests\Admin\UpdateCategoryRequest;
use App\Http\Resources\CategoryResource;
use App\Models\Category;
use App\Traits\ApiResponse;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Str;

class CategoryController extends Controller
{
    use ApiResponse;

    /**
     * Display a listing of all categories for admin.
     */
    public function index(Request $request): JsonResponse
    {
        $query = Category::withCount('products');

        if ($request->filled('search')) {
            $search = $request->search;
            $query->where('name', 'like', "%{$search}%")
                  ->orWhere('slug', 'like', "%{$search}%");
        }

        if ($request->filled('status')) {
            $query->where('status', $request->status);
        }

        $perPage = min((int) $request->get('per_page', 15), 100);
        $categories = $query->latest()->paginate($perPage);

        return $this->successResponse([
            'categories' => CategoryResource::collection($categories),
            'pagination' => [
                'total' => $categories->total(),
                'per_page' => $categories->perPage(),
                'current_page' => $categories->currentPage(),
                'last_page' => $categories->lastPage(),
            ],
        ], 'Categories retrieved successfully.');
    }

    /**
     * Store a newly created category.
     */
    public function store(StoreCategoryRequest $request): JsonResponse
    {
        $data = $request->validated();

        if (empty($data['slug'])) {
            $data['slug'] = Str::slug($data['name']);
        }

        if (empty($data['status'])) {
            $data['status'] = 'active';
        }

        $category = Category::create($data);

        return $this->successResponse(
            new CategoryResource($category),
            'Category created successfully.',
            201
        );
    }

    /**
     * Display the specified category.
     */
    public function show(mixed $category): JsonResponse
    {
        $model = $category instanceof Category ? $category->loadCount('products') : Category::withCount('products')->findOrFail($category);

        return $this->successResponse(
            new CategoryResource($model),
            'Category retrieved successfully.'
        );
    }

    /**
     * Update the specified category.
     */
    public function update(UpdateCategoryRequest $request, mixed $category): JsonResponse
    {
        $model = $category instanceof Category ? $category : Category::findOrFail($category);
        $data = $request->validated();

        if (isset($data['name']) && empty($data['slug'])) {
            $data['slug'] = Str::slug($data['name']);
        }

        $model->update($data);

        return $this->successResponse(
            new CategoryResource($model->fresh()->loadCount('products')),
            'Category updated successfully.'
        );
    }

    /**
     * Remove the specified category safely without breaking product relationships.
     */
    public function destroy(mixed $category): JsonResponse
    {
        $model = $category instanceof Category ? $category->loadCount('products') : Category::withCount('products')->findOrFail($category);

        if ($model->products_count > 0) {
            return $this->errorResponse(
                "Cannot delete category '{$model->name}' because it contains {$model->products_count} associated product(s). Please reassign or delete these products first.",
                422
            );
        }

        $model->delete();

        return $this->successResponse(null, 'Category deleted successfully.');
    }
}
