import type { Metadata } from "next";

import { WishlistView } from "@/components/commerce/wishlist-view";

export const metadata: Metadata = {
  title: "Yêu thích — DevPath",
  description: "Những khóa học bạn đã lưu lại trên DevPath.",
  robots: { index: false },
};

export default function WishlistPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="mb-6 text-3xl font-semibold tracking-tight">
        Danh sách yêu thích
      </h1>
      <WishlistView />
    </div>
  );
}
