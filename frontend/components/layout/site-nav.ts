/** The site's sections, for everyone. A signed-in user's own pages live in the avatar menu. */
export const NAV = [
  { href: "/khoa-hoc", label: "Khóa học" },
  { href: "/bang-xep-hang", label: "Bảng xếp hạng" },
] as const;

export function isCurrent(pathname: string, href: string) {
  // "/khoa-hoc-cua-toi" starts with "/khoa-hoc" and is not under it.
  return pathname === href || pathname.startsWith(`${href}/`);
}
