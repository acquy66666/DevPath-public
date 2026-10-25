/**
 * Quiz text is plain text with one piece of Markdown: `code` in backticks.
 *
 * Not the site's `<Markdown>`: a question is one sentence, and an option is a
 * few words that must stay on the line they are on. A full Markdown renderer
 * would turn "1. range(5)" into a list and "*args" into italics.
 */
export interface TextPiece {
  code: boolean;
  text: string;
}

const SPAN = /`([^`\n]+)`/g;

export function splitInlineCode(text: string): TextPiece[] {
  const pieces: TextPiece[] = [];
  let from = 0;
  for (const match of text.matchAll(SPAN)) {
    const at = match.index ?? 0;
    if (at > from) pieces.push({ code: false, text: text.slice(from, at) });
    pieces.push({ code: true, text: match[1] });
    from = at + match[0].length;
  }
  if (from < text.length) pieces.push({ code: false, text: text.slice(from) });
  return pieces;
}
