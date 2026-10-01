/** Formatting shared by every screen that shows money or a date. */

const PRICE = new Intl.NumberFormat("vi-VN", {
  style: "currency",
  currency: "VND",
  maximumFractionDigits: 0,
});

// A date on this site is a Vietnamese date, as it is everywhere on the backend
// and on the certificate PDF. Left to the runtime, the same timestamp is a
// different day on the server (the container runs in UTC) than in the browser:
// a certificate issued at 00:12 on 01/10 in Hà Nội read "30/09" on its public
// page while the PDF it links to said "01/10".
const DATE = new Intl.DateTimeFormat("vi-VN", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  timeZone: "Asia/Ho_Chi_Minh",
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

/**
 * The same money, as an amount rather than as a price: zero stays "0 ₫".
 *
 * A price of zero is a fact about the course, so "Miễn phí" reads correctly
 * there. A *discount* of zero is not free anything -- it is what a percentage
 * off a free course comes to -- and a line saying "Giảm giá: Miễn phí" is
 * nonsense the reader has to decode.
 */
export function formatAmount(value: string): string {
  const amount = Number(value);
  if (Number.isNaN(amount)) return value;
  return PRICE.format(amount);
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

/**
 * A moment inside a video: "04:05", or "1:04:05" once it passes an hour.
 *
 * Different from `formatDuration` on purpose. That one answers "how long is
 * this course"; this one is a position on a timeline, and a timeline is read
 * as a clock.
 */
export function formatTimestamp(seconds: number): string {
  const whole = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(whole / 3600);
  const minutes = Math.floor((whole % 3600) / 60);
  const rest = whole % 60;

  const pad = (value: number) => String(value).padStart(2, "0");
  return hours > 0
    ? `${hours}:${pad(minutes)}:${pad(rest)}`
    : `${pad(minutes)}:${pad(rest)}`;
}

const RELATIVE = new Intl.RelativeTimeFormat("vi-VN", { numeric: "auto" });

/**
 * How long ago something happened: "vừa xong", "5 phút trước", "hôm qua".
 * Past a week it is a date again -- "32 ngày trước" makes the reader count.
 */
export function formatRelativeTime(iso: string, now: number = Date.now()): string {
  const seconds = Math.round((new Date(iso).getTime() - now) / 1000);
  const ago = -seconds;

  if (ago < 60) return "vừa xong";
  if (ago < 3600) return RELATIVE.format(Math.round(seconds / 60), "minute");
  if (ago < 86400) return RELATIVE.format(Math.round(seconds / 3600), "hour");
  if (ago < 7 * 86400) return RELATIVE.format(Math.round(seconds / 86400), "day");
  return formatDate(iso);
}
