'use client';

export type FilterState = {
  search: string;
  tier: string;
  status: string;
  roleGroup: string;
  city: string;
  followupDue: boolean;
};

export type SavedFilter = {
  id: string;
  name: string;
  filters: FilterState;
};

const STORAGE_KEY = 'tc_saved_filters';

export function getSavedFilters(): SavedFilter[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch (e) {
    console.error('Failed to load saved filters:', e);
    return [];
  }
}

export function saveFilter(name: string, filters: FilterState): SavedFilter[] {
  if (typeof window === 'undefined') return [];
  try {
    const current = getSavedFilters();
    const id = Date.now().toString(36) + Math.random().toString(36).slice(2, 5);
    const updated = [...current, { id, name, filters }];
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
    return updated;
  } catch (e) {
    console.error('Failed to save filter:', e);
    return getSavedFilters();
  }
}

export function deleteFilter(id: string): SavedFilter[] {
  if (typeof window === 'undefined') return [];
  try {
    const current = getSavedFilters();
    const updated = current.filter((f) => f.id !== id);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
    return updated;
  } catch (e) {
    console.error('Failed to delete filter:', e);
    return getSavedFilters();
  }
}
