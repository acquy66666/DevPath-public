import type { User } from "@/lib/api/auth";

export const ROLE_LABELS: Record<User["role"], string> = {
  student: "Học viên",
  instructor: "Giảng viên",
  admin: "Quản trị viên",
};
