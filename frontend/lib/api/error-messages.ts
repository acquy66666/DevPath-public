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
    "Thứ tự vừa gửi không khớp với dữ liệu trên máy chủ. Tải lại trang rồi sắp xếp lại nhé.",

  // Đánh giá khóa học.
  NOT_ENROLLED: "Bạn cần đăng ký khóa học này trước khi đánh giá.",
  CANNOT_REVIEW_OWN_COURSE: "Bạn là giảng viên của khóa học này nên không đánh giá được.",
  REVIEW_NOT_FOUND: "Đánh giá này không còn tồn tại. Tải lại trang giúp mình nhé.",

  // Giỏ hàng & danh sách yêu thích. CART_FULL cố ý không có ở đây: câu của
  // backend nói đúng sức chứa ("tối đa 50 khóa học"), câu chung thì không.
  ALREADY_ENROLLED: "Bạn đã có khóa học này rồi, vào học được ngay.",
  CANNOT_BUY_OWN_COURSE: "Bạn là giảng viên của khóa học này nên không mua được.",

  // Mã giảm giá. COUPON_EXPIRED và COUPON_NOT_STARTED cố ý không có ở đây,
  // cùng lý do với CART_FULL: câu của backend kèm ngày ("hết hạn ngày
  // 23/08/2026"), và cái ngày đó là thứ người cầm tờ rơi cần đọc.
  COUPON_NOT_FOUND: "Mã giảm giá không đúng. Kiểm tra lại giúp mình nhé.",
  COUPON_EXHAUSTED: "Mã này đã hết lượt sử dụng.",
  COUPON_NOT_APPLICABLE:
    "Mã này không áp dụng cho khóa học nào đang có trong giỏ hàng.",
  CART_EMPTY: "Giỏ hàng chưa có khóa học nào cần thanh toán.",

  // Đơn hàng & thanh toán.
  ORDER_NOT_FOUND: "Không tìm thấy đơn hàng này trong tài khoản của bạn.",
  ORDER_NOT_PAYABLE:
    "Đơn hàng này không còn chờ thanh toán. Tải lại trang để xem trạng thái mới nhất.",
  PAYMENT_NOT_CONFIGURED:
    "Máy chủ chưa cấu hình cổng thanh toán VNPay nên chưa thanh toán được.",
  ORDER_CODE_UNAVAILABLE: "Chưa tạo được mã đơn hàng. Bấm thanh toán lại giúp mình nhé.",

  // Video.
  STORAGE_NOT_CONFIGURED:
    "Máy chủ chưa cấu hình kho lưu trữ nên chưa tải video lên được. Xem docs/huong-dan-cloudflare-r2.md.",
  STORAGE_ERROR: "Kho lưu trữ đang trục trặc. Thử lại sau ít phút.",
  VIDEO_ASSET_NOT_FOUND: "Không tìm thấy video này. Có thể nó đã được thay bằng video khác.",
  LESSON_NOT_VIDEO: "Chỉ bài học dạng video mới gắn được video.",
  INVALID_VIDEO_STATUS:
    "Video đang ở trạng thái khác nên không làm được thao tác này. Tải lại trang nhé.",

  // Transcript. TRANSCRIPT_UNREADABLE và TRANSCRIPT_EMPTY cố ý không có ở đây:
  // backend gửi kèm câu viết cho đúng tệp đó (vì sao không đọc được, sửa thế
  // nào), và câu đó đi thẳng tới giảng viên — tốt hơn mọi câu chung.
  LESSON_HAS_NO_VIDEO: "Tải video lên trước, rồi mới gắn transcript cho nó.",
  TRANSCRIPT_NOT_FOUND: "Video này chưa có transcript.",

  // Bài tập code. EXERCISE_NOT_FOUND cũng là câu trả lời bình thường cho một bài
  // học vừa tạo — nơi nào coi nó là trạng thái rỗng thì bắt riêng, không lấy câu
  // này.
  EXERCISE_NOT_FOUND: "Bài học này chưa có bài tập code.",
  EXERCISE_EXISTS: "Bài học này đã có bài tập code rồi. Tải lại trang nhé.",
  LESSON_NOT_CODE_EXERCISE:
    "Chỉ bài học kiểu “Bài tập code” mới gắn được bài tập chấm tự động.",
  TEST_CASE_NOT_FOUND: "Test case này không còn tồn tại. Tải lại trang giúp mình nhé.",
  EXERCISE_NOT_READY:
    "Bài tập chưa có test case nào nên chưa nhận bài nộp được.",
  // Khác EXERCISE_NOT_READY: bài tập vẫn nộp được bình thường, chỉ là không có
  // test mẫu nào để chạy thử. Trang nộp bài khóa riêng nút “Chạy thử”.
  NO_SAMPLE_TEST_CASES:
    "Bài tập này không có test case mẫu nào để chạy thử. Bạn nộp bài trực tiếp nhé.",
  SUBMISSION_NOT_FOUND: "Không tìm thấy bài nộp này.",
  // Kèm `retry_after` (giây) trong detail — trang nộp bài dùng số đó để đếm
  // ngược thay vì hiện câu chung chung này.
  SUBMISSION_RATE_LIMITED: "Bạn nộp bài hơi nhanh. Đợi một chút rồi thử lại nhé.",
  GRADING_UNAVAILABLE:
    "Hệ thống chấm bài đang bận hoặc tạm ngừng. Thử lại sau ít phút nhé.",

  // Sinh quiz bằng AI. QUIZ_GENERATION_RATE_LIMITED cố ý không có ở đây, cùng
  // lý do với CHAT_RATE_LIMITED bên dưới: câu của backend nói phải đợi bao lâu.
  LESSON_HAS_NO_TEXT:
    "Bài học này chưa có chữ để AI soạn câu hỏi — cần nội dung bài viết, hoặc transcript nếu là video.",
  SOURCE_NOT_IN_COURSE: "Chỉ sinh câu hỏi được từ bài học trong cùng khóa học.",
  QUIZ_GENERATION_FAILED:
    "AI không soạn được câu hỏi nào dùng được từ bài này. Thử lại, hoặc chọn bài khác.",
  QUIZ_NEEDS_REVIEW:
    "Còn câu hỏi do AI soạn chưa được duyệt. Duyệt, sửa hoặc xóa từng câu rồi hãy xuất bản.",
  QUESTION_NOT_GENERATED: "Câu hỏi này do bạn tự viết nên không cần duyệt.",

  // Trợ giảng AI. CHAT_RATE_LIMITED cố ý không có ở đây: câu của backend nói
  // đúng phải đợi bao lâu ("Đợi 3 giây…", "…sau khoảng 12 phút"), câu chung
  // thì không.
  CHAT_SESSION_NOT_FOUND:
    "Cuộc trò chuyện này không còn nữa — có thể đã bị xóa ở tab khác. Bắt đầu cuộc trò chuyện mới nhé.",
  LLM_UNAVAILABLE:
    "Trợ giảng AI đang quá tải hoặc tạm ngừng. Câu hỏi chưa được lưu — thử lại sau ít phút nhé.",
  LLM_NOT_CONFIGURED: "Máy chủ này chưa bật trợ giảng AI (thiếu khóa Gemini).",

  // Hỏi đáp. QA_NOT_ALLOWED cố ý không có ở đây: câu của backend nói đúng luật
  // nào chặn (chỉ người hỏi sửa được, chỉ người hỏi hoặc giảng viên xóa được…).
  QA_THREAD_NOT_FOUND: "Câu hỏi này không còn nữa — có thể đã bị xóa.",
  QA_REPLY_NOT_FOUND: "Câu trả lời này không còn nữa — có thể đã bị xóa.",
  CANNOT_VOTE_OWN_THREAD: "Bạn không thể bình chọn câu hỏi của chính mình.",

  // Báo cáo vi phạm.
  REPORT_TARGET_NOT_FOUND: "Nội dung này không còn nữa — có thể đã bị xóa.",
  CANNOT_REPORT_OWN_CONTENT: "Bạn không thể báo cáo nội dung của chính mình.",
  ALREADY_REPORTED: "Bạn đã báo cáo nội dung này rồi, quản trị viên đang xem xét.",

  // Quản trị.
  REPORT_NOT_FOUND: "Không tìm thấy báo cáo này. Tải lại trang giúp mình nhé.",
  REPORT_ALREADY_CLOSED:
    "Báo cáo này vừa được xử lý (có thể bởi một quản trị viên khác). Tải lại trang nhé.",
  USER_NOT_FOUND: "Không tìm thấy tài khoản này.",
  // CATEGORY_IN_USE, CATEGORY_HAS_CHILDREN, CATEGORY_NAME_TAKEN, CATEGORY_TOO_DEEP
  // cố ý không có ở đây: câu của backend nói đúng số khóa học/danh mục con đang
  // chắn và tên bị trùng.
  CANNOT_LOCK_ADMIN: "Không khóa được tài khoản quản trị viên.",
};

