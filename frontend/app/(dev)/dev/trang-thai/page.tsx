import type { Metadata } from "next";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import AuthLoading from "@/app/(auth)/loading";
import InstructorQaLoading from "@/app/(dashboard)/giang-day/hoi-dap/loading";
import InstructorLoading from "@/app/(dashboard)/giang-day/loading";
import InstructorStatsLoading from "@/app/(dashboard)/giang-day/thong-ke/loading";
import AdminLoading from "@/app/(dashboard)/quan-tri/loading";
import CertificateNotFound from "@/app/(marketing)/cert/[code]/not-found";
import CatalogueLoading from "@/app/(marketing)/khoa-hoc/(danh-sach)/loading";
import CourseNotFound from "@/app/(marketing)/khoa-hoc/[slug]/not-found";
import NotFound from "@/app/not-found";

import { ErrorSample } from "./error-sample";

export const metadata: Metadata = {
  title: "Trạng thái toàn site — xem trước",
  robots: { index: false, follow: false },
};

/**
 * Every 404, error boundary and route skeleton of the site on one page, as
 * the real files render them, to compare and capture evidence
 * (docs/report/assets/phase-7/site-states/). The real pages only show these
 * when something is missing, broken or slow, which a screenshot cannot ask
 * for on demand. Development only: a production build answers 404.
 */
export default function SiteStatesPreviewPage() {
  if (process.env.NODE_ENV === "production") notFound();
  return (
    <main className="mx-auto w-full max-w-6xl flex-1 space-y-10 px-4 py-8">
      <header className="space-y-1">
        <h1 className="text-h2">Trạng thái toàn site</h1>
        <p className="max-w-3xl text-body-sm text-muted-foreground">
          Trang chỉ có ở môi trường dev. Mỗi khung là đúng tệp <code>not-found.tsx</code>,{" "}
          <code>error.tsx</code> hay <code>loading.tsx</code> của route đó, render với một lỗi giả.
        </p>
      </header>

      <Group title="404">
        <Frame id="404-site" label="app/not-found.tsx" wide>
          <NotFound />
        </Frame>
        <Frame id="404-course" label="khoa-hoc/[slug]/not-found.tsx">
          <CourseNotFound />
        </Frame>
        <Frame id="404-cert" label="cert/[code]/not-found.tsx">
          <CertificateNotFound />
        </Frame>
      </Group>

      <Group title="Lỗi">
        <Frame id="error-site" label="app/error.tsx">
          <ErrorSample which="site" />
        </Frame>
        <Frame id="error-learn" label="(learn)/error.tsx">
          <ErrorSample which="learn" />
        </Frame>
        <Frame id="error-course" label="khoa-hoc/[slug]/error.tsx">
          <ErrorSample which="course" />
        </Frame>
        <Frame id="error-catalogue" label="khoa-hoc/error.tsx">
          <ErrorSample which="catalogue" />
        </Frame>
        <Frame id="error-cert" label="cert/[code]/error.tsx">
          <ErrorSample which="cert" />
        </Frame>
        <Frame id="error-auth" label="(auth)/error.tsx">
          <div className="mx-auto w-full max-w-sm py-8">
            <ErrorSample which="auth" />
          </div>
        </Frame>
        <Frame id="error-instructor" label="giang-day/error.tsx">
          <ErrorSample which="instructor" />
        </Frame>
        <Frame id="error-admin" label="quan-tri/error.tsx">
          <div className="mx-auto max-w-5xl px-4 py-10">
            <ErrorSample which="admin" />
          </div>
        </Frame>
      </Group>

      <Group title="Đang tải">
        <Frame id="loading-catalogue" label="khoa-hoc/(danh-sach)/loading.tsx" wide>
          <CatalogueLoading />
        </Frame>
        <Frame id="loading-auth" label="(auth)/loading.tsx">
          <div className="mx-auto w-full max-w-sm py-8">
            <AuthLoading />
          </div>
        </Frame>
        <Frame id="loading-instructor" label="giang-day/loading.tsx">
          <InstructorLoading />
        </Frame>
        <Frame id="loading-instructor-qa" label="giang-day/hoi-dap/loading.tsx">
          <InstructorQaLoading />
        </Frame>
        <Frame id="loading-instructor-stats" label="giang-day/thong-ke/loading.tsx" wide>
          <InstructorStatsLoading />
        </Frame>
        <Frame id="loading-admin" label="quan-tri/loading.tsx">
          <div className="mx-auto max-w-5xl px-4 py-10">
            <AdminLoading />
          </div>
        </Frame>
      </Group>
    </main>
  );
}

function Group({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-4">
      <h2 className="text-h3">{title}</h2>
      <div className="grid gap-6 lg:grid-cols-2">{children}</div>
    </section>
  );
}

function Frame({ id, label, wide, children }: { id: string; label: string; wide?: boolean; children: ReactNode }) {
  return (
    <figure className={wide ? "min-w-0 lg:col-span-2" : "min-w-0"}>
      <figcaption className="mb-2 font-mono text-caption text-muted-foreground">{label}</figcaption>
      {/* `transform` makes the frame the containing block of anything fixed inside. */}
      <div data-testid={`state-${id}`} className="overflow-hidden rounded-lg border bg-background [transform:translateZ(0)]">
        {children}
      </div>
    </figure>
  );
}
