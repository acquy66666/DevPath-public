import type { Metadata } from "next";

import { GoogleButton } from "@/components/auth/google-button";
import { LoginForm } from "@/components/auth/login-form";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export const metadata: Metadata = {
  title: "Đăng nhập — DevPath",
  description: "Đăng nhập để tiếp tục khóa học của bạn trên DevPath.",
};

/**
 * `loi` is set by the Google callback when the round trip fails: the callback
 * is a browser navigation, so its errors have to come back as a page.
 */
export default async function LoginPage({ searchParams }: PageProps<"/dang-nhap">) {
  const { loi } = await searchParams;
  const errorCode = typeof loi === "string" ? loi : null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xl">Đăng nhập</CardTitle>
        <CardDescription>Tiếp tục khóa học đang học dở của bạn.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <GoogleButton label="Đăng nhập bằng Google" />
        <LoginForm errorCode={errorCode} />
      </CardContent>
    </Card>
  );
}
