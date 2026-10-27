/**
 * The words around the cart: its headline, the pay button, and which saved
 * courses to offer beside it.
 *
 * Pure functions only, no runtime imports: `npm test` runs this on bare Node,
 * which cannot resolve an import without its extension, and the app build
 * will not take one with it.
 */

/** Same rule as `checkout.nothingToPay`: only exactly zero costs nothing. */
function nothingToPay(amount: string): boolean {
  const value = Number(amount);
  return !Number.isNaN(value) && value === 0;
}

interface Line {
  course: { id: string };
  already_enrolled: boolean;
}

/** "4 khóa học · 1 khóa bạn đã có không bị tính tiền". */
export function cartHeadline(items: readonly Line[]): string {
  const owned = items.filter((item) => item.already_enrolled).length;
  const head = `${items.length} khóa học`;
  if (owned === 0) return head;
  if (owned === items.length) return `${head} · bạn đều đã có, không có gì để trả`;
  return `${head} · ${owned} khóa bạn đã có không bị tính tiền`;
}

/** How many lines the total is made of. */
export function payableCount(items: readonly Line[]): number {
  return items.filter((item) => !item.already_enrolled).length;
}

/**
 * The pay button's words. The amount is on the button so the reader knows
 * what pressing it costs; `amountText` is that amount already formatted.
 */
export function payLabel(amountDue: string, amountText: string): string {
  return nothingToPay(amountDue) ? "Nhận khóa học" : `Thanh toán ${amountText} qua VNPay`;
}

/** The short line under the button: where the reader is about to go. */
export function payNote(amountDue: string): string {
  return nothingToPay(amountDue)
    ? "Đơn 0đ: khóa học vào tài khoản ngay, không qua trang thanh toán."
    : "Bạn trả tiền trên trang của VNPay. Khóa học vào tài khoản ngay khi ngân hàng xác nhận.";
}

/**
 * Saved courses not yet in the cart, newest saved first as the API sends
 * them, at most `limit`. Free courses are left out: they are enrolled in from
 * the course page, not bought. So are courses already owned: the wishlist
 * keeps a course after it is bought.
 */
export function wishlistPicks<T extends { course: { id: string; price: string } }>(
  wishlist: readonly T[],
  cart: readonly Line[],
  owned: ReadonlySet<string> = new Set(),
  limit = 2,
): T[] {
  const inCart = new Set(cart.map((line) => line.course.id));
  return wishlist
    .filter(
      (item) => !inCart.has(item.course.id) && !owned.has(item.course.id) && Number(item.course.price) > 0,
    )
    .slice(0, limit);
}
