"use client";

import { useDndContext } from "@dnd-kit/core";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ChevronUp,
  Code2,
  FileText,
  GripVertical,
  ListChecks,
  Loader2,
  Pencil,
  Trash2,
  Video,
} from "lucide-react";
import { useState } from "react";

import { LessonEditor } from "@/components/curriculum/lesson-editor";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { deleteLesson, type LessonSummary, type LessonType } from "@/lib/api/curriculum";
import { useAuth } from "@/lib/auth/auth-provider";
import { cn } from "@/lib/utils";

const TYPE_LABELS: Record<LessonType, string> = {
  video: "Video",
  article: "Bài đọc",
  quiz: "Trắc nghiệm",
  code_exercise: "Bài tập code",
};

const TYPE_ICONS: Record<LessonType, typeof FileText> = {
  video: Video,
  article: FileText,
  quiz: ListChecks,
  code_exercise: Code2,
};

/** The lesson type as a small tile: plain, since a list of colours would shout over the titles. */
function TypeIcon({ type, open }: { type: LessonType; open: boolean }) {
  const Icon = TYPE_ICONS[type];
  return (
    <span
      className={cn(
        "flex size-7 shrink-0 items-center justify-center rounded-sm",
        open ? "bg-card text-secondary-foreground" : "bg-muted text-muted-foreground",
      )}
      aria-hidden
    >
      <Icon className="size-3.5" />
    </span>
  );
}

export function LessonRow({
  lesson,
  sectionId,
  courseId,
}: {
  lesson: LessonSummary;
  sectionId: string;
  courseId: string;
}) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  // A section being dragged travels over its own lessons, and every one of
  // them would otherwise answer as a drop target -- so moving a section by
  // keyboard would mean arrowing past each lesson inside it, one at a time.
  const { active } = useDndContext();
  const sectionIsMoving = active?.data.current?.type === "section";

  const {
    attributes,
    listeners,
    setNodeRef,
    setActivatorNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({
    id: lesson.id,
    data: { type: "lesson", sectionId },
    disabled: { draggable: false, droppable: sectionIsMoving },
  });

  const remove = useMutation({
    mutationFn: () => deleteLesson(accessToken as string, lesson.id),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["curriculum", courseId] }),
  });

  return (
    <li
      ref={setNodeRef}
      style={{ transform: CSS.Translate.toString(transform), transition }}
      className={cn(
        "overflow-hidden rounded-md border bg-card",
        open && "border-primary",
        isDragging && "opacity-40",
      )}
    >
      <div className={cn("flex items-center gap-1.5 py-1.5 pr-1.5 pl-1 sm:gap-2", open && "bg-secondary")}>
        <Button
          ref={setActivatorNodeRef}
          variant="ghost"
          size="icon"
          className="cursor-grab touch-none text-muted-foreground active:cursor-grabbing"
          aria-label={`Kéo để sắp xếp bài học ${lesson.title}`}
          {...attributes}
          {...listeners}
        >
          <GripVertical aria-hidden />
        </Button>

        <TypeIcon type={lesson.type} open={open} />

        {/* A column on a phone: beside the badge and three buttons, one line
            left the title three letters wide. */}
        <span className="flex min-w-0 flex-1 flex-col items-start gap-1 sm:flex-row sm:items-center sm:gap-2">
          <span
            className={cn(
              "line-clamp-2 min-w-0 text-body-sm sm:flex-1 sm:truncate sm:text-[0.9375rem]",
              open && "font-semibold",
            )}
          >
            {lesson.title}
          </span>

          <span className="hidden shrink-0 text-caption text-muted-foreground sm:inline">
            {TYPE_LABELS[lesson.type]}
            {open ? " · đang sửa" : ""}
          </span>

          {lesson.is_preview ? (
            <Badge variant="outline" className="shrink-0">
              Học thử
            </Badge>
          ) : null}
        </span>

        <Button
          size="icon"
          variant="ghost"
          onClick={() => setOpen((current) => !current)}
          aria-expanded={open}
          aria-label={`Sửa bài học ${lesson.title}`}
        >
          {open ? <ChevronUp aria-hidden /> : <Pencil aria-hidden />}
        </Button>
        <Button
          size="icon"
          variant="ghost"
          onClick={() => setConfirmingDelete(true)}
          aria-label={`Xóa bài học ${lesson.title}`}
        >
          <Trash2 aria-hidden />
        </Button>
      </div>

      {confirmingDelete ? (
        <div className="flex flex-wrap items-center gap-2 border-t bg-destructive-soft px-3 py-2.5">
          <span className="text-sm">Xóa bài học này?</span>
          <Button
            size="sm"
            variant="destructive"
            onClick={() => remove.mutate()}
            disabled={remove.isPending}
          >
            {remove.isPending ? (
              <>
                <Loader2 className="animate-spin" aria-hidden />
                Đang xóa…
              </>
            ) : (
              "Xóa"
            )}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setConfirmingDelete(false)}
            disabled={remove.isPending}
          >
            Hủy
          </Button>
        </div>
      ) : null}

      {remove.isError ? (
        <div className="px-3 pb-3">
          <Alert variant="destructive">
            <AlertDescription>{apiErrorMessage(remove.error)}</AlertDescription>
          </Alert>
        </div>
      ) : null}

      {open ? (
        <LessonEditor
          lessonId={lesson.id}
          courseId={courseId}
          onClose={() => setOpen(false)}
        />
      ) : null}
    </li>
  );
}
