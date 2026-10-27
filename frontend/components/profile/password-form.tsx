"use client";

import { useMutation } from "@tanstack/react-query";
import { Check, Loader2 } from "lucide-react";
import { useRef, useState, type FormEvent } from "react";

import { GoogleMark } from "@/components/auth/google-button";
import { PasswordField } from "@/components/auth/password-field";
import { SettingsSection } from "@/components/profile/settings-section";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import type { User } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { changePassword } from "@/lib/api/users";
import { useAuth } from "@/lib/auth/auth-provider";
import { validatePassword } from "@/lib/auth/validation";

export function PasswordForm({ user }: { user: User }) {
  const { accessToken, refreshSession } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string | null>>({});
  const currentInput = useRef<HTMLInputElement>(null);
  const newInput = useRef<HTMLInputElement>(null);

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
    onError: (error) => {
      // The current password was wrong: that is the field to retype.
      if (error instanceof ApiError && error.code === "INVALID_CURRENT_PASSWORD") {
        setCurrentPassword("");
        requestAnimationFrame(() => currentInput.current?.focus());
      }
    },
  });

  /** Typing in a field takes back what was said about it. */
  function edit(key: string, set: (value: string) => void) {
    return (value: string) => {
      set(value);
      setFieldErrors((errors) => (errors[key] ? { ...errors, [key]: null } : errors));
    };
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const errors = {
      current_password: currentPassword ? null : "Vui lòng nhập mật khẩu hiện tại",
      new_password: validatePassword(newPassword),
    };
    setFieldErrors(errors);
    if (errors.current_password) return currentInput.current?.focus();
    if (errors.new_password) return newInput.current?.focus();

    mutation.mutate();
  }

  // A Google-only account has no password to change, and the backend would
  // answer 409. Say so instead of showing a form that cannot work.
  if (!user.has_password) {
    return (
      <SettingsSection id="profile-password" title="Mật khẩu">
        <p className="flex items-start gap-3 text-body text-foreground/80">
          <GoogleMark className="mt-0.5 size-5 shrink-0" />
          <span>
            Tài khoản này đăng nhập bằng Google nên chưa có mật khẩu riêng. Bạn vào DevPath bằng nút
            “Đăng nhập bằng Google”.
          </span>
        </p>
      </SettingsSection>
    );
  }

  return (
    <SettingsSection
      id="profile-password"
      title="Đổi mật khẩu"
      description="Đổi xong, mọi thiết bị khác sẽ bị đăng xuất. Thiết bị này thì không."
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
        {mutation.isError ? (
          <Alert variant="destructive">
            <AlertDescription>{apiErrorMessage(mutation.error)}</AlertDescription>
          </Alert>
        ) : null}

        {mutation.isSuccess ? (
          <Alert variant="success">
            <Check aria-hidden />
            <AlertDescription>Đã đổi mật khẩu. Các thiết bị khác đã bị đăng xuất.</AlertDescription>
          </Alert>
        ) : null}

        <PasswordField
          ref={currentInput}
          label="Mật khẩu hiện tại"
          value={currentPassword}
          onChange={edit("current_password", setCurrentPassword)}
          error={fieldErrors.current_password}
          autoComplete="current-password"
          disabled={mutation.isPending}
        />

        <PasswordField
          ref={newInput}
          label="Mật khẩu mới"
          value={newPassword}
          onChange={edit("new_password", setNewPassword)}
          error={fieldErrors.new_password}
          autoComplete="new-password"
          rule
          disabled={mutation.isPending}
        />

        <div>
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
        </div>
      </form>
    </SettingsSection>
  );
}
