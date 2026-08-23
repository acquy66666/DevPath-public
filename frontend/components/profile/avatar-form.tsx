"use client";

import { useMutation } from "@tanstack/react-query";
import { Loader2, Upload } from "lucide-react";
import { useRef, useState, type ChangeEvent } from "react";

import { UserAvatar } from "@/components/auth/user-avatar";
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
import { apiErrorMessage } from "@/lib/api/error-messages";
import { uploadToStorage } from "@/lib/api/storage";
import { completeAvatarUpload, createAvatarUpload } from "@/lib/api/users";
import { useAuth } from "@/lib/auth/auth-provider";

/** Mirrors ALLOWED_IMAGE_TYPES in backend/app/services/storage.py. */
const ACCEPTED = ["image/jpeg", "image/png", "image/webp"];
const MAX_BYTES = 5 * 1024 * 1024;

type Phase = "idle" | "signing" | "sending" | "finishing";

const PHASE_LABELS: Record<Exclude<Phase, "idle">, string> = {
  signing: "Đang xin đường dẫn tải lên…",
  sending: "Đang tải ảnh lên…",
  finishing: "Đang lưu vào hồ sơ…",
};

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

  return (
    <Card>
      <CardHeader>
        <CardTitle>Ảnh đại diện</CardTitle>
        <CardDescription>
          Ảnh hiển thị cạnh tên bạn ở thanh điều hướng và trong phần hỏi đáp khóa học.
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4">
        {fileError ? (
          <Alert variant="destructive">
            <AlertDescription>{fileError}</AlertDescription>
          </Alert>
        ) : null}

        {upload.isError ? (
          <Alert variant="destructive">
            <AlertDescription>{apiErrorMessage(upload.error)}</AlertDescription>
          </Alert>
        ) : null}

        <div className="flex items-center gap-4">
          <UserAvatar user={user} className="size-20 text-xl" />

          <div className="space-y-2">
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
            >
              {busy ? (
                <>
                  <Loader2 className="animate-spin" aria-hidden />
                  {PHASE_LABELS[phase as Exclude<Phase, "idle">]}
                </>
              ) : (
                <>
                  <Upload aria-hidden />
                  {user.avatar_url ? "Đổi ảnh khác" : "Tải ảnh lên"}
                </>
              )}
            </Button>
            <p className="text-xs text-muted-foreground">
              JPG, PNG hoặc WebP, tối đa 5 MB.
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
