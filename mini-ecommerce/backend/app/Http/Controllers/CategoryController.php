<?php

namespace App\Http\Controllers;

use App\Http\Resources\CategoryResource;
use App\Models\Category;
use App\Traits\ApiResponse;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class CategoryController extends Controller
{
    use ApiResponse;

    /**
     * Display a listing of active categories.
     */
    public function index(Request $request): JsonResponse
    {
        $categories = Category::active()
            ->withCount(['products' => function ($query) {
                $query->where('status', 'active');
            }])
            ->get();

        return $this->successResponse(
            CategoryResource::collection($categories),
            'Categories retrieved successfully.'
        );
    }

    /**
     * Display the specified active category.
     */
    public function show(int $id): JsonResponse
    {
        $category = Category::active()
            ->withCount(['products' => function ($query) {
                $query->where('status', 'active');
            }])
            ->findOrFail($id);

        return $this->successResponse(
            new CategoryResource($category),
            'Category retrieved successfully.'
        );
    }
}
