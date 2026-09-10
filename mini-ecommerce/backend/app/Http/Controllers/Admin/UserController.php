<?php

namespace App\Http\Controllers\Admin;

use App\Http\Controllers\Controller;
use App\Http\Requests\Admin\StoreUserRequest;
use App\Http\Requests\Admin\UpdateUserRequest;
use App\Http\Resources\UserResource;
use App\Models\User;
use App\Traits\ApiResponse;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class UserController extends Controller
{
    use ApiResponse;

    /**
     * Display a listing of users with search and filtering.
     */
    public function index(Request $request): JsonResponse
    {
        $query = User::query();

        if ($request->filled('search')) {
            $search = $request->search;
            $query->where(function ($q) use ($search) {
                $q->where('name', 'like', "%{$search}%")
                  ->orWhere('email', 'like', "%{$search}%");
            });
        }

        if ($request->filled('role')) {
            $query->where('role', $request->role);
        }

        if ($request->filled('status')) {
            $query->where('status', $request->status);
        }

        $perPage = min((int) $request->get('per_page', 15), 100);
        $users = $query->latest()->paginate($perPage);

        return $this->successResponse([
            'users' => UserResource::collection($users),
            'pagination' => [
                'total' => $users->total(),
                'per_page' => $users->perPage(),
                'current_page' => $users->currentPage(),
                'last_page' => $users->lastPage(),
            ],
        ], 'Users retrieved successfully.');
    }

    /**
     * Store a newly created user.
     */
    public function store(StoreUserRequest $request): JsonResponse
    {
        $data = $request->validated();

        $user = User::create([
            'name' => $data['name'],
            'email' => $data['email'],
            'password' => $data['password'],
            'role' => $data['role'],
            'status' => $data['status'],
        ]);

        return $this->successResponse(
            new UserResource($user),
            'User created successfully.',
            201
        );
    }

    /**
     * Display the specified user.
     */
    public function show(mixed $user): JsonResponse
    {
        $model = $user instanceof User ? $user : User::findOrFail($user);

        return $this->successResponse(
            new UserResource($model),
            'User retrieved successfully.'
        );
    }

    /**
     * Update the specified user.
     */
    public function update(UpdateUserRequest $request, mixed $user): JsonResponse
    {
        $model = $user instanceof User ? $user : User::findOrFail($user);
        $data = $request->validated();

        // Prevent self-demotion or self-deactivation if currently authenticated admin
        if ($model->id === $request->user()->id) {
            if (isset($data['role']) && $data['role'] !== 'admin') {
                return $this->errorResponse('You cannot demote your own administrator account.', 422);
            }
            if (isset($data['status']) && $data['status'] !== 'active') {
                return $this->errorResponse('You cannot deactivate your own administrator account.', 422);
            }
        }

        if (empty($data['password'])) {
            unset($data['password']);
        }

        $model->update($data);

        return $this->successResponse(
            new UserResource($model->fresh()),
            'User updated successfully.'
        );
    }

    /**
     * Remove the specified user.
     */
    public function destroy(Request $request, mixed $user): JsonResponse
    {
        $model = $user instanceof User ? $user : User::findOrFail($user);

        if ($model->id === $request->user()->id) {
            return $this->errorResponse('You cannot delete your own account.', 422);
        }

        // Prevent deleting the last admin
        if ($model->isAdmin()) {
            $adminCount = User::where('role', 'admin')->where('status', 'active')->count();
            if ($adminCount <= 1) {
                return $this->errorResponse('Cannot delete the sole active administrator account.', 422);
            }
        }

        $model->tokens()->delete();
        $model->delete();

        return $this->successResponse(null, 'User deleted successfully.');
    }
}
