"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Award,
  Bell,
  CircleCheck,
  CircleX,
  EyeOff,
  GraduationCap,
  MessageCircleQuestion,
  MessageSquareReply,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";

import {
  markAllNotificationsRead,
  markNotificationRead,
  type AppNotification,
} from "@/lib/api/notifications";
import { useAuth } from "@/lib/auth/auth-provider";
import { formatRelativeTime } from "@/lib/format";
import { cn } from "@/lib/utils";

/** Every notification query sits under this key: the bell, its count, the page. */
export const NOTIFICATIONS_KEY = ["notifications"] as const;

interface Described {
  icon: LucideIcon;
  /** The sentence, with the quoted title picked out. */
  lead: string;
  quote: string | null;
  tail: string;
  href: string;
}

/**
 * A notification as a sentence and a place to go.
 *
 * Built here rather than on the server because the links are this app's
 * routes. The `default` branch is for a type the backend learned after this
 * page was built: it still gets a line, and the page is where it leads.
 */
export function describe(notification: AppNotification): Described {
  switch (notification.type) {
    case "qa_reply": {
      const p = notification.payload;
      return {
        icon: MessageSquareReply,
        lead: `${p.replier_name}${p.is_instructor_reply ? " (giảng viên)" : ""} đã trả lời câu hỏi `,
        quote: p.thread_title,
        tail: " của bạn",
        href: `/hoc/${p.course_slug}?bai=${p.lesson_id}&hoi-dap=${p.thread_id}`,
      };
    }
    case "qa_question": {
      const p = notification.payload;
      return {
        icon: MessageCircleQuestion,
        lead: `${p.asker_name} đặt câu hỏi `,
        quote: p.thread_title,
        tail: ` trong ${p.course_title} · ${p.lesson_title}`,
        href: `/giang-day/hoi-dap?cau-hoi=${p.thread_id}`,
      };
    }
    case "course_approved": {
      const p = notification.payload;
      return {
        icon: CircleCheck,
        lead: "Khóa học ",
        quote: p.course_title,
        tail: " đã được duyệt và đang hiển thị công khai",
        href: `/giang-day/${p.course_id}`,
      };
    }
    case "course_rejected": {
      const p = notification.payload;
      return {
        icon: CircleX,
        lead: "Khóa học ",
        quote: p.course_title,
        tail: ` bị từ chối: ${clip(p.reason)}`,
        href: `/giang-day/${p.course_id}`,
      };
    }
    case "course_taken_down": {
      const p = notification.payload;
      return {
        icon: EyeOff,
        lead: "Khóa học ",
        quote: p.course_title,
        tail: ` đã bị gỡ khỏi trang công khai: ${clip(p.reason)}`,
        href: `/giang-day/${p.course_id}`,
      };
    }
    case "instructor_tier_changed": {
      const p = notification.payload;
      const up = p.to_rank > p.from_rank;
      return {
        icon: Award,
        lead: up ? "Chúc mừng! Bạn đã lên cấp " : "Cấp giảng viên của bạn đổi thành ",
        quote: p.to_tier,
        tail: ` (nhận ${Math.round(Number(p.share_rate) * 100)}% mỗi lượt bán): ${clip(p.note)}`,
        href: "/giang-day/cap-bac",
      };
    }
    case "instructor_application_approved":
      return {
        icon: GraduationCap,
        lead: "Yêu cầu trở thành giảng viên của bạn đã được duyệt. Vào khu giảng dạy để tạo khóa học đầu tiên",
        quote: null,
        tail: "",
        href: "/giang-day",
      };
    case "instructor_application_rejected":
      return {
        icon: CircleX,
        lead: "Yêu cầu trở thành giảng viên chưa được duyệt: ",
        quote: null,
        tail: clip(notification.payload.reason),
        href: "/tro-thanh-giang-vien",
      };
    default:
      return {
        icon: Bell,
        lead: "Bạn có một thông báo mới",
        quote: null,
        tail: "",
        href: "/thong-bao",
      };
  }
}

/** A reason is written for the course page; the bell only needs its start. */
function clip(text: string, max = 140): string {
  return text.length <= max ? text : `${text.slice(0, max - 1).trimEnd()}…`;
}

/** Marking read, shared by the bell and the page so both refresh everything. */
export function useMarkRead() {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();

  const one = useMutation({
    mutationFn: (id: string) => markNotificationRead(accessToken as string, id),
    onSettled: () => queryClient.invalidateQueries({ queryKey: NOTIFICATIONS_KEY }),
  });
  const all = useMutation({
    mutationFn: () => markAllNotificationsRead(accessToken as string),
    onSettled: () => queryClient.invalidateQueries({ queryKey: NOTIFICATIONS_KEY }),
  });
  return { one, all };
}

/** What a notification says: icon, sentence, when, and a dot while unread. */
export function NotificationBody({ notification }: { notification: AppNotification }) {
  const { icon: Icon, lead, quote, tail } = describe(notification);
  const unread = notification.read_at === null;

  return (
    <>
      <Icon className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
      <span className="min-w-0 flex-1 space-y-0.5">
        <span className={cn("block break-words whitespace-normal", unread && "font-medium")}>
          {lead}
          {quote ? <>“{quote}”</> : null}
          {tail}
        </span>
        <span className="block text-xs text-muted-foreground">
          {formatRelativeTime(notification.created_at)}
        </span>
      </span>
      {unread ? (
        <span className="mt-1.5 size-2 shrink-0 rounded-full bg-primary" aria-label="Chưa đọc" />
      ) : null}
    </>
  );
}

/**
 * One notification as a link, for the page. Following it marks it read --
 * that is the moment the person has seen what it was about.
 */
export function NotificationLink({
  notification,
  onFollow,
}: {
  notification: AppNotification;
  onFollow: (notification: AppNotification) => void;
}) {
  return (
    <Link
      href={describe(notification).href}
      onClick={() => onFollow(notification)}
      className={cn(
        "flex w-full items-start gap-3 rounded-md p-3 text-left text-sm transition-colors hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none",
        notification.read_at === null && "bg-primary/5",
      )}
    >
      <NotificationBody notification={notification} />
    </Link>
  );
}
