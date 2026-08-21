import { apiFetch } from "./client";

export interface Category {
  id: string;
  name: string;
  slug: string;
  position: number;
}

/** A top-level category. `children` is always present, empty when there are none. */
export interface CategoryTree extends Category {
  children: Category[];
}

/**
 * The whole taxonomy in one call -- it is a dozen curated rows, not user data,
 * so the backend sends it unpaginated and the form can render it as it stands.
 */
export function listCategories(): Promise<CategoryTree[]> {
  return apiFetch<CategoryTree[]>("/api/v1/categories");
}
