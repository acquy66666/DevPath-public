import { apiFetch } from "./client";
import type { CourseCard } from "./courses";

/**
 * Orders and their payment. Types mirror `backend/app/schemas/orders.py`.
 *
 * The one thing worth knowing here: **`status` is read from our own API, never
 * from the query string VNPay redirects the browser back with.** That query
 * string says the same thing, but it arrives through a browser, and a browser
 * is something its owner can edit. The result page takes the order code out of
 * the redirect and asks the backend what actually happened.
 */

export interface OrderItem {
  course: CourseCard;
  /** What it cost on the day of the sale, which may differ from the card. */
  unit_price: string;
}

export type OrderStatus = "pending" | "paid" | "failed" | "cancelled";

export interface Order {
  code: string;
  status: OrderStatus;
  items: OrderItem[];
  subtotal: string;
  discount: string;
  total: string;
  coupon_code: string | null;
  payment_provider: string;
  provider_txn_id: string | null;
  /** VNPay's refusal code, e.g. "24" for a payment the person cancelled. */
  failure_code: string | null;
  paid_at: string | null;
  created_at: string;
}

/**
 * Turn the cart into an order. Sends a coupon code at most: the lines and the
 * total come from the cart on the server.
 *
 * Refusals arrive as `ApiError`, and they are the cart's and the coupon's own
 * -- `CART_EMPTY`, `COUPON_EXPIRED`, `COUPON_EXHAUSTED` and the rest -- because
 * this is the same set of rules, checked once more at the last moment.
 */
export function createOrder(
  accessToken: string,
  couponCode: string | null,
): Promise<Order> {
  return apiFetch<Order>("/api/v1/orders", {
    method: "POST",
    accessToken,
    body: JSON.stringify(couponCode ? { coupon_code: couponCode } : {}),
  });
}

export function getOrder(accessToken: string, code: string): Promise<Order> {
  return apiFetch<Order>(`/api/v1/orders/${code}`, { accessToken });
}

/**
 * A signed VNPay URL for a pending order, good for a few minutes.
 *
 * 503 `PAYMENT_NOT_CONFIGURED` on a server with no merchant credentials — the
 * order still exists, so the page says so rather than losing it.
 */
export async function createPaymentUrl(
  accessToken: string,
  code: string,
): Promise<string> {
  const body = await apiFetch<{ payment_url: string }>(
    `/api/v1/orders/${code}/payment-url`,
    { method: "POST", accessToken },
  );
  return body.payment_url;
}
