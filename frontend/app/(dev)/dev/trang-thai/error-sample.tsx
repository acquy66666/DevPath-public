"use client";

import AuthError from "@/app/(auth)/error";
import InstructorError from "@/app/(dashboard)/giang-day/error";
import AdminError from "@/app/(dashboard)/quan-tri/error";
import LearnError from "@/app/(learn)/error";
import CertificateError from "@/app/(marketing)/cert/[code]/error";
import CourseDetailError from "@/app/(marketing)/khoa-hoc/[slug]/error";
import CatalogError from "@/app/(marketing)/khoa-hoc/error";
import AppError from "@/app/error";

const BOUNDARIES = {
  site: AppError,
  learn: LearnError,
  course: CourseDetailError,
  catalogue: CatalogError,
  cert: CertificateError,
  auth: AuthError,
  instructor: InstructorError,
  admin: AdminError,
} as const;

/** The digest Next attaches to a server error: shown so the "Mã lỗi" line is visible too. */
const SAMPLE = Object.assign(new Error("preview"), { digest: "2043918857" });

/** An error boundary as Next renders it, with a fake error and a no-op retry. */
export function ErrorSample({ which }: { which: keyof typeof BOUNDARIES }) {
  const Boundary = BOUNDARIES[which];
  return <Boundary error={SAMPLE} retry={() => undefined} />;
}
