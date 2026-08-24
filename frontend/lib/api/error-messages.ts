import { ApiError } from "@/lib/api/client";

/**
 * Turn a failed API call into one sentence a person can act on.
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

  // Đăng nhập Google — backend chuyển hướng về /dang-nhap?loi=<code>.
  GOOGLE_ACCESS_DENIED: "Bạn đã hủy đăng nhập bằng Google.",
  GOOGLE_STATE_INVALID:
    "Phiên đăng nhập Google không hợp lệ hoặc đã quá hạn. Bấm đăng nhập lại giúp mình nhé.",
  GOOGLE_AUTH_FAILED: "Không đăng nhập được bằng Google. Thử lại sau ít phút.",
  GOOGLE_EMAIL_NOT_VERIFIED:
    "Google chưa xác thực email của tài khoản này nên không dùng để đăng nhập được.",
  GOOGLE_ACCOUNT_CONFLICT:
    "Email này đã liên kết với một tài khoản Google khác. Dùng mật khẩu để đăng nhập nhé.",
  GOOGLE_OAUTH_NOT_CONFIGURED: "Đăng nhập bằng Google chưa được bật trên máy chủ này.",

  // Hồ sơ & đổi mật khẩu.
  INVALID_CURRENT_PASSWORD: "Mật khẩu hiện tại không đúng.",
  PASSWORD_UNCHANGED: "Mật khẩu mới phải khác mật khẩu hiện tại.",
  PASSWORD_NOT_SET:
    "Tài khoản này đăng nhập bằng Google nên chưa có mật khẩu để đổi.",
  ROLE_CHANGE_NOT_ALLOWED: "Tài khoản này không thể tự đổi vai trò.",

  // Khóa học.
  COURSE_NOT_FOUND: "Không tìm thấy khóa học này. Có thể nó đã bị xóa.",
  CATEGORY_NOT_FOUND: "Danh mục vừa chọn không còn tồn tại, chọn lại giúp mình nhé.",
  INVALID_COURSE_STATUS:
    "Khóa học đang ở trạng thái khác nên không làm được thao tác này. Tải lại trang nhé.",
  PERMISSION_DENIED: "Bạn không có quyền thực hiện thao tác này.",

  // Mục lục.
  SECTION_NOT_FOUND: "Chương này không còn tồn tại. Tải lại trang giúp mình nhé.",
  LESSON_NOT_FOUND: "Bài học này không còn tồn tại. Tải lại trang giúp mình nhé.",
  LESSON_LOCKED: "Bài học này cần đăng ký khóa học mới xem được.",
  INVALID_ORDER:
    "Thứ tự vừa gửi không khớp với nội dung khóa học. Tải lại trang rồi sắp xếp lại nhé.",

  // Đánh giá khóa học.
  NOT_ENROLLED: "Bạn cần đăng ký khóa học này trước khi đánh giá.",
  CANNOT_REVIEW_OWN_COURSE: "Bạn là giảng viên của khóa học này nên không đánh giá được.",
  REVIEW_NOT_FOUND: "Đánh giá này không còn tồn tại. Tải lại trang giúp mình nhé.",

  // Video.
  STORAGE_NOT_CONFIGURED:
    "Máy chủ chưa cấu hình kho lưu trữ nên chưa tải video lên được. Xem docs/huong-dan-cloudflare-r2.md.",
  STORAGE_ERROR: "Kho lưu trữ đang trục trặc. Thử lại sau ít phút.",
  VIDEO_ASSET_NOT_FOUND: "Không tìm thấy video này. Có thể nó đã được thay bằng video khác.",
  LESSON_NOT_VIDEO: "Chỉ bài học dạng video mới gắn được video.",
  INVALID_VIDEO_STATUS:
    "Video đang ở trạng thái khác nên không làm được thao tác này. Tải lại trang nhé.",
};

const NETWORK_FAILURE = "Không kết nối được máy chủ. Kiểm tra mạng rồi thử lại.";
const UNKNOWN_FAILURE = "Có lỗi xảy ra, vui lòng thử lại.";

/** Message for a bare error code, e.g. the `loi` query the OAuth callback sends. */
export function errorMessageForCode(code: string): string {
  return MESSAGES[code] ?? UNKNOWN_FAILURE;
}

export function apiErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return MESSAGES[error.code] ?? error.message ?? UNKNOWN_FAILURE;
  }

  // fetch() rejects with a TypeError when the backend is unreachable, which is
  // the most common failure while developing.
  if (error instanceof TypeError) return NETWORK_FAILURE;

  return UNKNOWN_FAILURE;
}
