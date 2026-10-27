import { MessageSquareText, ShieldCheck, Sparkles } from "lucide-react";
import type { Metadata } from "next";

import { AuthShell } from "@/components/auth/auth-shell";
import { GoogleButton } from "@/components/auth/google-button";
import { LoginForm } from "@/components/auth/login-form";
import { safeNextPath } from "@/lib/auth/next-path";

export const metadata: Metadata = {
  title: "Đăng nhập — DevPath",
  description: "Đăng nhập để tiếp tục khóa học của bạn trên DevPath.",
};

const ASIDE = {
  heading: "Chào mừng trở lại",
  text: "Tiến độ, bài đã nộp, ghi chú và chuỗi ngày học của bạn vẫn ở đây.",
  points: [
    { icon: ShieldCheck, text: "Chấm trong sandbox Docker" },
    { icon: Sparkles, text: "Gợi ý theo tiến độ" },
    { icon: MessageSquareText, text: "Trợ giảng AI trích nguồn bài giảng" },
  ],
};

/**
 * `loi` is set by the Google callback when the round trip fails: the callback
 * is a browser navigation, so its errors have to come back as a page.
 * `email` is filled in by sign-up's "this email already has an account".
 */
export default async function LoginPage({ searchParams }: PageProps<"/dang-nhap">) {
  const { loi, next, email } = await searchParams;
  const errorCode = typeof loi === "string" ? loi : null;

  return (
    <AuthShell title="Đăng nhập" description="Tiếp tục khóa học đang học dở của bạn." aside={ASIDE}>
      <GoogleButton label="Đăng nhập bằng Google" />
      <LoginForm
        errorCode={errorCode}
        next={safeNextPath(next)}
        initialEmail={typeof email === "string" ? email : ""}
      />
    </AuthShell>
  );
}