const NETWORK_FAILURE = "Không kết nối được máy chủ. Kiểm tra mạng rồi thử lại.";
const UNKNOWN_FAILURE = "Có lỗi xảy ra, vui lòng thử lại.";

/** Message for a bare error code, e.g. the `loi` query the OAuth callback sends. */
export function errorMessageForCode(code: string): string {
  return MESSAGES[code] ?? UNKNOWN_FAILURE;
}

/**
 * Wording one screen needs in place of the default for a code it shares.
 *
 * The backend names a failure, not the screen it happened on: the storage codes
 * come back the same from a video upload and an avatar upload. The defaults
 * above were written for video, where they first appeared, so a screen that
 * uploads something else passes its own sentence rather than telling someone
 * changing their photo that a video could not be uploaded.
 */
export type MessageOverrides = Readonly<Partial<Record<string, string>>>;

export const AVATAR_UPLOAD_MESSAGES: MessageOverrides = {
  STORAGE_NOT_CONFIGURED:
    "Máy chủ chưa cấu hình kho lưu trữ nên chưa đổi được ảnh đại diện. Ảnh hiện tại vẫn giữ nguyên.",
  STORAGE_ERROR: "Kho lưu trữ đang trục trặc nên chưa lưu được ảnh. Thử lại sau ít phút.",
};

/** NOT_ENROLLED is worded for reviews, where it first appeared. */
export const CHAT_MESSAGES: MessageOverrides = {
  NOT_ENROLLED: "Trợ giảng AI dành cho học viên đã đăng ký khóa học này.",
  COURSE_NOT_FOUND:
    "Khóa học này hiện không mở trợ giảng AI — có thể nó vừa ngừng xuất bản.",
};

export function apiErrorMessage(error: unknown, overrides?: MessageOverrides): string {
  if (error instanceof ApiError) {
    return overrides?.[error.code] ?? MESSAGES[error.code] ?? error.message ?? UNKNOWN_FAILURE;
  }

  // fetch() rejects with a TypeError when the backend is unreachable, which is
  // the most common failure while developing.
  if (error instanceof TypeError) return NETWORK_FAILURE;

  return UNKNOWN_FAILURE;
}
