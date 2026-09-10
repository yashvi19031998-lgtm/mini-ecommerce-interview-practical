<?php

namespace App\Policies;

use App\Models\Order;
use App\Models\User;

class OrderPolicy
{
    /**
     * Determine whether the user can view any models.
     */
    public function viewAny(User $user): bool
    {
        return $user->isActive();
    }

    /**
     * Determine whether the user can view the model.
     */
    public function view(User $user, Order $order): bool
    {
        if (!$user->isActive()) {
            return false;
        }

        return $user->isAdmin() || $user->id === $order->user_id;
    }

    /**
     * Determine whether the user can update the model (e.g. status).
     */
    public function update(User $user, Order $order): bool
    {
        return $user->isActive() && $user->isAdmin();
    }
}
