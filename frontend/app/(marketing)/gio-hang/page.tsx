import type { Metadata } from "next";

import { CartView } from "@/components/commerce/cart-view";

export const metadata: Metadata = {
  title: "Giỏ hàng — DevPath",
  description: "Những khóa học bạn đang định mua trên DevPath.",
  // Nothing here belongs to anyone but the reader, and a crawler signed in as
  // nobody would only ever see the "đăng nhập" card.
  robots: { index: false },
};

export default function CartPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="mb-6 text-3xl font-semibold tracking-tight">Giỏ hàng</h1>
      <CartView />
    </div>
  );
}
