"use client";

import Editor, { loader, type OnMount } from "@monaco-editor/react";
import { useEffect, useImperativeHandle, useRef, useState, type Ref } from "react";

import { Skeleton } from "@/components/ui/skeleton";

/**
 * Monaco, served from this origin rather than from a CDN.
 *
 * `@monaco-editor/react` fetches the editor from jsdelivr unless told
 * otherwise. That would make the most important page of this project depend on
 * somebody else's uptime and on the room's network — on the day of a defence.
 * `scripts/copy-monaco.mjs` puts the files under `public/monaco`, and this is
 * the line that points at them.
 *
 * Module scope on purpose: the loader must be configured before any editor
 * mounts, and doing it in an effect is a race with the first render.
 */
loader.config({ paths: { vs: "/monaco/vs" } });

/**
 * Whether the page is currently in dark mode.
 *
 * Read from the class the stylesheet keys off rather than from a theme
 * library: the app has dark tokens but nothing that toggles them yet, and
 * adding a dependency to answer a question the DOM already answers would be
 * the wrong trade. When a toggle does arrive, this follows it.
 */
function useDarkMode(): boolean {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const root = document.documentElement;
    const read = () => setDark(root.classList.contains("dark"));
    read();

    const observer = new MutationObserver(read);
    observer.observe(root, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, []);

  return dark;
}

export interface CodeEditorHandle {
  /** Replace everything in the editor — "restore the starter code", say. */
  setValue: (next: string) => void;
}

export interface CodeEditorProps {
  /** The text to start with. Later changes to this prop are ignored. */
  initialValue: string;
  onChange: (value: string) => void;
  language?: string;
  height?: number;
  ref?: Ref<CodeEditorHandle>;
}

/**
 * The editor owns its text; React only mirrors it.
 *
 * `defaultValue`, not `value`. Monaco is not an input with a string in it — it
 * holds a document with a cursor, a selection and an undo stack, and every
 * keystroke already lands there first. Adding React state as the source means
 * each keystroke makes a round trip out and back, and every render in between
 * is a chance to push stale text into a live document: at best the cursor
 * jumps, at worst a character typed during the trip is overwritten.
 *
 * So the text stays in the editor, `onChange` reports it outwards for
 * submitting and for the draft, and the only way back in is the imperative
 * handle below — used when something other than typing should replace the
 * whole buffer, which is the one case where clobbering is the intent.
 */
export function CodeEditor({
  initialValue,
  onChange,
  language = "python",
  height = 420,
  ref,
}: CodeEditorProps) {
  const dark = useDarkMode();
  const editor = useRef<Parameters<OnMount>[0] | null>(null);

  useImperativeHandle(ref, () => ({
    setValue: (next: string) => {
      editor.current?.setValue(next);
      onChange(next);
    },
  }));

  return (
    <div className="overflow-hidden rounded-md border" style={{ height }}>
      <Editor
        height="100%"
        language={language}
        defaultValue={initialValue}
        onMount={(instance) => {
          editor.current = instance;
        }}
        onChange={(next) => onChange(next ?? "")}
        theme={dark ? "vs-dark" : "light"}
        loading={<Skeleton className="size-full rounded-none" />}
        options={{
          fontSize: 14,
          // A beginner's exercise is short; a minimap over twenty lines is
          // decoration that costs a fifth of the width.
          minimap: { enabled: false },
          scrollBeyondLastLine: false,
          // Python is whitespace-significant and these are the defaults every
          // Python course teaches. Getting them wrong here would have students
          // debugging indentation the editor introduced.
          tabSize: 4,
          insertSpaces: true,
          renderWhitespace: "selection",
          automaticLayout: true,
          padding: { top: 12, bottom: 12 },
        }}
      />
    </div>
  );
}
