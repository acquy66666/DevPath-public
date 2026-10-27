"use client";

import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { CourseDeleteCard } from "@/components/instructor/course-delete-card";
import { CourseDetailsForm } from "@/components/instructor/course-details-form";
import { CourseOutlineCard } from "@/components/instructor/course-outline-card";
import { CourseStatusBadge } from "@/components/instructor/course-status-badge";
import { CourseStatusCard } from "@/components/instructor/course-status-card";
import { CourseEditorBodySkeleton } from "@/components/instructor/instructor-skeletons";
import { CurriculumBuilder } from "@/components/curriculum/curriculum-builder";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { getCourse } from "@/lib/api/courses";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { useAuth } from "@/lib/auth/auth-provider";

export type EditorTab = "noi-dung" | "thong-tin";

/**
 * One page for one course: what is in it, what it says about itself, and
 * whether it is live.
 *
 * Two tabs, because they are two jobs: the curriculum is the work of weeks,
 * the details a few minutes at the end. Where the course stands sits beside
 * both, so "Gửi duyệt" and an admin's reason are never a scroll away. The tab
 * is in the URL (`?tab=thong-tin`) so the overview can link to a rejected
 * course's reason; both panels stay mounted, so a half-edited lesson survives
 * a look at the other tab.
 */
export function CourseEditor({ courseId, initialTab }: { courseId: string; initialTab: EditorTab }) {
  const { accessToken } = useAuth();
  const [tab, setTab] = useState<EditorTab>(initialTab);

  const query = useQuery({
    queryKey: ["course", courseId],
    queryFn: () => getCourse(courseId, accessToken),
    enabled: accessToken !== null,
  });

  function choose(next: string) {
    const value = next as EditorTab;
    setTab(value);
    // The address only, without a navigation: nothing on the page needs to load again.
    const url = new URL(window.location.href);
    if (value === "noi-dung") url.searchParams.delete("tab");
    else url.searchParams.set("tab", value);
    window.history.replaceState(window.history.state, "", url);
  }

  if (query.isPending) return <CourseEditorBodySkeleton />;

  if (query.isError) {
    return (
      <div className="space-y-4">
        <Alert variant="destructive">
          <AlertDescription>{apiErrorMessage(query.error)}</AlertDescription>
        </Alert>
        <Link href="/giang-day" className="text-body-sm text-link underline-offset-4 hover:underline">
          Về danh sách khóa học
        </Link>
      </div>
    );
  }

  const course = query.data;

  return (
    <div className="space-y-5">
      <div className="space-y-2.5">
        <nav aria-label="Vị trí" className="text-body-sm text-muted-foreground">
          <ol className="flex min-w-0 items-center gap-1.5">
            <li>
              <Link href="/giang-day" className="hover:text-foreground hover:underline">
                Khóa học
              </Link>
            </li>
            <li aria-hidden>/</li>
            <li className="min-w-0 truncate text-foreground" aria-current="page">
              {course.title}
            </li>
          </ol>
        </nav>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <h1 className="text-h2 text-pretty break-words sm:text-h1">{course.title}</h1>
          <CourseStatusBadge status={course.status} />
          {/* Only once published: before that the public page answers 404 to
              everyone the server can identify, which is nobody — it renders
              anonymously. */}
          {course.status === "published" ? (
            <Link
              href={`/khoa-hoc/${course.slug}`}
              className="inline-flex items-center gap-1.5 text-body-sm font-medium text-link hover:underline sm:ml-auto"
            >
              Xem trang công khai
              <ExternalLink className="size-3.5" aria-hidden />
            </Link>
          ) : null}
        </div>
      </div>

      <Tabs value={tab} onValueChange={choose} className="gap-5">
        <TabsList variant="line" aria-label="Soạn khóa học">
          <TabsTrigger value="noi-dung" className="text-[0.9375rem]">
            Nội dung
          </TabsTrigger>
          <TabsTrigger value="thong-tin" className="text-[0.9375rem]">
            Thông tin khóa học
          </TabsTrigger>
        </TabsList>

        <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_18.75rem]">
          <div className="min-w-0">
            <TabsContent value="noi-dung" forceMount className="data-[state=inactive]:hidden">
              <CurriculumBuilder courseId={course.id} />
            </TabsContent>
            <TabsContent value="thong-tin" forceMount className="space-y-5 data-[state=inactive]:hidden">
              <CourseDetailsForm course={course} />
              <CourseDeleteCard course={course} />
            </TabsContent>
          </div>

          <aside className="space-y-4 lg:sticky lg:top-6" aria-label="Tình trạng khóa học">
            <CourseStatusCard course={course} />
            <CourseOutlineCard courseId={course.id} />
          </aside>
        </div>
      </Tabs>
    </div>
  );
}
