/**
 * What the payment result page says about an order, and when Naomi reacts.
 *
 * Pure functions only, type imports only: `npm test` runs this on bare Node.
 */
import type { Mood } from "@/lib/mascot/moods";

export type OrderState = "paid" | "pending" | "failed" | "cancelled";

/** VNPay's refusal codes, in words. Anything else gets the general sentence. */
export const REFUSALS: Record<string, string> = {
  "07": "Giao dịch bị nghi ngờ gian lận nên ngân hàng đã giữ lại.",
  "09": "Thẻ chưa đăng ký dịch vụ InternetBanking.",
  "10": "Xác thực thông tin thẻ sai quá 3 lần.",
  "11": "Đã hết hạn chờ thanh toán.",
  "12": "Thẻ hoặc tài khoản đang bị khóa.",
  "24": "Bạn đã hủy giao dịch trên trang của VNPay.",
  "51": "Tài khoản không đủ số dư.",
  "65": "Tài khoản đã vượt hạn mức giao dịch trong ngày.",
  "75": "Ngân hàng đang bảo trì.",
  "79": "Sai mật khẩu thanh toán quá số lần cho phép.",
};

export type OrderTone = "success" | "warning" | "destructive" | "muted";

export interface OrderHeadline {
  tone: OrderTone;
  /** Naomi beside the heading, or none (waiting is not something that happened). */
  mood: Extract<Mood, "paid" | "oops"> | null;
  eyebrow: string;
  title: string;
  /** What happened, in one sentence. */
  description: string;
  /** What it means for the reader's money and cart, when that needs saying. */
  reassurance: string | null;
}

interface OrderFacts {
  status: OrderState;
  /** A 0 đ order: settled at checkout, never at a gateway. */
  free: boolean;
  itemCount: number;
  failureCode: string | null;
  /** Still polling for the gateway's callback (pending only). */
  waiting: boolean;
}

function courses(count: number): string {
  return count === 1 ? "Khóa học" : `${count} khóa học`;
}

export function orderHeadline(order: OrderFacts): OrderHeadline {
  switch (order.status) {
    case "paid":
      return order.free
        ? {
            tone: "success",
            mood: "paid",
            eyebrow: "Đã nhận",
            title: "Đã nhận khóa học",
            description: `Đơn 0đ nên không cần thanh toán. ${courses(order.itemCount)} đã vào tài khoản của bạn.`,
            reassurance: null,
          }
        : {
            tone: "success",
            mood: "paid",
            eyebrow: "Đã thanh toán",
            title: "Thanh toán thành công",
            description: `${courses(order.itemCount)} đã vào tài khoản của bạn. Học được ngay, trên mọi thiết bị.`,
            reassurance: null,
          };
    case "pending":
      return order.waiting
        ? {
            tone: "warning",
            mood: null,
            eyebrow: "Đang chờ",
            title: "Đang chờ ngân hàng xác nhận",
            description: "Thường mất vài giây. Trang này tự cập nhật, bạn không cần tải lại.",
            reassurance: null,
          }
        : {
            tone: "warning",
            mood: null,
            eyebrow: "Đang chờ",
            title: "Ngân hàng chưa báo kết quả",
            description:
              "Nếu tiền đã bị trừ, khóa học sẽ vào tài khoản ngay khi VNPay báo về — bạn không cần trả lại lần nữa.",
            reassurance: null,
          };
    case "failed":
      return {
        tone: "destructive",
        mood: "oops",
        eyebrow: "Chưa thanh toán",
        title: "Thanh toán không thành công",
        description:
          (order.failureCode && REFUSALS[order.failureCode]) ||
          "Giao dịch không hoàn tất trên trang của VNPay.",
        reassurance: "Chưa có khoản nào bị trừ, và giỏ hàng của bạn vẫn còn nguyên.",
      };
    case "cancelled":
      return {
        tone: "muted",
        mood: "oops",
        eyebrow: "Đã hủy",
        title: "Đơn hàng đã hủy",
        description: "Đơn này không còn được thanh toán nữa.",
        reassurance: "Giỏ hàng của bạn vẫn còn nguyên.",
      };
  }
}

/** How long after the order was placed its outcome still counts as news. */
export const FRESH_FOR_MS = 60 * 60 * 1000;

/** Per order: the status this browser last reacted to. */
export function orderSeenKey(code: string): string {
  return `devpath:order-seen:${code}`;
}

/**
 * Whether Naomi should react, given what this browser last reacted to.
 *
 * She reacts to a payment that just went through or just failed: once, the
 * first time this browser sees that outcome, and only while the order is
 * fresh. A receipt opened next week from a bookmark -- or a reload -- is
 * shown with her standing still.
 */
export function shouldReact(
  status: OrderState,
  seenStatus: string | null,
  createdAt: string,
  now: number,
): boolean {
  if (status !== "paid" && status !== "failed") return false;
  if (seenStatus === status) return false;
  const age = now - new Date(createdAt).getTime();
  return Number.isFinite(age) && age >= 0 && age <= FRESH_FOR_MS;
}
