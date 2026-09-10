import { Product } from './catalog.model';

export interface CartItem {
  id: number;
  cart_id: number;
  product_id: number;
  quantity: number;
  created_at: string;
  updated_at: string;
  product?: Product;
  subtotal?: number;
}

export interface Cart {
  id: number;
  user_id: number;
  created_at: string;
  updated_at: string;
  items: CartItem[];
  total?: number;
}

export interface CartResponse {
  success: boolean;
  message: string;
  data: Cart;
}
