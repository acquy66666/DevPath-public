"use client";

import { useMutation } from "@tanstack/react-query";
import { Check, Loader2 } from "lucide-react";
import { useState, type FormEvent } from "react";

import { AuthFormField } from "@/components/auth/auth-form-field";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { User } from "@/lib/api/auth";
import { changePassword } from "@/lib/api/users";
import { useAuth } from "@/lib/auth/auth-provider";
import { authErrorMessage } from "@/lib/auth/error-messages";
import { PASSWORD_MIN_LENGTH, validatePassword } from "@/lib/auth/validation";

export function PasswordForm({ user }: { user: User }) {
  const { accessToken, refreshSession } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string | null>>({});

  const mutation = useMutation({
    mutationFn: async () => {
      await changePassword(accessToken as string, {
        current_password: currentPassword,
        new_password: newPassword,
      });
      // Every session was just revoked, this browser's included. Picking the
      // replacement up is what keeps the tab signed in.
      await refreshSession();
    },
    onSuccess: () => {
      setCurrentPassword("");
      setNewPassword("");
    },
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const errors = {
      current_password: currentPassword ? null : "Vui lòng nhập mật khẩu hiện tại",
      new_password: validatePassword(newPassword),
    };
    setFieldErrors(errors);
    if (errors.current_password || errors.new_password) return;

    mutation.mutate();
  }

  // A Google-only account has no password to change, and the backend would
  // answer 409. Say so instead of showing a form that cannot work.
  if (!user.has_password) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Mật khẩu</CardTitle>
          <CardDescription>
            Tài khoản này đăng nhập bằng Google nên chưa có mật khẩu. Đặt mật khẩu
            riêng là tính năng sẽ bổ sung sau.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Đổi mật khẩu</CardTitle>
        <CardDescription>
          Đổi xong, mọi thiết bị khác sẽ bị đăng xuất. Thiết bị này thì không.
        </CardDescription>
      </CardHeader>

      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          {mutation.isError ? (
            <Alert variant="destructive">
              <AlertDescription>{authErrorMessage(mutation.error)}</AlertDescription>
            </Alert>
          ) : null}

          {mutation.isSuccess ? (
            <Alert>
              <AlertDescription className="flex items-center gap-2">
                <Check className="size-4" aria-hidden />
                Đã đổi mật khẩu. Các thiết bị khác đã bị đăng xuất.
              </AlertDescription>
            </Alert>
          ) : null}

          <AuthFormField
            label="Mật khẩu hiện tại"
            type="password"
            value={currentPassword}
            onChange={setCurrentPassword}
            error={fieldErrors.current_password}
            autoComplete="current-password"
            disabled={mutation.isPending}
          />

          <AuthFormField
            label="Mật khẩu mới"
            type="password"
            value={newPassword}
            onChange={setNewPassword}
            error={fieldErrors.new_password}
            hint={`Tối thiểu ${PASSWORD_MIN_LENGTH} ký tự`}
            autoComplete="new-password"
            disabled={mutation.isPending}
          />

          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? (
              <>
                <Loader2 className="animate-spin" aria-hidden />
                Đang đổi…
              </>
            ) : (
              "Đổi mật khẩu"
            )}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
