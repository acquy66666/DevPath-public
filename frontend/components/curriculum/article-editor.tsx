"use client";

import {
  Bold,
  Code,
  Heading2,
  ImagePlus,
  Italic,
  Link2,
  List,
  ListOrdered,
  Loader2,
  Maximize2,
  Minimize2,
  Quote,
  SquareCode,
  Table,
  type LucideIcon,
} from "lucide-react";
import {
  useEffect,
  useRef,
  useState,
  type ClipboardEvent,
  type Dispatch,
  type DragEvent,
  type KeyboardEvent,
  type SetStateAction,
} from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Markdown } from "@/components/ui/markdown";
import { Textarea } from "@/components/ui/textarea";
import { apiErrorMessage } from "@/lib/api/error-messages";
import { createLessonImageUpload } from "@/lib/api/lesson-images";
import { UploadError, uploadToStorage } from "@/lib/api/storage";
import { useAuth } from "@/lib/auth/auth-provider";
import {
  applyReplacement,
  BULLETS,
  codeBlock,
  HEADING,
  imageMarkdown,
  insertBlock,
  link,
  NUMBERS,
  prefixLines,
  QUOTE,
  replaceOnce,
  table,
  wrapInline,
  type Replacement,
  type Selection,
} from "@/lib/markdown/editing";
import {
  defaultAltText,
  LESSON_IMAGE_TYPES,
  lessonImageProblem,
  UPLOAD_PLACEHOLDER_PREFIX,
} from "@/lib/markdown/images";
import { cn } from "@/lib/utils";

type Mode = "write" | "preview";

interface Tool {
  label: string;
  /** Shown in the tooltip, so the shortcut is discoverable. */
  shortcut?: string;
  icon: LucideIcon;
  run: (text: string, selection: Selection) => Replacement;
}

const TOOLS: Tool[][] = [
  [
    {
      label: "Tiêu đề",
      icon: Heading2,
      run: (t, s) => prefixLines(t, s, HEADING.prefix, HEADING.pattern, HEADING.replaces),
    },
    {
      label: "Chữ đậm",
      shortcut: "Ctrl+B",
      icon: Bold,
      run: (t, s) => wrapInline(t, s, "**", "chữ đậm"),
    },
    {
      label: "Chữ nghiêng",
      shortcut: "Ctrl+I",
      icon: Italic,
      run: (t, s) => wrapInline(t, s, "_", "chữ nghiêng"),
    },
  ],
  [
    {
      label: "Danh sách",
      icon: List,
      run: (t, s) => prefixLines(t, s, BULLETS.prefix, BULLETS.pattern, BULLETS.replaces),
    },
    {
      label: "Danh sách đánh số",
      icon: ListOrdered,
      run: (t, s) => prefixLines(t, s, NUMBERS.prefix, NUMBERS.pattern, NUMBERS.replaces),
    },
    {
      label: "Trích dẫn",
      icon: Quote,
      run: (t, s) => prefixLines(t, s, QUOTE.prefix, QUOTE.pattern, QUOTE.replaces),
    },
  ],
  [
    { label: "Code trong dòng", icon: Code, run: (t, s) => wrapInline(t, s, "`", "code") },
    { label: "Khối code", icon: SquareCode, run: codeBlock },
    { label: "Bảng", icon: Table, run: table },
    { label: "Liên kết", shortcut: "Ctrl+K", icon: Link2, run: link },
  ],
];

const SHORTCUTS: Record<string, Tool> = {
  b: TOOLS[0][1],
  i: TOOLS[0][2],
  k: TOOLS[2][3],
};

/**
 * The article editor: Markdown on one side, the page a student will see on
 * the other.
 *
 * Still Markdown underneath -- the lesson stores it, the chatbot chunks it,
 * and the preview is drawn by the very `<Markdown>` the lesson page uses, so
 * what the instructor sees is what the student gets. The toolbar only writes
 * the syntax; it never hides it.
 *
 * Pictures go in by pasting, dropping, or the picture button. Each one is a
 * placeholder in the text at once, uploaded straight to the bucket, then
 * swapped for its address -- so typing goes on while it uploads.
 */
