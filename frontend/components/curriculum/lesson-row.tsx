"use client";

import { useDndContext } from "@dnd-kit/core";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Code2,
  FileText,
  GripVertical,
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

const TYPE_LABELS: Record<LessonType, string> = {
  video: "Video",
  article: "Bài đọc",
  quiz: "Trắc nghiệm",
  code_exercise: "Bài tập code",
};

const TYPE_ICONS: Record<LessonType, typeof FileText> = {
  video: Video,
  article: FileText,
  quiz: FileText,
  code_exercise: Code2,
};

function TypeIcon({ type }: { type: LessonType }) {
  const Icon = TYPE_ICONS[type];
  return <Icon className="size-4 shrink-0 text-muted-foreground" aria-hidden />;
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
      className={`rounded-lg border bg-background ${isDragging ? "opacity-40" : ""}`}
    >
      <div className="flex items-center gap-2 p-2">
        <Button
          ref={setActivatorNodeRef}
          variant="ghost"
          size="icon"
          className="cursor-grab touch-none active:cursor-grabbing"
          aria-label={`Kéo để sắp xếp bài học ${lesson.title}`}
          {...attributes}
          {...listeners}
        >
          <GripVertical aria-hidden />
        </Button>

        <TypeIcon type={lesson.type} />

        <span className="min-w-0 flex-1 truncate text-sm">{lesson.title}</span>

        <span className="hidden shrink-0 text-xs text-muted-foreground sm:inline">
          {TYPE_LABELS[lesson.type]}
        </span>

        {lesson.is_preview ? (
          <Badge variant="outline" className="shrink-0">
            Học thử
          </Badge>
        ) : null}

        <Button
          size="icon"
          variant="ghost"
          onClick={() => setOpen((current) => !current)}
          aria-expanded={open}
          aria-label={`Sửa bài học ${lesson.title}`}
        >
          <Pencil aria-hidden />
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
        <div className="flex flex-wrap items-center gap-2 border-t bg-destructive/5 px-3 py-2">
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
