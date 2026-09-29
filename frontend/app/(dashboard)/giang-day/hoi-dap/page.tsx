import type { Metadata } from "next";

import { QaInbox } from "@/components/instructor/qa-inbox";

export const metadata: Metadata = {
  title: "Hỏi đáp của học viên — DevPath",
  description: "Câu hỏi học viên đặt dưới các bài học trong khóa bạn dạy.",
};

/** `?cau-hoi=` opens one question; without it, the inbox. */
export default async function InstructorQaPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { "cau-hoi": raw } = await searchParams;
  const threadId = Array.isArray(raw) ? (raw[0] ?? null) : (raw ?? null);

  return (
    <div className="px-4 py-12">
      <QaInbox openThreadId={threadId} />
    </div>
  );
}
