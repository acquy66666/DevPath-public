"use client";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

/**
 * Render-time failures only. A rejected sign-in never reaches here -- the form
 * catches those and shows them in place, which is where the user is looking.
 */
export default function AuthError({ reset }: { error: Error; reset: () => void }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xl">Không mở được trang</CardTitle>
        <CardDescription>
          Có lỗi xảy ra khi hiển thị biểu mẫu. Thử lại giúp mình nhé.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Button onClick={reset} className="w-full">
          Thử lại
        </Button>
      </CardContent>
    </Card>
  );
}
