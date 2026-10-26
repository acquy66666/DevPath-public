import assert from "node:assert/strict";
import { test } from "node:test";

import {
  afterSignUpPath,
  authHref,
  courseSlugFromPath,
  greetingName,
  welcomeAction,
  welcomeMarker,
} from "./welcome.ts";

test("greets by the given name: the last word of a Vietnamese full name", () => {
  assert.equal(greetingName("Lê Thu Hà"), "Hà");
  assert.equal(greetingName("  Nguyễn   Văn   An "), "An");
  assert.equal(greetingName("Minh"), "Minh");
  // A name that ends in a number is not a given name: say it whole.
  assert.equal(greetingName("Người mua 08"), "Người mua 08");
  assert.equal(greetingName("   "), null);
});

test("sign-up goes to the welcome page and carries where the visitor was headed", () => {
  assert.equal(afterSignUpPath("/"), "/chao-mung");
  assert.equal(
    afterSignUpPath("/khoa-hoc/python-co-ban"),
    "/chao-mung?next=%2Fkhoa-hoc%2Fpython-co-ban",
  );
});

test("the link between sign-in and sign-up keeps `next`", () => {
  assert.equal(authHref("/dang-ky", "/"), "/dang-ky");
  assert.equal(
    authHref("/dang-nhap", "/hoc/python-co-ban?bai=1"),
    "/dang-nhap?next=%2Fhoc%2Fpython-co-ban%3Fbai%3D1",
  );
  assert.equal(authHref("/dang-nhap", "/", { email: "an@example.com" }), "/dang-nhap?email=an%40example.com");
});

test("a course page or its learn page names the course to go back to", () => {
  assert.equal(courseSlugFromPath("/khoa-hoc/python-co-ban"), "python-co-ban");
  assert.equal(courseSlugFromPath("/hoc/python-co-ban?bai=abc"), "python-co-ban");
  assert.equal(courseSlugFromPath("/khoa-hoc"), null);
  assert.equal(courseSlugFromPath("/khoa-hoc?category_id=1"), null);
  assert.equal(courseSlugFromPath("/gio-hang"), null);
  assert.equal(courseSlugFromPath("/khoa-hoc/python/extra"), null);
});

test("the welcome page's main button goes where the visitor was headed", () => {
  assert.deepEqual(welcomeAction("/", null), { href: "/khoa-hoc", label: "Khám phá khóa học" });
  assert.deepEqual(welcomeAction("/khoa-hoc/python-co-ban", "Python cơ bản"), {
    href: "/khoa-hoc/python-co-ban",
    label: "Quay lại “Python cơ bản”",
  });
  // The course could not be read: still go back, without a name.
  assert.deepEqual(welcomeAction("/khoa-hoc/python-co-ban", null), {
    href: "/khoa-hoc/python-co-ban",
    label: "Quay lại khóa học bạn đang xem",
  });
  assert.deepEqual(welcomeAction("/gio-hang", null), { href: "/gio-hang", label: "Tiếp tục" });
});

test("Naomi waves once, for the account that was just made in this tab", () => {
  assert.equal(welcomeMarker.key, "devpath:just-signed-up");
  assert.equal(welcomeMarker.shouldWave("u-1", "u-1"), true);
  assert.equal(welcomeMarker.shouldWave(null, "u-1"), false);
  // Another account signed in since: not theirs to celebrate.
  assert.equal(welcomeMarker.shouldWave("u-2", "u-1"), false);
});
