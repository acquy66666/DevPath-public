"use client";

import Editor, { loader, type BeforeMount, type OnMount } from "@monaco-editor/react";
import { useEffect, useImperativeHandle, useRef, useState, type Ref } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

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

/**
 * The editor's light theme, in the design system's colours.
 *
 * Monaco paints on its own and wants hex values, so they are read from the
 * palette variables app/globals.css declares (`@theme static`) rather than
 * written here: the stylesheet stays the only place a colour is spelled.
 * If any of them is missing the theme is Monaco's own `vs` under our name --
 * plainer, never broken.
 */
const THEME = "devpath-light";

/** `#fff` → `#ffffff`: the stylesheet is minified, and Monaco takes six digits only. */
function longHex(value: string): string {
  const short = /^#([0-9a-f])([0-9a-f])([0-9a-f])$/i.exec(value);
  return short ? `#${short[1]}${short[1]}${short[2]}${short[2]}${short[3]}${short[3]}` : value;
}

function defineTheme(monaco: Parameters<BeforeMount>[0]) {
  const css = getComputedStyle(document.documentElement);
  const step = (name: string) => longHex(css.getPropertyValue(`--color-${name}`).trim());
  const names = [
    "slate-0", "slate-25", "slate-50", "slate-100", "slate-300", "slate-400", "slate-600",
    "slate-700", "slate-900", "jade-50", "jade-100", "jade-300", "jade-600", "jade-700",
    "rose-700", "amber-700",
  ];
  const c = Object.fromEntries(names.map((name) => [name, step(name)]));
  if (!Object.values(c).every((value) => /^#[0-9a-f]{6}$/i.test(value))) {
    monaco.editor.defineTheme(THEME, { base: "vs", inherit: true, rules: [], colors: {} });
    return;
  }
  const fg = (name: string) => c[name].slice(1);

  monaco.editor.defineTheme(THEME, {
    base: "vs",
    inherit: true,
    rules: [
      { token: "", foreground: fg("slate-900") },
      { token: "keyword", foreground: fg("jade-700") },
      { token: "comment", foreground: fg("slate-600"), fontStyle: "italic" },
      { token: "string", foreground: fg("rose-700") },
      { token: "number", foreground: fg("amber-700") },
      { token: "delimiter", foreground: fg("slate-700") },
    ],
    colors: {
      "editor.background": c["slate-0"],
      "editor.foreground": c["slate-900"],
      "editorLineNumber.foreground": c["slate-400"],
      "editorLineNumber.activeForeground": c["slate-700"],
      "editor.lineHighlightBackground": c["slate-25"],
      "editor.lineHighlightBorder": c["slate-50"],
      "editor.selectionBackground": c["jade-100"],
      "editor.inactiveSelectionBackground": c["jade-50"],
      "editorCursor.foreground": c["jade-600"],
      "editorIndentGuide.background1": c["slate-100"],
      "editorIndentGuide.activeBackground1": c["slate-300"],
      "editorBracketMatch.background": c["jade-50"],
      "editorBracketMatch.border": c["jade-300"],
    },
  });
}

/** Geist Mono, the design system's code face, with its metric-matched fallback. */
function monoFamily(): string {
  const family = getComputedStyle(document.documentElement).getPropertyValue("--font-geist-mono").trim();
  return family ? `${family}, monospace` : "monospace";
}

export interface CodeEditorHandle {
  /** Replace everything in the editor — "restore the starter code", say. */
  setValue: (next: string) => void;
  /** Put the cursor in the editor. */
  focus: () => void;
}

export interface CodeEditorProps {
  /** The text to start with. Later changes to this prop are ignored. */
  initialValue: string;
  onChange: (value: string) => void;
  language?: string;
  /**
   * Sizes the box: a fixed height by default, or `flex-1 min-h-0` inside a
   * column that gives it the rest of the screen.
   */
  className?: string;
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
  className,
  ref,
}: CodeEditorProps) {
  const dark = useDarkMode();
  const editor = useRef<Parameters<OnMount>[0] | null>(null);

  useImperativeHandle(ref, () => ({
    setValue: (next: string) => {
      editor.current?.setValue(next);
      onChange(next);
    },
    focus: () => editor.current?.focus(),
  }));

  return (
    <div className={cn("h-80 overflow-hidden sm:h-[420px]", className)}>
      <Editor
        height="100%"
        language={language}
        defaultValue={initialValue}
        beforeMount={defineTheme}
        onMount={(instance, monaco) => {
          editor.current = instance;
          // Measured with the fallback face if Geist Mono was still on its
          // way; measured again once it is here, or the cursor drifts off the
          // letters it sits between.
          void document.fonts?.ready.then(() => monaco.editor.remeasureFonts());
        }}
        onChange={(next) => onChange(next ?? "")}
        theme={dark ? "vs-dark" : THEME}
        loading={<Skeleton className="size-full rounded-none" />}
        options={{
          fontSize: 14,
          lineHeight: 22,
          fontFamily: monoFamily(),
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
