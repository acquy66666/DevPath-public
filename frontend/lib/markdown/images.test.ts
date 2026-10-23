// node --test lib/markdown/images.test.ts  (npm test runs every *.test.ts)
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  classifyImage,
  defaultAltText,
  DEV_MEDIA_ORIGIN,
  lessonImageProblem,
  MAX_LESSON_IMAGE_BYTES,
  mediaOrigins,
  UPLOAD_PLACEHOLDER_PREFIX,
} from "./images.ts";

const SITE = "https://devpath-01.me";
const ORIGINS = mediaOrigins(SITE, true);

test("production trusts the site's own origin and nothing else", () => {
  assert.deepEqual(ORIGINS, [SITE]);
  assert.deepEqual(mediaOrigins(undefined, true), []);
});

test("development also trusts the dev storage service", () => {
  assert.deepEqual(mediaOrigins("http://localhost:3000", false), [
    "http://localhost:3000",
    DEV_MEDIA_ORIGIN,
  ]);
});

test("a picture from our own bucket is drawn", () => {
  const src = `${SITE}/devpath-media/lesson-images/c/abc.png`;
  assert.deepEqual(classifyImage(src, ORIGINS), { kind: "hosted", src });
});

test("a picture from anywhere else becomes a link, not a request", () => {
  assert.deepEqual(classifyImage("https://tracker.example/pixel.gif", ORIGINS), {
    kind: "external",
    href: "https://tracker.example/pixel.gif",
  });
  // Same name, another origin: the scheme and port are part of the origin.
  assert.equal(classifyImage("http://devpath-01.me/a.png", ORIGINS).kind, "external");
  assert.equal(classifyImage("https://devpath-01.me.evil.example/a.png", ORIGINS).kind, "external");
});

test("an address that is not a web link is neither drawn nor linked", () => {
  for (const src of ["javascript:alert(1)", "data:image/png;base64,AAAA", "a.png", "", undefined]) {
    assert.deepEqual(classifyImage(src, ORIGINS), { kind: "external", href: null }, String(src));
  }
});

test("an upload still running is its own kind", () => {
  assert.deepEqual(classifyImage(`${UPLOAD_PLACEHOLDER_PREFIX}1`, ORIGINS), { kind: "uploading" });
});

test("only small pictures of the four types may be inserted", () => {
  assert.equal(lessonImageProblem({ type: "image/png", size: 1000 }), null);
  assert.equal(lessonImageProblem({ type: "image/gif", size: MAX_LESSON_IMAGE_BYTES }), null);
  assert.match(lessonImageProblem({ type: "image/svg+xml", size: 10 }) ?? "", /PNG/);
  assert.match(lessonImageProblem({ type: "image/png", size: MAX_LESSON_IMAGE_BYTES + 1 }) ?? "", /5 MB/);
});

test("the description starts from the file name, unless the name says nothing", () => {
  assert.equal(defaultAltText("cua-so_terminal.png"), "cua so terminal");
  assert.equal(defaultAltText("image.png"), "Ảnh");
  assert.equal(defaultAltText("Image 3.PNG"), "Ảnh");
  assert.equal(defaultAltText("so-do [moi].webp"), "so do moi");
  assert.equal(defaultAltText(".png"), "Ảnh");
});
