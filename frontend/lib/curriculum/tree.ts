/**
 * The curriculum as the builder holds it while a drag is in progress.
 *
 * All pure functions over a plain tree: the component decides *when* an
 * arrangement changes, these decide *what* it becomes. Keeping them apart is
 * what makes the drag handlers short enough to read.
 */

import { arrayMove } from "@dnd-kit/sortable";

import type { LessonSummary, SectionWithLessons } from "@/lib/api/curriculum";

export type Tree = SectionWithLessons[];

/**
 * Droppable id for the "chưa có bài học nào" area of a section. Prefixed so it
 * cannot collide with a row id, which is always a UUID.
 */
export const EMPTY_SLOT_PREFIX = "empty:";

export function emptySlotId(sectionId: string): string {
  return `${EMPTY_SLOT_PREFIX}${sectionId}`;
}

export function sectionOfLesson(
  tree: Tree,
  lessonId: string,
): SectionWithLessons | undefined {
  return tree.find((section) =>
    section.lessons.some((lesson) => lesson.id === lessonId),
  );
}

export function findLesson(tree: Tree, lessonId: string): LessonSummary | undefined {
  return sectionOfLesson(tree, lessonId)?.lessons.find(
    (lesson) => lesson.id === lessonId,
  );
}

/** Which section a drop lands in: over a lesson, a section, or an empty slot. */
export function sectionIdFromOver(tree: Tree, overId: string): string | undefined {
  if (overId.startsWith(EMPTY_SLOT_PREFIX)) {
    return overId.slice(EMPTY_SLOT_PREFIX.length);
  }
  if (tree.some((section) => section.id === overId)) return overId;
  return sectionOfLesson(tree, overId)?.id;
}

function withLessons(
  tree: Tree,
  sectionId: string,
  lessons: LessonSummary[],
): Tree {
  return tree.map((section) =>
    section.id === sectionId ? { ...section, lessons } : section,
  );
}

/**
 * Put the dragged lesson where it is being held.
 *
 * Used both while dragging -- so the row visibly leaves one section and joins
 * another -- and on drop, where the result is what gets saved.
 */
export function placeLesson(tree: Tree, activeId: string, overId: string): Tree {
  const from = sectionOfLesson(tree, activeId);
  const toId = sectionIdFromOver(tree, overId);
  if (from === undefined || toId === undefined) return tree;

  const to = tree.find((section) => section.id === toId);
  if (to === undefined) return tree;

  const overIndex = to.lessons.findIndex((lesson) => lesson.id === overId);

  if (from.id === to.id) {
    // Hovering your own section's header or empty area is not a request to
    // jump to the end -- it happens constantly on the way past.
    if (overIndex === -1) return tree;

    const oldIndex = from.lessons.findIndex((lesson) => lesson.id === activeId);
    if (oldIndex === overIndex) return tree;
    return withLessons(tree, to.id, arrayMove(to.lessons, oldIndex, overIndex));
  }

  const lesson = from.lessons.find((item) => item.id === activeId);
  if (lesson === undefined) return tree;

  // Over the section itself rather than one of its rows: the end of the list.
  const insertAt = overIndex === -1 ? to.lessons.length : overIndex;

  return tree.map((section) => {
    if (section.id === from.id) {
      return {
        ...section,
        lessons: section.lessons.filter((item) => item.id !== activeId),
      };
    }
    if (section.id === to.id) {
      return {
        ...section,
        lessons: [
          ...section.lessons.slice(0, insertAt),
          lesson,
          ...section.lessons.slice(insertAt),
        ],
      };
    }
    return section;
  });
}

export function placeSection(tree: Tree, activeId: string, overId: string): Tree {
  const toId = sectionIdFromOver(tree, overId);
  if (toId === undefined) return tree;

  const oldIndex = tree.findIndex((section) => section.id === activeId);
  const newIndex = tree.findIndex((section) => section.id === toId);
  if (oldIndex === -1 || newIndex === -1 || oldIndex === newIndex) return tree;

  return arrayMove(tree, oldIndex, newIndex);
}

/**
 * Renumber after a move, so the optimistic tree carries the same positions the
 * backend is about to write. Without this the UI would show stale numbers
 * until the refetch lands.
 */
export function renumber(tree: Tree): Tree {
  return tree.map((section, sectionIndex) => ({
    ...section,
    position: sectionIndex,
    lessons: section.lessons.map((lesson, lessonIndex) => ({
      ...lesson,
      position: lessonIndex,
    })),
  }));
}

export function sameOrder(before: string[], after: string[]): boolean {
  return before.length === after.length && before.every((id, i) => id === after[i]);
}
