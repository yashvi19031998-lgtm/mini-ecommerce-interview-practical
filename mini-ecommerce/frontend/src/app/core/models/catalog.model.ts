export interface Category {
  id: number;
  name: string;
  slug: string;
  description: string;
  status: 'active' | 'inactive';
  products_count?: number;
  created_at: string;
  updated_at: string;
}

export interface Product {
  id: number;
  category_id: number;
  name: string;
  slug: string;
  description: string;
  price: string | number;
  stock: number;
  image: string | null;
  status: 'active' | 'inactive';
  created_at: string;
  updated_at: string;
  category?: Category;
}

export interface PaginationMeta {
  total: number;
  per_page: number;
  current_page: number;
  last_page: number;
}

export interface PaginatedData<T, K extends string> {
  pagination: PaginationMeta;
}

// We use an intersection type trick so that if K is 'products', the key is 'products': T[]
export type PaginatedResponse<T, K extends string = 'data'> = {
  success: boolean;
  message: string;
  data: {
    [key in K]: T[];
  } & PaginationMeta; // Wait, pagination is nested inside data.
};

// Actually, simpler approach:
export interface PaginatedResponseRaw<T> {
  success: boolean;
  message: string;
  data: any; // We'll cast it where needed
}

export interface ProductPaginatedData {
  products: Product[];
  pagination: PaginationMeta;
}

export interface ProductPaginatedResponse {
  success: boolean;
  message: string;
  data: ProductPaginatedData;
}
