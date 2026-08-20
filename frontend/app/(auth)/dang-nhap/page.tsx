import type { Metadata } from "next";

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

export default function LoginPage() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xl">Đăng nhập</CardTitle>
        <CardDescription>Tiếp tục khóa học đang học dở của bạn.</CardDescription>
      </CardHeader>
      <CardContent>
        <LoginForm />
      </CardContent>
    </Card>
  );
}
