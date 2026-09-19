/**
 * Turning `[2]` in an answer into a link to the lesson it cites.
 *
 * Done on the markdown tree rather than on the string, because the tree
 * already knows what is code: `[1, 3]` inside a code block or `inline code` is
 * a Python list, and those nodes are never visited here. Only plain text is.
 *
 * Kept in step with `_CITATION` in `backend/app/services/chat.py`: a letter
 * or digit right before the bracket makes it indexing (`a[1]`), not a mark.
 * Python's `\w` is Unicode-aware, hence `\p{L}\p{N}` rather than JS's `\w` --
 * otherwise "trị[1]" would be a citation here and not on the server.
 */

/** The fragment a citation link points at. Never navigated to: see `citationNumber`. */
const HREF_PREFIX = "#nguon-";

// Built from a string: the project's `target` is ES2017, and TypeScript
// rejects a lookbehind or `\p{…}` written as a literal for that target. Every
// browser the site supports runs both.
const CITATION = new RegExp(String.raw`(?<![\p{L}\p{N}_])\[(\d+(?:\s*,\s*\d+)*)\]`, "gu");

/** The number a link made by `remarkCitations` stands for, or null for any other link. */
export function citationNumber(href: string | undefined): number | null {
  if (!href?.startsWith(HREF_PREFIX)) return null;
  const number = Number(href.slice(HREF_PREFIX.length));
  return Number.isInteger(number) ? number : null;
}

/** Just enough of mdast to walk it: react-markdown hands the plugin a real one. */
interface MdNode {
  type: string;
  value?: string;
  url?: string;
  children?: MdNode[];
}

function textNode(value: string): MdNode {
  return { type: "text", value };
}

function linkNode(number: number): MdNode {
  return { type: "link", url: `${HREF_PREFIX}${number}`, children: [textNode(String(number))] };
}

/**
 * One text node as text and citation links. A mark whose numbers are none of
 * `known` stays exactly as written -- `[2021]` is a year, and a number the
 * answer was never given is a citation of nothing.
 */
function splitText(value: string, known: ReadonlySet<number>): MdNode[] {
  const out: MdNode[] = [];
  let last = 0;

  for (const match of value.matchAll(CITATION)) {
    const numbers = match[1]
      .split(",")
      .map((raw) => Number(raw.trim()))
      .filter((number) => known.has(number));
    if (numbers.length === 0) continue;

    const start = match.index ?? 0;
    if (start > last) out.push(textNode(value.slice(last, start)));
    out.push(...numbers.map(linkNode));
    last = start + match[0].length;
  }

  if (last === 0) return [textNode(value)];
  if (last < value.length) out.push(textNode(value.slice(last)));
  return out;
}

function walk(node: MdNode, known: ReadonlySet<number>): void {
  if (!node.children) return;
  // Inside a link, a mark would become a link within a link.
  if (node.type === "link" || node.type === "linkReference") return;

  node.children = node.children.flatMap((child) => {
    if (child.type === "text" && child.value) return splitText(child.value, known);
    walk(child, known);
    return [child];
  });
}

/**
 * A remark plugin: `[n]` for every n in `known` becomes a link to
 * `#nguon-n`, which the page renders as a button to lesson n.
 */
export function remarkCitations({ known }: { known: ReadonlySet<number> }) {
  return (tree: MdNode) => walk(tree, known);
}
