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

/**
 * A course length in words: "6 giờ 30 phút", "45 phút".
 *
 * Rounded to whole minutes because that is the precision anyone reads it at,
 * and returns null at zero so a course with no video yet can leave the line out
 * rather than claim it lasts nothing.
 */
export function formatDuration(seconds: number): string | null {
  const minutes = Math.round(seconds / 60);
  if (minutes <= 0) return null;

  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;

  if (hours === 0) return `${rest} phút`;
  return rest === 0 ? `${hours} giờ` : `${hours} giờ ${rest} phút`;
}
