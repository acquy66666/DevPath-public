"use client";

import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  MeasuringStrategy,
  PointerSensor,
  closestCorners,
  useSensor,
  useSensors,
  type Announcements,
  type DragEndEvent,
  type DragOverEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { restrictToVerticalAxis } from "@dnd-kit/modifiers";
import {
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { GripVertical, ListTree } from "lucide-react";
import { useMemo, useState } from "react";

import { AddSectionForm } from "@/components/curriculum/add-section-form";
import { SectionCard } from "@/components/curriculum/section-card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { apiErrorMessage } from "@/lib/api/error-messages";
import {
  getCurriculum,
  reorderLessons,
  reorderSections,
} from "@/lib/api/curriculum";
import { useAuth } from "@/lib/auth/auth-provider";
import {
  EMPTY_SLOT_PREFIX,
  findLesson,
  placeLesson,
  placeSection,
  renumber,
  sameOrder,
  sectionIdFromOver,
  sectionOfLesson,
  type Tree,
} from "@/lib/curriculum/tree";

/** Stable empty array: a fresh `[]` per render would restart every memo below. */
const NO_SECTIONS: Tree = [];

export function CurriculumBuilder({ courseId }: { courseId: string }) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const queryKey = ["curriculum", courseId];

  const query = useQuery({
    queryKey,
    queryFn: () => getCurriculum(courseId, accessToken),
    enabled: accessToken !== null,
  });

  /**
   * While a drag is running the tree lives here, so a lesson can visibly leave
   * one section and join another before anything is saved. The rest of the
   * time the query cache is the single source of truth.
   */
  const [dragTree, setDragTree] = useState<Tree | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [orderError, setOrderError] = useState<string | null>(null);

  const tree = dragTree ?? query.data?.sections ?? NO_SECTIONS;

  const sensors = useSensors(
    // The row carries buttons; dragging starts from the grip handle only, so
    // no activation distance is needed to tell a click from a drag.
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  function saveOptimistically(next: Tree) {
    queryClient.setQueryData(queryKey, { sections: next });
    setDragTree(null);
  }

  function handleOrderError(error: unknown) {
    setOrderError(apiErrorMessage(error));
  }

  const sectionOrder = useMutation({
    mutationFn: (sectionIds: string[]) =>
      reorderSections(accessToken as string, courseId, sectionIds),
    onSuccess: () => setOrderError(null),
    onError: handleOrderError,
    // Whatever happened, the server's numbering is the one that counts.
    onSettled: () => queryClient.invalidateQueries({ queryKey }),
  });

  const lessonOrder = useMutation({
    mutationFn: (input: { sectionId: string; lessonIds: string[] }) =>
      reorderLessons(accessToken as string, input.sectionId, input.lessonIds),
    onSuccess: () => setOrderError(null),
    onError: handleOrderError,
    onSettled: () => queryClient.invalidateQueries({ queryKey }),
  });

  function handleDragStart(event: DragStartEvent) {
    setActiveId(String(event.active.id));
    setDragTree(query.data?.sections ?? NO_SECTIONS);
  }

  /**
   * Only cross-section moves need handling here: inside one section dnd-kit
   * animates the rows itself. Moving a lesson to another section, on the other
   * hand, is a change to the tree, and without it the row would hover over a
   * section it has not joined.
   */
  function handleDragOver(event: DragOverEvent) {
    const { active, over } = event;
    if (over === null || active.data.current?.type !== "lesson") return;

    const from = sectionOfLesson(tree, String(active.id));
    const to = sectionIdFromOver(tree, String(over.id));
    if (from === undefined || to === undefined || from.id === to) return;

    setDragTree(placeLesson(tree, String(active.id), String(over.id)));
  }

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    setActiveId(null);

    if (over === null) {
      setDragTree(null);
      return;
    }

    const activeDragId = String(active.id);
    const overId = String(over.id);

    if (active.data.current?.type === "section") {
      const next = renumber(placeSection(tree, activeDragId, overId));
      const before = (query.data?.sections ?? NO_SECTIONS).map(
        (section) => section.id,
      );
      const after = next.map((section) => section.id);

      if (sameOrder(before, after)) {
        setDragTree(null);
        return;
      }

      saveOptimistically(next);
      sectionOrder.mutate(after);
      return;
    }

    const next = renumber(placeLesson(tree, activeDragId, overId));
    const target = sectionOfLesson(next, activeDragId);
    if (target === undefined) {
      setDragTree(null);
      return;
    }

    const serverSections = query.data?.sections ?? NO_SECTIONS;
    const before = serverSections.find((section) => section.id === target.id);
    const after = target.lessons.map((lesson) => lesson.id);

    // Same section, same order: the drag went nowhere and a PUT would only be
    // a round trip that rewrites the numbers they already have.
    if (before && sameOrder(before.lessons.map((lesson) => lesson.id), after)) {
      setDragTree(null);
      return;
    }

    saveOptimistically(next);
    lessonOrder.mutate({ sectionId: target.id, lessonIds: after });
  }

  const announcements = useMemo(() => buildAnnouncements(tree), [tree]);

  const activeSection = tree.find((section) => section.id === activeId);
  const activeLesson = activeId ? findLesson(tree, activeId) : undefined;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Nội dung khóa học</CardTitle>
        <CardDescription>
          Kéo tay nắm{" "}
          <GripVertical className="inline size-4 align-text-bottom" aria-hidden /> để
          sắp xếp lại. Dùng bàn phím: chọn tay nắm, bấm phím cách, di chuyển bằng phím
          mũi tên rồi bấm phím cách lần nữa để thả.
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4">
        {orderError ? (
          <Alert variant="destructive">
            <AlertDescription>{orderError}</AlertDescription>
          </Alert>
        ) : null}

        {query.isPending ? (
          <div className="space-y-3">
            {[0, 1].map((row) => (
              <div
                key={row}
                className="h-28 animate-pulse rounded-lg border bg-muted/40"
              />
            ))}
          </div>
        ) : query.isError ? (
          <Alert variant="destructive">
            <AlertDescription>{apiErrorMessage(query.error)}</AlertDescription>
          </Alert>
        ) : tree.length === 0 ? (
          <EmptyCurriculum />
        ) : (
          <DndContext
            sensors={sensors}
            collisionDetection={closestCorners}
            modifiers={[restrictToVerticalAxis]}
            // Sections change size as lessons move between them; without
            // continuous measuring the drop targets go stale mid-drag.
            measuring={{ droppable: { strategy: MeasuringStrategy.Always } }}
            accessibility={{ announcements }}
            onDragStart={handleDragStart}
            onDragOver={handleDragOver}
            onDragEnd={handleDragEnd}
            onDragCancel={() => {
              setActiveId(null);
              setDragTree(null);
            }}
          >
            <SortableContext
              items={tree.map((section) => section.id)}
              strategy={verticalListSortingStrategy}
            >
              <ul className="space-y-3">
                {tree.map((section, index) => (
                  <SectionCard
                    key={section.id}
                    section={section}
                    index={index}
                    courseId={courseId}
                  />
                ))}
              </ul>
            </SortableContext>

            <DragOverlay>
              {activeSection ? (
                <div className="rounded-lg border bg-card px-4 py-3 shadow-lg">
                  <p className="font-medium">{activeSection.title}</p>
                  <p className="text-xs text-muted-foreground">
                    {activeSection.lessons.length} bài học
                  </p>
                </div>
              ) : activeLesson ? (
                <div className="rounded-md border bg-card px-3 py-2 text-sm shadow-lg">
                  {activeLesson.title}
                </div>
              ) : null}
            </DragOverlay>
          </DndContext>
        )}

        <AddSectionForm courseId={courseId} sectionCount={tree.length} />
      </CardContent>
    </Card>
  );
}

