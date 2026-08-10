import { Check } from 'lucide-react';

import { useCategoryIndex } from '../hooks/useLookups.js';

const ROW = 'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-surface-hover';

/**
 * Category → subcategory picker. `onSelect` receives a patch body ready for
 * the transactions endpoint: picking a category clears the subcategory,
 * picking a subcategory sets both.
 */
export function CategoryMenu({ onSelect, categoryId = null, subcategoryId = null }) {
  const { categories } = useCategoryIndex();

  return (
    <div className="w-72 p-1">
      <button
        type="button"
        className={`${ROW} ${categoryId === null ? 'text-content' : 'text-content-muted'}`}
        onClick={() => onSelect({ category_id: null, subcategory_id: null })}
      >
        {categoryId === null && <Check size={14} />}
        <span className={categoryId === null ? '' : 'pl-[22px]'}>Nicht zugeordnet</span>
      </button>

      {categories.map((category) => {
        const isCategory = categoryId === category.id && subcategoryId === null;
        return (
          <div key={category.id}>
            <button
              type="button"
              className={`${ROW} font-medium ${isCategory ? 'text-content' : 'text-content-muted'}`}
              onClick={() => onSelect({ category_id: category.id, subcategory_id: null })}
            >
              <span
                className="size-2.5 shrink-0 rounded-full border border-line"
                style={category.color ? { backgroundColor: category.color } : undefined}
              />
              <span className="flex-1 truncate">{category.name}</span>
              {isCategory && <Check size={14} />}
            </button>

            {(category.subcategories ?? []).map((subcategory) => (
              <button
                key={subcategory.id}
                type="button"
                className={`${ROW} pl-7 ${
                  subcategoryId === subcategory.id ? 'text-content' : 'text-content-muted'
                }`}
                onClick={() =>
                  onSelect({ category_id: category.id, subcategory_id: subcategory.id })
                }
              >
                <span className="flex-1 truncate">{subcategory.name}</span>
                {subcategoryId === subcategory.id && <Check size={14} />}
              </button>
            ))}
          </div>
        );
      })}
    </div>
  );
}
