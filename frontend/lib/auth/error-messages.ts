import { ApiError } from "@/lib/api/client";

/**
 * Turn a failed auth call into one sentence a person can act on.
 *
 * Keyed by the backend's `code`, never by its message: the message is written
 * for the log, and switching on prose breaks the moment someone rewords it.
 */
const MESSAGES: Record<string, string> = {
  EMAIL_ALREADY_REGISTERED: "Email này đã có tài khoản. Bạn đăng nhập nhé?",
  INVALID_CREDENTIALS: "Email hoặc mật khẩu không đúng.",
  ACCOUNT_LOCKED: "Tài khoản đã bị khóa. Liên hệ quản trị viên để mở lại.",
  VALIDATION_ERROR: "Thông tin chưa hợp lệ, vui lòng kiểm tra lại các ô bên trên.",
  REFRESH_TOKEN_MISSING: "Phiên đăng nhập đã kết thúc, vui lòng đăng nhập lại.",
  INVALID_REFRESH_TOKEN: "Phiên đăng nhập đã hết hạn, vui lòng đăng nhập lại.",
  REFRESH_TOKEN_REUSED:
    "Phiên đăng nhập đã bị thu hồi vì lý do an toàn. Vui lòng đăng nhập lại.",
  NOT_AUTHENTICATED: "Bạn cần đăng nhập để tiếp tục.",
};

const NETWORK_FAILURE = "Không kết nối được máy chủ. Kiểm tra mạng rồi thử lại.";
const UNKNOWN_FAILURE = "Có lỗi xảy ra, vui lòng thử lại.";

export function authErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return MESSAGES[error.code] ?? error.message ?? UNKNOWN_FAILURE;
  }

  // fetch() rejects with a TypeError when the backend is unreachable, which is
  // the most common failure while developing.
  if (error instanceof TypeError) return NETWORK_FAILURE;

  return UNKNOWN_FAILURE;
}
