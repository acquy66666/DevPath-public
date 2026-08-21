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
import { updateProfile } from "@/lib/api/users";
import { useAuth } from "@/lib/auth/auth-provider";
import { authErrorMessage } from "@/lib/auth/error-messages";
import { ROLE_LABELS } from "@/lib/auth/roles";
import { validateFullName } from "@/lib/auth/validation";

function joinedOn(user: User): string {
  return new Date(user.created_at).toLocaleDateString("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

export function ProfileForm({ user }: { user: User }) {
  const { accessToken, refreshSession } = useAuth();
  const [fullName, setFullName] = useState(user.full_name);
  const [nameError, setNameError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: async () => {
      await updateProfile(accessToken as string, { full_name: fullName.trim() });
      // Re-read rather than patch: the header shows the same name.
      await refreshSession();
    },
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const error = validateFullName(fullName);
    setNameError(error);
    if (error) return;

    mutation.mutate();
  }

  const unchanged = fullName.trim() === user.full_name;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Thông tin cá nhân</CardTitle>
        <CardDescription>
          {ROLE_LABELS[user.role]} · Tham gia ngày {joinedOn(user)}
        </CardDescription>
      </CardHeader>

      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          {mutation.isError ? (
            <Alert variant="destructive">
              <AlertDescription>{authErrorMessage(mutation.error)}</AlertDescription>
            </Alert>
          ) : null}

          {mutation.isSuccess && unchanged ? (
            <Alert>
              <AlertDescription className="flex items-center gap-2">
                <Check className="size-4" aria-hidden />
                Đã lưu thay đổi.
              </AlertDescription>
            </Alert>
          ) : null}

          <AuthFormField
            label="Họ và tên"
            type="text"
            value={fullName}
            onChange={setFullName}
            error={nameError}
            autoComplete="name"
            disabled={mutation.isPending}
          />

          <div className="space-y-2">
            <p className="text-sm font-medium">Email</p>
            <p className="text-sm text-muted-foreground">{user.email}</p>
            <p className="text-xs text-muted-foreground">
              Chưa đổi được email: địa chỉ mới phải xác thực xong mới dùng được, và
              đó là một luồng riêng.
            </p>
          </div>

          <Button type="submit" disabled={mutation.isPending || unchanged}>
            {mutation.isPending ? (
              <>
                <Loader2 className="animate-spin" aria-hidden />
                Đang lưu…
              </>
            ) : (
              "Lưu thay đổi"
            )}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
