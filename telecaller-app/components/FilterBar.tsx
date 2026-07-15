'use client';

import { useState, useEffect } from 'react';
import { FilterState, SavedFilter, getSavedFilters, saveFilter, deleteFilter } from '@/lib/savedFilters';

type FilterBarProps = {
  filters: FilterState;
  onChange: (filters: FilterState) => void;
  cities: string[];
  roleGroups: string[];
  statuses: string[];
};

export default function FilterBar({ filters, onChange, cities, roleGroups, statuses }: FilterBarProps) {
  const [presets, setPresets] = useState<SavedFilter[]>([]);
  const [newPresetName, setNewPresetName] = useState('');
  const [showSaveForm, setShowSaveForm] = useState(false);

  useEffect(() => {
    setPresets(getSavedFilters());
  }, []);

  const updateFilter = <K extends keyof FilterState>(key: K, value: FilterState[K]) => {
    onChange({ ...filters, [key]: value });
  };

  const handleSavePreset = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newPresetName.trim()) return;
    const updated = saveFilter(newPresetName.trim(), filters);
    setPresets(updated);
    setNewPresetName('');
    setShowSaveForm(false);
  };

  const handleDeletePreset = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const updated = deleteFilter(id);
    setPresets(updated);
  };

  const handleApplyPreset = (preset: SavedFilter) => {
    onChange(preset.filters);
  };

  const handleClearAll = () => {
    onChange({
      search: '',
      tier: '',
      status: '',
      roleGroup: '',
      city: '',
      followupDue: false,
    });
  };

  return (
    <div className="filter-bar card pad" style={{ marginBottom: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
      <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'center' }}>
        <input
          type="text"
          placeholder="Search company, contact..."
          className="input"
          value={filters.search}
          onChange={(e) => updateFilter('search', e.target.value)}
          style={{ flex: 1, minWidth: '200px' }}
        />

        <select
          className="input"
          value={filters.city}
          onChange={(e) => updateFilter('city', e.target.value)}
          style={{ width: '150px' }}
        >
          <option value="">All Cities</option>
          {cities.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>

        <select
          className="input"
          value={filters.roleGroup}
          onChange={(e) => updateFilter('roleGroup', e.target.value)}
          style={{ width: '160px' }}
        >
          <option value="">All Roles</option>
          {roleGroups.map((rg) => (
            <option key={rg} value={rg}>{rg}</option>
          ))}
        </select>

        <select
          className="input"
          value={filters.status}
          onChange={(e) => updateFilter('status', e.target.value)}
          style={{ width: '150px' }}
        >
          <option value="">All Statuses</option>
          {statuses.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>

        <label style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', cursor: 'pointer', fontSize: '14px', fontWeight: 500 }}>
          <input
            type="checkbox"
            checked={filters.followupDue}
            onChange={(e) => updateFilter('followupDue', e.target.checked)}
          />
          Follow-up Due
        </label>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', alignItems: 'center', justifyContent: 'space-between', borderTop: '1px solid var(--border-default)', paddingTop: '10px' }}>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-muted)' }}>Tiers:</span>
          {['', 'hot', 'warm'].map((t) => (
            <button
              key={t}
              onClick={() => updateFilter('tier', t)}
              className={`chip-link ${filters.tier === t ? 'active' : ''}`}
              style={{ padding: '4px 12px', fontSize: '13px', border: 'none', cursor: 'pointer', background: 'transparent' }}
            >
              {t === '' ? 'All Tiers' : t.toUpperCase()}
            </button>
          ))}
        </div>

        <div style={{ display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
          {presets.length > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginRight: '8px' }}>
              <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-muted)' }}>Presets:</span>
              <div className="preset-list" style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                {presets.map((p) => (
                  <span
                    key={p.id}
                    onClick={() => handleApplyPreset(p)}
                    className="badge sky animate-fade-in"
                    style={{ cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '4px', paddingRight: '4px' }}
                  >
                    {p.name}
                    <button
                      onClick={(e) => handleDeletePreset(p.id, e)}
                      style={{ border: 'none', background: 'transparent', color: 'inherit', cursor: 'pointer', padding: '0 2px', fontSize: '11px', lineHeight: 1 }}
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            </div>
          )}

          {!showSaveForm ? (
            <button className="btn secondary" style={{ padding: '6px 12px', fontSize: '13px' }} onClick={() => setShowSaveForm(true)}>
              Save current filter
            </button>
          ) : (
            <form onSubmit={handleSavePreset} style={{ display: 'flex', gap: '6px' }}>
              <input
                type="text"
                className="input"
                placeholder="Preset name"
                required
                value={newPresetName}
                onChange={(e) => setNewPresetName(e.target.value)}
                style={{ padding: '4px 8px', fontSize: '13px', width: '120px' }}
              />
              <button type="submit" className="btn primary" style={{ padding: '6px 12px', fontSize: '13px' }}>Save</button>
              <button type="button" className="btn secondary" style={{ padding: '6px 12px', fontSize: '13px' }} onClick={() => setShowSaveForm(false)}>Cancel</button>
            </form>
          )}

          <button className="btn secondary" style={{ padding: '6px 12px', fontSize: '13px' }} onClick={handleClearAll}>
            Clear all
          </button>
        </div>
      </div>
    </div>
  );
}
