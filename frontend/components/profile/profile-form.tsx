"use client";

import { useMutation } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useRef, useState, type FormEvent } from "react";

import { SettingsSection } from "@/components/profile/settings-section";
import { FormField } from "@/components/ui/form-field";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import type { User } from "@/lib/api/auth";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { updateProfile } from "@/lib/api/users";
import { useAuth } from "@/lib/auth/auth-provider";
import { validateFullName } from "@/lib/auth/validation";

/**
 * The name, and the email shown read-only beside it. The certificate keeps the
 * name it was issued with (`certificates.recipient_name`), so a change reaches
 * only certificates issued afterwards -- the description says so.
 */
export function ProfileForm({ user }: { user: User }) {
  const { accessToken, refreshSession } = useAuth();
  const [fullName, setFullName] = useState(user.full_name);
  const [nameError, setNameError] = useState<string | null>(null);
  const nameInput = useRef<HTMLInputElement>(null);

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
    if (error) return nameInput.current?.focus();

    mutation.mutate();
  }

  const unchanged = fullName.trim() === user.full_name;

  return (
    <SettingsSection
      id="profile-info"
      title="Thông tin cá nhân"
      description="Tên hiện ở thanh điều hướng, phần hỏi đáp và trên chứng chỉ cấp sau khi đổi."
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
        {mutation.isError ? (
          <Alert variant="destructive">
            <AlertDescription>{apiErrorMessage(mutation.error)}</AlertDescription>
          </Alert>
        ) : null}

        <FormField
          ref={nameInput}
          label="Họ và tên"
          type="text"
          value={fullName}
          onChange={setFullName}
          error={nameError}
          autoComplete="name"
          disabled={mutation.isPending}
        />

        <div className="flex min-w-0 flex-col gap-1.5">
          <p className="text-sm font-medium">Email</p>
          <p className="rounded-md bg-muted px-3 py-2 text-base break-all text-foreground/80">{user.email}</p>
          <p className="text-sm text-muted-foreground">
            Chưa đổi được email: địa chỉ mới phải xác thực xong mới dùng được.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
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
          {/* One live line beside the button: what the button can do right now. */}
          <p role="status" className="text-body-sm text-muted-foreground">
            {mutation.isSuccess && unchanged ? (
              <span className="text-success-text">Đã lưu thay đổi.</span>
            ) : unchanged ? (
              "Chưa có gì thay đổi"
            ) : null}
          </p>
        </div>
      </form>
    </SettingsSection>
  );
}
