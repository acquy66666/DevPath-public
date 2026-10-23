/**
 * What each button of the article editor does to the text.
 *
 * Every operation is a pure function from (text, selection) to one
 * replacement: the range to replace, what to put there, and what to select
 * afterwards. The editor applies it through the browser's own "insert text"
 * so that Ctrl+Z still undoes a click on Bold -- which is why the result is a
 * replacement rather than a whole new text.
 */

export interface Selection {
  start: number;
  end: number;
}

export interface Replacement {
  from: number;
  to: number;
  insert: string;
  /** Where the selection goes, in the text after the replacement. */
  select: Selection;
}

/** Text around the selection: `**bold**`, `_italic_`, `` `code` ``. */
export function wrapInline(
  text: string,
  selection: Selection,
  marker: string,
  placeholder: string,
): Replacement {
  const { start, end } = selection;
  const chosen = text.slice(start, end);

  // Already wrapped: the second click takes it off again.
  if (
    chosen &&
    text.slice(start - marker.length, start) === marker &&
    text.slice(end, end + marker.length) === marker
  ) {
    const from = start - marker.length;
    return {
      from,
      to: end + marker.length,
      insert: chosen,
      select: { start: from, end: from + chosen.length },
    };
  }

  const inner = chosen || placeholder;
  return {
    from: start,
    to: end,
    insert: `${marker}${inner}${marker}`,
    select: { start: start + marker.length, end: start + marker.length + inner.length },
  };
}

/** The whole lines the selection touches. */
function lineRange(text: string, selection: Selection): Selection {
  const start = text.lastIndexOf("\n", selection.start - 1) + 1;
  // A selection ending right after a newline does not include the next line.
  const last = selection.end > selection.start && text[selection.end - 1] === "\n"
    ? selection.end - 1
    : selection.end;
  const newline = text.indexOf("\n", last);
  return { start, end: newline === -1 ? text.length : newline };
}

/**
 * A marker at the start of every selected line: a heading, a list, a quote.
 * Clicking again on lines that all carry it takes it off.
 */
export function prefixLines(
  text: string,
  selection: Selection,
  prefix: (index: number) => string,
  pattern: RegExp,
  /** What else to take off before marking: a bullet, when numbering a list. */
  replaces: RegExp = pattern,
): Replacement {
  const range = lineRange(text, selection);
  const lines = text.slice(range.start, range.end).split("\n");
  const allMarked = lines.every((line) => pattern.test(line));
  const changed = lines.map((line, index) =>
    allMarked ? line.replace(pattern, "") : `${prefix(index)}${line.replace(replaces, "")}`,
  );
  const insert = changed.join("\n");
  return {
    from: range.start,
    to: range.end,
    insert,
    select: { start: range.start, end: range.start + insert.length },
  };
}

const LIST_MARKER = /^(?:[-*+]|\d+\.) /;

export const HEADING = { prefix: () => "## ", pattern: /^#{1,6} /, replaces: /^#{1,6} / };
export const BULLETS = { prefix: () => "- ", pattern: /^[-*+] /, replaces: LIST_MARKER };
export const NUMBERS = {
  prefix: (index: number) => `${index + 1}. `,
  pattern: /^\d+\. /,
  replaces: LIST_MARKER,
};
export const QUOTE = { prefix: () => "> ", pattern: /^> ?/, replaces: /^> ?/ };

/**
 * A block of its own -- a table, a code block, a picture -- with a blank line
 * on either side, so it never glues itself onto the paragraph next to it.
 * `selectWithin` is the part of `block` to select, as offsets into it.
 */
export function insertBlock(
  text: string,
  selection: Selection,
  block: string,
  selectWithin: Selection = { start: block.length, end: block.length },
): Replacement {
  const before = text.slice(0, selection.start);
  const after = text.slice(selection.end);
  const lead = before === "" || before.endsWith("\n\n") ? "" : before.endsWith("\n") ? "\n" : "\n\n";
  const tail = after === "" || after.startsWith("\n\n") ? "" : after.startsWith("\n") ? "\n" : "\n\n";
  const insert = `${lead}${block}${tail}`;
  return {
    from: selection.start,
    to: selection.end,
    insert,
    select: {
      start: selection.start + lead.length + selectWithin.start,
      end: selection.start + lead.length + selectWithin.end,
    },
  };
}

export function codeBlock(text: string, selection: Selection): Replacement {
  const code = text.slice(selection.start, selection.end) || "print(\"Xin chào\")";
  const open = "```python\n";
  const block = `${open}${code}\n\`\`\``;
  // The language is what most often needs changing: select it.
  return insertBlock(text, selection, block, { start: 3, end: open.length - 1 });
}

export const TABLE_TEMPLATE = [
  "| Cột 1 | Cột 2 |",
  "| --- | --- |",
  "| Ô 1 | Ô 2 |",
].join("\n");

export function table(text: string, selection: Selection): Replacement {
  return insertBlock(text, selection, TABLE_TEMPLATE, { start: 2, end: 7 });
}

export function link(text: string, selection: Selection): Replacement {
  const label = text.slice(selection.start, selection.end) || "chữ hiển thị";
  const insert = `[${label}](https://)`;
  // The address is the part still to be written.
  const urlStart = selection.start + label.length + 3;
  return {
    from: selection.start,
    to: selection.end,
    insert,
    select: { start: urlStart, end: urlStart + "https://".length },
  };
}

/** `![description](address)`, escaped so a `]` in the name cannot end it early. */
export function imageMarkdown(alt: string, src: string): string {
  return `![${alt.replace(/[[\]]/g, "")}](${src})`;
}

/** The text with `search` replaced once, or unchanged when it is gone. */
export function replaceOnce(text: string, search: string, replacement: string): string {
  const at = text.indexOf(search);
  return at === -1 ? text : text.slice(0, at) + replacement + text.slice(at + search.length);
}

export function applyReplacement(text: string, replacement: Replacement): string {
  return text.slice(0, replacement.from) + replacement.insert + text.slice(replacement.to);
}
