"use client";

import { useQuery } from "@tanstack/react-query";
import { BookOpen, ChevronDown, Info, Sparkles, TrendingUp, Users } from "lucide-react";
import { useId, useState } from "react";

import { CourseCard, CourseRowCard } from "@/components/courses/course-card";
import {
  CourseBlock,
  CourseBlockSkeleton,
} from "@/components/recommendations/course-block";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { getRecommendations, type Recommendations } from "@/lib/api/recommendations";
import { useAuth } from "@/lib/auth/auth-provider";
import { formatDateTime } from "@/lib/format";
import { TAG_LABELS, recommendationReason, type Reason, type ReasonTag } from "@/lib/recommendations/reason";
import { cn } from "@/lib/utils";

const TITLE = "Gợi ý cho bạn";

const ICONS = { both: Sparkles, learners: Users, content: BookOpen, popular: TrendingUp } as const;

/**
 * "Gợi ý cho bạn" -- signed-in readers only: on the home page, and under the
 * list on "Khóa học của tôi" (`columns={2}`, beside the achievements).
 *
 * A Client Component because the answer is one person's history and needs
 * the access token, which only the browser holds. Nothing is drawn for a
 * signed-out visitor: there is no anonymous version of a recommendation, and
 * the catalogue one click away already is the "popular" list.
 *
 * Every card says why it is there and which half of the hybrid recommender
 * put it in ("Học viên giống bạn", "Nội dung gần", or the popular fallback),
 * and "Cách DevPath gợi ý" opens the three sources in plain words.
 */
export function RecommendedForYou({ columns = 4 }: { columns?: 2 | 4 }) {
  const { accessToken, status } = useAuth();
  const signedIn = status === "authenticated" && accessToken !== null;
  // One row: four on the home page, two pairs in the narrow column.
  const limit = 4;
  const [open, setOpen] = useState(false);
  const panelId = useId();

  const query = useQuery({
    queryKey: ["recommendations", limit],
    queryFn: () => getRecommendations(accessToken as string, limit),
    enabled: signedIn,
  });

  if (!signedIn) return null;

  if (query.isError) {
    return (
      <CourseBlock title={TITLE} columns={columns}>
        <p className="col-span-full text-sm text-muted-foreground">
          Chưa tải được gợi ý lúc này: {apiErrorMessage(query.error)}
        </p>
      </CourseBlock>
    );
  }

  if (!query.data) {
    return <CourseBlockSkeleton title={TITLE} count={columns === 2 ? 2 : limit} columns={columns} described notes />;
  }
  if (query.data.items.length === 0) return null;

  // A reader who has taken most of a small catalogue gets one or two courses
  // back: those lie on their side rather than leave the row mostly empty.
  const few = query.data.items.length <= 2;
  const Card = few ? CourseRowCard : CourseCard;

  return (
    <CourseBlock
      title={TITLE}
      description={describe(query.data)}
      layout={few ? "rows" : "grid"}
      columns={columns}
      action={
        <button
          type="button"
          aria-expanded={open}
          aria-controls={panelId}
          onClick={() => setOpen((value) => !value)}
          className={cn(
            "inline-flex h-8 items-center gap-1.5 rounded-md px-2.5 text-body-sm font-semibold text-link transition-colors duration-fast hover:bg-secondary",
            open && "bg-secondary text-secondary-foreground",
          )}
        >
          <Info className="size-4 shrink-0" aria-hidden />
          Cách DevPath gợi ý
          <ChevronDown
            className={cn("size-4 shrink-0 transition-transform duration-fast motion-reduce:transition-none", open && "rotate-180")}
            aria-hidden
          />
        </button>
      }
      intro={open ? <HowWeRecommend id={panelId} generatedAt={query.data.generated_at} /> : null}
    >
      {query.data.items.map((item) => {
        const reason = recommendationReason(item);
        return <Card key={item.id} course={item} note={<ReasonLine reason={reason} />} tags={<ReasonTags tags={reason.tags} />} />;
      })}
    </CourseBlock>
  );
}

/**
 * Where the row came from, said plainly. A block made only of popular
 * courses must not claim to know the reader: that is the fallback talking,
 * not the model.
 */
function describe(block: Recommendations): string {
  const personal = block.items.some((item) => !item.sources.includes("popular"));
  if (personal) {
    return "Dựa trên các khóa bạn đã học và lựa chọn của những học viên giống bạn.";
  }
  return block.generated_at === null
    ? "Bạn chưa có lịch sử học để gợi ý riêng — đây là những khóa được nhiều học viên chọn."
    : "Chưa có gợi ý mới từ lịch sử học của bạn — đây là những khóa được nhiều học viên chọn.";
}

/** The line on top of a card. Text only: it sits inside the card's link. */
function ReasonLine({ reason }: { reason: Reason }) {
  if (reason.text === null) return null;
  const Icon = ICONS[reason.icon];
  return (
    <>
      <Icon className="size-3.5 shrink-0" aria-hidden />
      <span className="line-clamp-1">{reason.text}</span>
    </>
  );
}

/** Which half of the hybrid put the card here. */
function ReasonTags({ tags }: { tags: ReasonTag[] }) {
  return (
    <span className="flex flex-wrap gap-1.5">
      {tags.map((tag) => {
        const Icon = ICONS[tag];
        return (
          <span
            key={tag}
            data-reason-tag={tag}
            className="inline-flex h-5.5 items-center gap-1 rounded-full border border-border-strong px-2 text-caption text-muted-foreground"
          >
            <Icon className="size-3 shrink-0" aria-hidden />
            {TAG_LABELS[tag]}
          </span>
        );
      })}
    </span>
  );
}

const SOURCES: { tag: ReasonTag; title: string; body: string }[] = [
  {
    tag: "learners",
    title: "Học viên giống bạn",
    body: "Những người học cùng khóa với bạn còn học khóa nào nữa.",
  },
  {
    tag: "content",
    title: "Nội dung gần",
    body: "Khóa có tên, mô tả và chủ đề gần với khóa bạn đã học.",
  },
  {
    tag: "popular",
    title: "Được nhiều người chọn",
    body: "Khi chưa đủ lịch sử học của bạn, chỗ trống được lấp bằng khóa phổ biến.",
  },
];

/** The three sources in plain words: what "Cách DevPath gợi ý" opens. */
function HowWeRecommend({ id, generatedAt }: { id: string; generatedAt: string | null }) {
  return (
    <div id={id} className="@container rounded-lg bg-muted p-4 sm:p-5">
      <ul className="grid gap-4 @2xl:grid-cols-3 @2xl:gap-6">
        {SOURCES.map((source) => {
          const Icon = ICONS[source.tag];
          return (
            <li key={source.tag} className="flex gap-3">
              <span className="flex size-9 shrink-0 items-center justify-center rounded-md bg-card text-link">
                <Icon className="size-4.5" aria-hidden />
              </span>
              <span className="flex min-w-0 flex-col gap-0.5">
                <span className="text-title">{source.title}</span>
                <span className="text-body-sm text-muted-foreground">{source.body}</span>
              </span>
            </li>
          );
        })}
      </ul>
      <p className="mt-4 border-t border-border-strong pt-3 text-caption text-muted-foreground">
        Hai nguồn đầu được trộn theo thứ hạng: khóa được cả hai cùng gợi ý thường đứng trước. Gợi ý
        được tính lại mỗi đêm
        {generatedAt ? `, lần gần nhất lúc ${formatDateTime(generatedAt)}` : ""}.
      </p>
    </div>
  );
}

