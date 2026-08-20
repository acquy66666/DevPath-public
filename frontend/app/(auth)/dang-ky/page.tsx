import type { Metadata } from "next";

import { RegisterForm } from "@/components/auth/register-form";
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

export default function RegisterPage() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xl">Tạo tài khoản</CardTitle>
        <CardDescription>
          Miễn phí. Học thử, làm bài tập code và được chấm tự động.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <RegisterForm />
      </CardContent>
    </Card>
  );
}
