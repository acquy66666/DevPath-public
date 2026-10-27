"use client";

import { useDndContext, useDroppable } from "@dnd-kit/core";
import { SortableContext, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, GripVertical, Loader2, Pencil, Trash2, X } from "lucide-react";
import { useState } from "react";

import { AddLessonForm } from "@/components/curriculum/add-lesson-form";
import { LessonRow } from "@/components/curriculum/lesson-row";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { deleteSection, updateSection, type SectionWithLessons } from "@/lib/api/curriculum";
import { useAuth } from "@/lib/auth/auth-provider";
import { emptySlotId } from "@/lib/curriculum/tree";
import { validateSectionTitle } from "@/lib/courses/validation";
import { sectionSummary } from "@/lib/instructor/teaching-view";

export function SectionCard({
  section,
  index,
  courseId,
}: {
  section: SectionWithLessons;
  index: number;
  courseId: string;
}) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const queryKey = ["curriculum", courseId];

  const [renaming, setRenaming] = useState(false);
  const [title, setTitle] = useState(section.title);
  const [titleError, setTitleError] = useState<string | null>(null);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  const { attributes, listeners, setNodeRef, setActivatorNodeRef, transform, transition, isDragging } =
    useSortable({ id: section.id, data: { type: "section" } });

  const rename = useMutation({
    mutationFn: () => updateSection(accessToken as string, section.id, title.trim()),
    onSuccess: () => {
      setRenaming(false);
      queryClient.invalidateQueries({ queryKey });
    },
  });

  const remove = useMutation({
    mutationFn: () => deleteSection(accessToken as string, section.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
  });

  function submitRename() {
    const error = validateSectionTitle(title);
    setTitleError(error);
    if (error) return;
    rename.mutate();
  }

  const error = rename.error ?? remove.error;

  return (
    <li
      ref={setNodeRef}
      style={{ transform: CSS.Translate.toString(transform), transition }}
      // The floating copy in the DragOverlay stands in for the row while it is
      // being dragged; leaving both at full opacity reads as two rows.
      className={`rounded-lg border bg-card ${isDragging ? "opacity-40" : ""}`}
    >
      <div className="flex items-start gap-1.5 border-b py-3 pr-3 pl-2 sm:items-center sm:gap-2">
        <Button
          ref={setActivatorNodeRef}
          variant="ghost"
          size="icon"
          className="cursor-grab touch-none active:cursor-grabbing"
          aria-label={`Kéo để sắp xếp chương ${section.title}`}
          {...attributes}
          {...listeners}
        >
          <GripVertical aria-hidden />
        </Button>

        <div className="min-w-0 flex-1 pt-0.5 sm:pt-0">
          <p className="text-eyebrow text-muted-foreground">Chương {index + 1}</p>

          {renaming ? (
            <div className="mt-1 flex items-start gap-2">
              <div className="flex-1">
                <Input
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      event.preventDefault();
                      submitRename();
                    }
                    if (event.key === "Escape") {
                      setRenaming(false);
                      setTitle(section.title);
                    }
                  }}
                  aria-label="Tên chương"
                  aria-invalid={Boolean(titleError)}
                  autoFocus
                />
                {titleError ? (
                  <p className="mt-1 text-sm text-destructive-text">{titleError}</p>
                ) : null}
              </div>
              <Button
                size="icon"
                variant="ghost"
                onClick={submitRename}
                disabled={rename.isPending}
                aria-label="Lưu tên chương"
              >
                {rename.isPending ? (
                  <Loader2 className="animate-spin" aria-hidden />
                ) : (
                  <Check aria-hidden />
                )}
              </Button>
              <Button
                size="icon"
                variant="ghost"
                onClick={() => {
                  setRenaming(false);
                  setTitle(section.title);
                  setTitleError(null);
                }}
                aria-label="Hủy đổi tên"
              >
                <X aria-hidden />
              </Button>
            </div>
          ) : (
            <h3 className="text-title text-pretty break-words">{section.title}</h3>
          )}

          <p className="mt-0.5 text-caption text-muted-foreground lg:hidden">
            {sectionSummary(section)}
          </p>
        </div>

        {!renaming ? (
          <p className="hidden shrink-0 text-caption text-muted-foreground lg:block">
            {sectionSummary(section)}
          </p>
        ) : null}

        {!renaming ? (
          <div className="flex shrink-0 items-center gap-1">
            <Button
              size="icon"
              variant="ghost"
              onClick={() => setRenaming(true)}
              aria-label={`Đổi tên chương ${section.title}`}
            >
              <Pencil aria-hidden />
            </Button>
            <Button
              size="icon"
              variant="ghost"
              onClick={() => setConfirmingDelete(true)}
              aria-label={`Xóa chương ${section.title}`}
            >
              <Trash2 aria-hidden />
            </Button>
          </div>
        ) : null}
      </div>

      {confirmingDelete ? (
        <div className="flex flex-wrap items-center gap-2 border-b bg-destructive-soft px-3 py-2.5">
          <span className="text-sm">
            Xóa chương này cùng {section.lessons.length} bài học trong đó?
          </span>
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

      {error ? (
        <div className="px-3 pt-3">
          <Alert variant="destructive">
            <AlertDescription>{apiErrorMessage(error)}</AlertDescription>
          </Alert>
        </div>
      ) : null}

      <div className="space-y-2 p-2 sm:p-3">
        <SortableContext
          items={section.lessons.map((lesson) => lesson.id)}
          strategy={verticalListSortingStrategy}
        >
          <ul className="space-y-1.5">
            {section.lessons.map((lesson) => (
              <LessonRow
                key={lesson.id}
                lesson={lesson}
                sectionId={section.id}
                courseId={courseId}
              />
            ))}
          </ul>
        </SortableContext>

        {section.lessons.length === 0 ? <EmptyLessonSlot sectionId={section.id} /> : null}

        <AddLessonForm sectionId={section.id} courseId={courseId} />
      </div>
    </li>
  );
}

/**
 * A drop target for a section with nothing in it.
 *
 * Without it an empty section has no row to hover, so there would be no way to
 * drag the first lesson into it -- the one case where dropping matters most.
 */
function EmptyLessonSlot({ sectionId }: { sectionId: string }) {
  const { active } = useDndContext();
  const { setNodeRef, isOver } = useDroppable({
    id: emptySlotId(sectionId),
    // Nothing to receive while a section is the thing being moved.
    disabled: active?.data.current?.type === "section",
  });

  return (
    <div
      ref={setNodeRef}
      className={`rounded-md border border-dashed border-border-strong px-3 py-4 text-center text-body-sm text-muted-foreground transition-colors ${
        isOver ? "border-primary bg-secondary text-foreground" : ""
      }`}
    >
      Chưa có bài học nào — thêm bên dưới, hoặc kéo một bài từ chương khác vào đây.
    </div>
  );
}
