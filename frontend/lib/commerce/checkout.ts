/**
 * Where checking out leads, decided from the order the API just wrote.
 *
 * An order of 0 đ — a 100 % code, or a free course checked out through the
 * cart — comes back already `paid`: there is nothing to charge, and VNPay
 * cannot be asked for 0 đ. It goes to our own result page. Every other order
 * is still waiting for money and goes to the gateway.
 *
 * No imports, so `node --test` can run it as it is.
 */

interface OrderOutcome {
  code: string;
  status: string;
}

/** The result page for an order that needs no payment, or null. */
export function settledOrderPath(order: OrderOutcome): string | null {
  return order.status === "paid"
    ? `/thanh-toan/ket-qua?ma=${encodeURIComponent(order.code)}`
    : null;
}

/**
 * Whether checking out will cost nothing, so the button can say what it is
 * going to do. The server decides either way; this only picks the words.
 */
export function nothingToPay(amount: string): boolean {
  const value = Number(amount);
  return !Number.isNaN(value) && value === 0;
}
