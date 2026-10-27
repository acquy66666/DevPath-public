"use client";

import { useMutation } from "@tanstack/react-query";
import { CircleAlert, Loader2, Upload } from "lucide-react";
import { useRef, useState, type ChangeEvent } from "react";

import { UserAvatar } from "@/components/auth/user-avatar";
import { Button } from "@/components/ui/button";
import type { User } from "@/lib/api/auth";
import { apiErrorMessage, AVATAR_UPLOAD_MESSAGES } from "@/lib/api/error-messages";
import { uploadToStorage } from "@/lib/api/storage";
import { completeAvatarUpload, createAvatarUpload } from "@/lib/api/users";
import { useAuth } from "@/lib/auth/auth-provider";

/** Mirrors ALLOWED_IMAGE_TYPES in backend/app/services/storage.py. */
const ACCEPTED = ["image/jpeg", "image/png", "image/webp"];
const MAX_BYTES = 5 * 1024 * 1024;

type Phase = "idle" | "signing" | "sending" | "finishing";

const PHASE_LABELS: Record<Exclude<Phase, "idle">, string> = {
  signing: "Đang chuẩn bị…",
  sending: "Đang tải ảnh…",
  finishing: "Đang lưu…",
};

/**
 * The picture and the button that changes it, in the same place: the account
 * card at the top of the profile. What it accepts is said beside the name
 * (`AVATAR_RULE`), a refusal right under the button.
 */
export function AvatarForm({ user }: { user: User }) {
  const { accessToken, refreshSession } = useAuth();
  const fileInput = useRef<HTMLInputElement>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [fileError, setFileError] = useState<string | null>(null);

  const upload = useMutation({
    mutationFn: async (file: File) => {
      setPhase("signing");
      const ticket = await createAvatarUpload(accessToken as string, {
        filename: file.name,
        content_type: file.type,
        size_bytes: file.size,
      });

      // Straight to the bucket: the signature in the URL is the whole
      // authorization, and the bytes never touch our API.
      setPhase("sending");
      await uploadToStorage(ticket, file);

      setPhase("finishing");
      await completeAvatarUpload(accessToken as string, ticket.storage_key);
      // Re-read rather than patch: the header draws the same picture.
      await refreshSession();
    },
    onSettled: () => {
      setPhase("idle");
      // Let the same file be picked again after a failure — without this the
      // input holds the old value and `change` never fires.
      if (fileInput.current) fileInput.current.value = "";
    },
  });

  function handleFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!ACCEPTED.includes(file.type)) {
      setFileError("Định dạng chưa hỗ trợ. Dùng JPG, PNG hoặc WebP.");
      return;
    }
    if (file.size > MAX_BYTES) {
      setFileError("Ảnh đại diện tối đa 5 MB.");
      return;
    }

    setFileError(null);
    upload.mutate(file);
  }

  const busy = phase !== "idle";
  const error = fileError ?? (upload.isError ? apiErrorMessage(upload.error, AVATAR_UPLOAD_MESSAGES) : null);

  return (
    <div className="flex shrink-0 flex-col items-center gap-2">
      <UserAvatar user={user} className="size-20 text-h2 md:size-24" />
      <input
        ref={fileInput}
        type="file"
        accept={ACCEPTED.join(",")}
        onChange={handleFile}
        className="hidden"
        aria-hidden
        tabIndex={-1}
      />
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={() => fileInput.current?.click()}
        disabled={busy}
        aria-describedby="avatar-rule"
      >
        {busy ? (
          <>
            <Loader2 className="animate-spin" aria-hidden />
            {PHASE_LABELS[phase as Exclude<Phase, "idle">]}
          </>
        ) : (
          <>
            <Upload aria-hidden />
            {user.avatar_url ? "Đổi ảnh" : "Tải ảnh lên"}
          </>
        )}
      </Button>
      {error ? (
        <p role="alert" className="flex max-w-48 items-start gap-1.5 text-caption text-destructive-text">
          <CircleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          <span>{error}</span>
        </p>
      ) : null}
    </div>
  );
}

/** What the picture may be. `id` is the upload button's description. */
export const AVATAR_RULE = { id: "avatar-rule", text: "Ảnh JPG, PNG hoặc WebP, tối đa 5 MB." };
