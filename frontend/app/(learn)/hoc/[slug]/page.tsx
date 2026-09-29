import type { Metadata } from "next";

import { LearnView } from "@/components/learn/learn-view";

export const metadata: Metadata = {
  title: "Đang học — DevPath",
  // Everything on this page belongs to one enrolled reader, and a crawler is
  // signed in as nobody.
  robots: { index: false },
};

/**
 * `?bai=` picks the lesson, and `?hoi-dap=` opens one of its questions. A query parameter rather than another path segment
 * because the lesson is a position inside this page, not a page of its own --
 * and because it keeps one component in charge of the player, the table of
 * contents and the progress they share.
 */
export default async function LearnPage({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { slug } = await params;
  const query = await searchParams;
  const lessonId = first(query.bai);
  const threadId = first(query["hoi-dap"]);

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <LearnView slug={slug} lessonId={lessonId} threadId={threadId} />
    </div>
  );
}

function first(value: string | string[] | undefined): string | null {
  return Array.isArray(value) ? (value[0] ?? null) : (value ?? null);
}
