"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { StatePanel } from "@/components/ui/state-panel";

/**
 * Render-time failures only. A rejected sign-in never reaches here -- the form
 * catches those and shows them in place, which is where the user is looking.
 * The card is as narrow as the sign-in form, so Naomi stands above the text.
 */
export default function AuthError({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  return (
    <Card>
      <CardContent>
        <StatePanel
          mood="sorry"
          title="Không mở được trang"
          titleAs="h2"
          compact
          detail={error.digest ? `Mã lỗi: ${error.digest}` : null}
          actions={
            <Button onClick={retry} className="w-full">
              Thử lại
            </Button>
          }
        >
          Lỗi phía hệ thống khi hiển thị biểu mẫu, không phải do bạn. Thử lại thường là đủ.
        </StatePanel>
      </CardContent>
    </Card>
  );
}
