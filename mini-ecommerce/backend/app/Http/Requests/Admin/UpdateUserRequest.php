<?php

namespace App\Http\Requests\Admin;

use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

class UpdateUserRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        $userParam = $this->route('user') ?? $this->route('id');
        $userId = is_object($userParam) ? $userParam->id : $userParam;

        return [
            'name' => ['sometimes', 'required', 'string', 'max:255'],
            'email' => [
                'sometimes',
                'required',
                'string',
                'email',
                'max:255',
                Rule::unique('users', 'email')->ignore($userId),
            ],
            'password' => ['nullable', 'string', 'min:6'],
            'role' => ['sometimes', 'required', 'in:admin,customer'],
            'status' => ['sometimes', 'required', 'in:active,inactive'],
        ];
    }
}
