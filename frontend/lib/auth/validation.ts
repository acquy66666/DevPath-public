/**
 * Client-side copies of the rules in backend/app/schemas/auth.py.
 *
 * The backend stays the authority -- this only saves a round trip and lets the
 * form say what is wrong next to the field instead of in a banner.
 */

export const PASSWORD_MIN_LENGTH = 8;
/** bcrypt reads at most 72 bytes; the backend rejects anything longer. */
export const PASSWORD_MAX_BYTES = 72;
export const FULL_NAME_MAX_LENGTH = 150;

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function byteLength(value: string): number {
  return new TextEncoder().encode(value).length;
}

export function validateEmail(value: string): string | null {
  const email = value.trim();
  if (!email) return "Vui lòng nhập email";
  if (!EMAIL_PATTERN.test(email)) return "Email không hợp lệ";
  return null;
}

export function validatePassword(value: string): string | null {
  if (!value) return "Vui lòng nhập mật khẩu";
  if (value.length < PASSWORD_MIN_LENGTH) {
    return `Mật khẩu tối thiểu ${PASSWORD_MIN_LENGTH} ký tự`;
  }
  if (byteLength(value) > PASSWORD_MAX_BYTES) {
    // Vietnamese letters take 2–3 bytes each, so this is closer than it looks.
    return `Mật khẩu quá dài (tối đa ${PASSWORD_MAX_BYTES} byte, chữ có dấu tính 2–3 byte)`;
  }
  return null;
}

export function validateFullName(value: string): string | null {
  const name = value.trim();
  if (!name) return "Vui lòng nhập họ tên";
  if (name.length > FULL_NAME_MAX_LENGTH) {
    return `Họ tên tối đa ${FULL_NAME_MAX_LENGTH} ký tự`;
  }
  return null;
}