export function ArticleEditor({
  id,
  lessonId,
  value,
  onChange,
  disabled = false,
  onUploadingChange,
}: {
  id: string;
  lessonId: string;
  value: string;
  onChange: Dispatch<SetStateAction<string>>;
  disabled?: boolean;
  /** True while at least one picture is still uploading: saving now would
   * save its placeholder. */
  onUploadingChange?: (uploading: boolean) => void;
}) {
  const { accessToken } = useAuth();
  const area = useRef<HTMLTextAreaElement>(null);
  const filePicker = useRef<HTMLInputElement>(null);
  const placeholderCount = useRef(0);

  const [mode, setMode] = useState<Mode>("write");
  const [fullscreen, setFullscreen] = useState(false);
  const [uploading, setUploading] = useState(0);
  const [dragging, setDragging] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  useEffect(() => {
    onUploadingChange?.(uploading > 0);
  }, [uploading, onUploadingChange]);

  // The page behind a full-screen editor must not scroll under it.
  useEffect(() => {
    if (!fullscreen) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [fullscreen]);

  function selection(): Selection {
    const el = area.current;
    return el
      ? { start: el.selectionStart, end: el.selectionEnd }
      : { start: value.length, end: value.length };
  }

  /**
   * Through the browser's own insertText where it has one, so that Ctrl+Z
   * undoes a toolbar click like any typing; the plain state update is the
   * fallback, and costs only the undo.
   */
  function apply(replacement: Replacement) {
    const el = area.current;
    if (!el) return;
    const expected = applyReplacement(el.value, replacement);
    el.focus();
    el.setSelectionRange(replacement.from, replacement.to);
    let inserted = false;
    try {
      inserted = document.execCommand("insertText", false, replacement.insert);
    } catch {
      inserted = false;
    }
    if (!inserted || el.value !== expected) onChange(expected);
    requestAnimationFrame(() => {
      el.focus();
      el.setSelectionRange(replacement.select.start, replacement.select.end);
    });
  }

  function runTool(tool: Tool) {
    const el = area.current;
    if (!el) return;
    apply(tool.run(el.value, selection()));
  }

  async function uploadOne(file: File, placeholder: string) {
    try {
      const ticket = await createLessonImageUpload(accessToken as string, lessonId, {
        content_type: file.type,
        size_bytes: file.size,
      });
      await uploadToStorage(ticket, file);
      onChange((text) =>
        replaceOnce(text, placeholder, imageMarkdown(defaultAltText(file.name), ticket.public_url)),
      );
    } catch (error) {
      onChange((text) => replaceOnce(replaceOnce(text, `${placeholder}\n\n`, ""), placeholder, ""));
      setUploadError(error instanceof UploadError ? error.message : apiErrorMessage(error));
    } finally {
      setUploading((count) => count - 1);
    }
  }

  /** True when the files were pictures and were taken care of. */
  function insertPictures(files: File[]): boolean {
    const pictures = files.filter((file) => file.type.startsWith("image/"));
    if (pictures.length === 0 || disabled) return false;

    const accepted: File[] = [];
    for (const file of pictures) {
      const problem = lessonImageProblem(file);
      if (problem) setUploadError(`${file.name}: ${problem}`);
      else accepted.push(file);
    }
    if (accepted.length === 0) return true;
    setUploadError(null);

    const placeholders = accepted.map(() => {
      placeholderCount.current += 1;
      const token = `${UPLOAD_PLACEHOLDER_PREFIX}${Date.now().toString(36)}-${placeholderCount.current}`;
      return imageMarkdown("Đang tải ảnh lên", token);
    });
    const el = area.current;
    apply(insertBlock(el ? el.value : value, selection(), placeholders.join("\n\n")));

    setUploading((count) => count + accepted.length);
    accepted.forEach((file, index) => void uploadOne(file, placeholders[index]));
    return true;
  }

  function handlePaste(event: ClipboardEvent<HTMLTextAreaElement>) {
    if (insertPictures(Array.from(event.clipboardData.files))) event.preventDefault();
  }

  function handleDragOver(event: DragEvent<HTMLTextAreaElement>) {
    if (!event.dataTransfer.types.includes("Files")) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
    setDragging(true);
  }

  function handleDrop(event: DragEvent<HTMLTextAreaElement>) {
    setDragging(false);
    if (insertPictures(Array.from(event.dataTransfer.files))) event.preventDefault();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Escape" && fullscreen) {
      setFullscreen(false);
      return;
    }
    if (!(event.ctrlKey || event.metaKey) || event.altKey || event.shiftKey) return;
    const tool = SHORTCUTS[event.key.toLowerCase()];
    if (!tool) return;
    event.preventDefault();
    runTool(tool);
  }

  // Below `lg` (and outside full screen) one pane at a time; in full screen
  // on a wide screen, both side by side.
  const paneVisibility = (pane: Mode) =>
    cn(mode !== pane && "hidden", fullscreen && "lg:flex");

  return (
    <div
      className={cn(
        "flex flex-col gap-2",
        fullscreen && "fixed inset-0 z-50 bg-background p-4 sm:p-6",
      )}
      role={fullscreen ? "region" : undefined}
      aria-label={fullscreen ? "Soạn bài đọc toàn màn hình" : undefined}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div
          role="tablist"
          aria-label="Chế độ xem"
          className={cn("inline-flex rounded-md border border-border p-0.5", fullscreen && "lg:hidden")}
        >
          {(["write", "preview"] as const).map((pane) => (
            <button
              key={pane}
              type="button"
              role="tab"
              aria-selected={mode === pane}
              aria-controls={`${id}-${pane}`}
              onClick={() => setMode(pane)}
              className={cn(
                "rounded-sm px-3 py-1 text-sm font-medium transition-colors duration-fast",
                mode === pane
                  ? "bg-secondary text-secondary-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {pane === "write" ? "Soạn" : "Xem trước"}
            </button>
          ))}
        </div>
        {fullscreen ? (
          <p className="hidden text-sm font-medium lg:block">Soạn bài đọc</p>
        ) : null}
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => setFullscreen((on) => !on)}
          aria-pressed={fullscreen}
        >
          {fullscreen ? <Minimize2 aria-hidden /> : <Maximize2 aria-hidden />}
          {fullscreen ? "Thu nhỏ" : "Toàn màn hình"}
        </Button>
      </div>

      <div
        className={cn(
          // `grid-cols-1` is minmax(0, 1fr): an implicit column would grow to
          // the textarea's longest line (a picture's address) and push the
          // editor out of its panel on a phone.
          "grid min-h-0 grid-cols-1 gap-3",
          fullscreen && "flex-1 lg:grid-cols-2",
        )}
      >
        <div
          id={`${id}-write`}
          className={cn(
            "min-h-0 min-w-0 flex-col gap-2",
            paneVisibility("write"),
            mode === "write" && "flex",
          )}
        >
          <div
            role="toolbar"
            aria-label="Định dạng"
            aria-controls={id}
            className="flex flex-wrap items-center gap-1 rounded-md border border-border bg-card p-1"
          >
            {TOOLS.map((group, index) => (
              <div key={index} className="flex items-center gap-0.5 not-first:border-l not-first:border-border not-first:pl-1">
                {group.map((tool) => (
                  <Button
                    key={tool.label}
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    title={tool.shortcut ? `${tool.label} (${tool.shortcut})` : tool.label}
                    aria-label={tool.label}
                    disabled={disabled}
                    // Keeps the selection in the text while the button is pressed.
                    onMouseDown={(event) => event.preventDefault()}
                    onClick={() => runTool(tool)}
                  >
                    <tool.icon aria-hidden />
                  </Button>
                ))}
              </div>
            ))}
            <div className="flex items-center gap-0.5 border-l border-border pl-1">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                disabled={disabled}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => filePicker.current?.click()}
              >
                <ImagePlus aria-hidden />
                Chèn ảnh
              </Button>
              <input
                ref={filePicker}
                type="file"
                accept={LESSON_IMAGE_TYPES.join(",")}
                multiple
                className="sr-only"
                tabIndex={-1}
                aria-hidden
                onChange={(event) => {
                  insertPictures(Array.from(event.target.files ?? []));
                  event.target.value = "";
                }}
              />
            </div>
          </div>

          <Textarea
            ref={area}
            id={id}
            value={value}
            onChange={(event) => onChange(event.target.value)}
            onPaste={handlePaste}
            onDragOver={handleDragOver}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            spellCheck={false}
            placeholder={"## Mở đầu\n\nViết nội dung bài học ở đây. Dán hoặc kéo thả ảnh vào để chèn ảnh."}
            className={cn(
              // Grows with the text up to most of a screen, then scrolls.
              "max-h-[70vh] min-h-80 py-2.5 leading-relaxed",
              fullscreen && "field-sizing-fixed max-h-none min-h-0 flex-1 resize-none",
              dragging && "border-primary bg-accent",
            )}
          />
        </div>

        <div
          id={`${id}-preview`}
          role="region"
          aria-label="Xem trước bài đọc"
          className={cn(
            "min-h-80 min-w-0 flex-col overflow-auto rounded-md border border-border bg-card p-4",
            paneVisibility("preview"),
            mode === "preview" && "flex",
            fullscreen && "min-h-0",
          )}
        >
          {value.trim() ? (
            <article className="max-w-prose">
              <Markdown>{value}</Markdown>
            </article>
          ) : (
            <p className="text-sm text-muted-foreground">Chưa có nội dung để xem trước.</p>
          )}
        </div>
      </div>

      {uploadError ? (
        <Alert variant="destructive">
          <AlertDescription>{uploadError}</AlertDescription>
        </Alert>
      ) : null}

      <p className="flex items-center gap-2 text-sm text-muted-foreground" aria-live="polite">
        {uploading > 0 ? (
          <>
            <Loader2 className="size-4 animate-spin" aria-hidden />
            Đang tải {uploading} ảnh lên…
          </>
        ) : (
          <>
            Dán (Ctrl+V) hoặc kéo thả ảnh vào ô soạn: PNG, JPEG, WebP, GIF, tối đa 5 MB. Chữ
            trong ![…] là mô tả ảnh — học viên và trợ giảng AI đọc phần này.
          </>
        )}
      </p>
    </div>
  );
}