function EmptyCurriculum() {
  return (
    <div className="rounded-lg border border-dashed px-4 py-10 text-center">
      <div className="mx-auto mb-3 flex size-10 items-center justify-center rounded-md bg-muted">
        <ListTree className="size-5 text-muted-foreground" aria-hidden />
      </div>
      <p className="font-medium">Chưa có chương nào</p>
      <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">
        Khóa học được chia thành chương, mỗi chương chứa các bài học. Tạo chương đầu
        tiên bên dưới — ví dụ &quot;Nhập môn&quot;.
      </p>
    </div>
  );
}

/**
 * What a screen reader hears during a drag.
 *
 * dnd-kit's defaults are in English and read out the item's id -- which here is
 * a UUID. These say the title instead, in the same language as the rest of the
 * page, because for a keyboard drag this narration *is* the interface.
 */
function buildAnnouncements(tree: Tree): Announcements {
  const label = (rawId: string): string => {
    const id = rawId.startsWith(EMPTY_SLOT_PREFIX)
      ? rawId.slice(EMPTY_SLOT_PREFIX.length)
      : rawId;

    const section = tree.find((item) => item.id === id);
    if (section) return `chương “${section.title}”`;

    const lesson = findLesson(tree, id);
    return lesson ? `bài học “${lesson.title}”` : "mục này";
  };

  return {
    onDragStart: ({ active }) =>
      `Đã nhấc ${label(String(active.id))}. Dùng phím mũi tên để di chuyển, phím cách để thả, Escape để hủy.`,
    onDragOver: ({ active, over }) =>
      over
        ? `${label(String(active.id))} đang ở vị trí của ${label(String(over.id))}.`
        : `${label(String(active.id))} đang ở ngoài vùng thả được.`,
    onDragEnd: ({ active, over }) =>
      over
        ? `Đã thả ${label(String(active.id))} tại ${label(String(over.id))} và lưu thứ tự mới.`
        : `Đã hủy, thứ tự giữ nguyên.`,
    onDragCancel: ({ active }) =>
      `Đã hủy di chuyển ${label(String(active.id))}, thứ tự giữ nguyên.`,
  };
}
