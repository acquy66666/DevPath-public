import { apiFetch } from "./client";
import type { CourseCard, Page } from "./courses";

/**
 * The cart and the wishlist. Types mirror `backend/app/schemas/commerce.py`.
 *
 * Every cart call answers with the whole cart, so a mutation's result can be
 * written straight into the `["cart"]` query and the header badge, the total
 * and the button all move together. The wishlist is paged and answers 204
 * instead, so its mutations invalidate rather than replace.
 */

export interface CartItem {
  course: CourseCard;
  added_at: string;
  /** Owned since it went in. Drawn greyed out and left out of the total. */
  already_enrolled: boolean;
}

export interface Cart {
  items: CartItem[];
  /** VND as a string, like every other price — the column is NUMERIC. */
  total: string;
}

export interface WishlistItem {
  course: CourseCard;
  added_at: string;
}

export function getCart(accessToken: string): Promise<Cart> {
  return apiFetch<Cart>("/api/v1/cart", { accessToken });
}

/**
 * Put a course in the cart. Idempotent: adding what is already there answers
 * with the same cart rather than an error.
 *
 * Refusals arrive as `ApiError` with a code the page can speak to:
 * `ALREADY_ENROLLED`, `CANNOT_BUY_OWN_COURSE`, `CART_FULL`, `COURSE_NOT_FOUND`.
 */
export function addToCart(accessToken: string, courseId: string): Promise<Cart> {
  return apiFetch<Cart>(`/api/v1/cart/courses/${courseId}`, {
    method: "PUT",
    accessToken,
  });
}

export function removeFromCart(accessToken: string, courseId: string): Promise<Cart> {
  return apiFetch<Cart>(`/api/v1/cart/courses/${courseId}`, {
    method: "DELETE",
    accessToken,
  });
}

export function clearCart(accessToken: string): Promise<void> {
  return apiFetch<void>("/api/v1/cart", { method: "DELETE", accessToken });
}

export function listWishlist(
  accessToken: string,
  page = 1,
): Promise<Page<WishlistItem>> {
  return apiFetch<Page<WishlistItem>>(`/api/v1/wishlist?page=${page}`, {
    accessToken,
  });
}

export function addToWishlist(accessToken: string, courseId: string): Promise<void> {
  return apiFetch<void>(`/api/v1/wishlist/courses/${courseId}`, {
    method: "PUT",
    accessToken,
  });
}

export function removeFromWishlist(
  accessToken: string,
  courseId: string,
): Promise<void> {
  return apiFetch<void>(`/api/v1/wishlist/courses/${courseId}`, {
    method: "DELETE",
    accessToken,
  });
}

/**
 * Which courses the caller has saved. Unwrapped from its envelope here so the
 * components deal in a plain array of ids, which is what they compare against.
 */
export async function listWishlistedCourseIds(
  accessToken: string,
): Promise<string[]> {
  const body = await apiFetch<{ course_ids: string[] }>(
    "/api/v1/wishlist/course-ids",
    { accessToken },
  );
  return body.course_ids;
}
