import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';

import { listCategories } from '../api/categories.js';
import { listTags } from '../api/tags.js';

// Categories and tags change rarely and are needed by the filter bar, the
// category menu and every row, so they get a long stale time and are shared
// through the query cache rather than passed down from the page.
const LOOKUP_STALE_TIME = 5 * 60 * 1000;

export function useCategories() {
  return useQuery({
    queryKey: ['categories'],
    queryFn: listCategories,
    staleTime: LOOKUP_STALE_TIME,
  });
}

export function useTags() {
  return useQuery({
    queryKey: ['tags'],
    queryFn: listTags,
    staleTime: LOOKUP_STALE_TIME,
  });
}

/**
 * Look up tables for resolving the `category_id` / `subcategory_id` that
 * transactions carry — the transaction payload has no names on it.
 */
export function useCategoryIndex() {
  const { data: categories } = useCategories();

  return useMemo(() => {
    const byId = new Map();
    const subcategoryById = new Map();
    for (const category of categories ?? []) {
      byId.set(category.id, category);
      for (const subcategory of category.subcategories ?? []) {
        subcategoryById.set(subcategory.id, subcategory);
      }
    }
    return { categories: categories ?? [], byId, subcategoryById };
  }, [categories]);
}
