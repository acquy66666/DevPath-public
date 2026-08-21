/** Formatting shared by every screen that shows money or a date. */

const PRICE = new Intl.NumberFormat("vi-VN", {
  style: "currency",
  currency: "VND",
  maximumFractionDigits: 0,
});

const DATE = new Intl.DateTimeFormat("vi-VN", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
});

/**
 * `price` arrives as a string because the column is NUMERIC. Formatting is the
 * one place it may become a number: the value is at most a few million đồng, so
 * nothing is lost, and it never travels back to the server this way.
 */
export function formatPrice(price: string): string {
  const amount = Number(price);
  if (Number.isNaN(amount)) return price;
  return amount === 0 ? "Miễn phí" : PRICE.format(amount);
}

export function formatDate(iso: string): string {
  return DATE.format(new Date(iso));
}
