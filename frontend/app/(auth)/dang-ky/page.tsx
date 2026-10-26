import { Check } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { AuthShell } from "@/components/auth/auth-shell";
import { GoogleButton } from "@/components/auth/google-button";
import { RegisterForm } from "@/components/auth/register-form";
import { courseTitleFor } from "@/lib/account/course-title";
import { safeNextPath } from "@/lib/auth/next-path";

export const metadata: Metadata = {
  title: "Đăng ký — DevPath",
  description: "Tạo tài khoản DevPath để bắt đầu học lập trình với chấm bài tự động.",
};

const ASIDE = {
  heading: "Học lập trình bằng cách viết code",
  text: "Tài khoản miễn phí. Bạn chỉ trả tiền cho khóa có phí, khi bạn chọn mua.",
  points: [
    { icon: Check, text: "Học thử các bài xem trước của mọi khóa" },
    { icon: Check, text: "Bài tập code được chấm tự động, từng test một" },
    { icon: Check, text: "XP, chuỗi ngày học và chứng chỉ khi học xong" },
  ],
};

export default async function RegisterPage({ searchParams }: PageProps<"/dang-ky">) {
  const next = safeNextPath((await searchParams).next);
  // Someone sent here from a course page is told they go back to it.
  const title = await courseTitleFor(next);

  return (
    <AuthShell
      title="Tạo tài khoản"
      description={
        title ? (
          <>
            Xong là bạn quay lại{" "}
            <Link href={next} className="font-medium text-link underline-offset-4 hover:underline">
              {title}
            </Link>
            .
          </>
        ) : (
          "Miễn phí. Học thử, làm bài tập code và được chấm tự động."
        )
      }
      aside={ASIDE}
    >
      <GoogleButton label="Đăng ký bằng Google" />
      <RegisterForm next={next} />
    </AuthShell>
  );
}
