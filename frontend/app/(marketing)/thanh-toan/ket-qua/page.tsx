import type { Metadata } from "next";

import { OrderResult } from "@/components/commerce/order-result";

export const metadata: Metadata = {
  title: "Kết quả thanh toán — DevPath",
  description: "Trạng thái đơn hàng của bạn trên DevPath.",
  // Somebody's receipt, reachable only with their own order code.
  robots: { index: false },
};

/**
 * Where VNPay sends the browser back after a payment.
 *
 * The redirect carries VNPay's whole answer in the query string, and all that
 * is taken from it is `vnp_TxnRef` — our own order code. Whether the order was
 * paid is asked of the API, which only learns that from VNPay's server-to-
 * server callback; believing the query string would mean anyone who can type
 * one is enrolled.
 *
 * `ma` is the same code, for links we build ourselves.
 */
export default async function PaymentResultPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const raw = params.vnp_TxnRef ?? params.ma;
  const code = Array.isArray(raw) ? raw[0] : (raw ?? null);

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      {/* The order's own heading says what happened; this names the page. */}
      <h1 className="sr-only">Kết quả thanh toán</h1>
      <OrderResult code={code} />
    </div>
  );
}
