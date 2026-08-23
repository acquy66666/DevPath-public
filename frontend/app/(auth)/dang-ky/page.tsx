import type { Metadata } from "next";

import { GoogleButton } from "@/components/auth/google-button";
import { RegisterForm } from "@/components/auth/register-form";
import { safeNextPath } from "@/lib/auth/next-path";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export const metadata: Metadata = {
  title: "Đăng ký — DevPath",
  description: "Tạo tài khoản DevPath để bắt đầu học lập trình với chấm bài tự động.",
};

export default async function RegisterPage({ searchParams }: PageProps<"/dang-ky">) {
  const { next } = await searchParams;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xl">Tạo tài khoản</CardTitle>
        <CardDescription>
          Miễn phí. Học thử, làm bài tập code và được chấm tự động.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <GoogleButton label="Đăng ký bằng Google" />
        <RegisterForm next={safeNextPath(next)} />
      </CardContent>
    </Card>
  );
}
