import { NavLink } from 'react-router-dom';
import { ArrowDownUp, FolderTree, LayoutDashboard, Receipt, Tags, X } from 'lucide-react';

export const NAV_ITEMS = [
  { to: '/', label: 'Übersicht', icon: LayoutDashboard, end: true },
  { to: '/transaktionen', label: 'Transaktionen', icon: Receipt },
  { to: '/kategorien', label: 'Kategorien', icon: FolderTree },
  { to: '/tags', label: 'Tags', icon: Tags },
  { to: '/import-export', label: 'Import/Export', icon: ArrowDownUp },
];

function linkClasses({ isActive }) {
  const base =
    'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors';
  return isActive
    ? `${base} bg-accent-soft text-accent`
    : `${base} text-content-muted hover:bg-surface-hover hover:text-content`;
}

export function Sidebar({ isOpen, onClose }) {
  return (
    <aside
      className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-line bg-surface-raised transition-transform duration-200 lg:static lg:translate-x-0 ${
        isOpen ? 'translate-x-0' : '-translate-x-full'
      }`}
    >
      <div className="flex items-center justify-between px-5 py-4">
        <span className="text-lg font-semibold tracking-tight">Finanzen</span>
        <button
          type="button"
          onClick={onClose}
          aria-label="Navigation schließen"
          className="rounded-md p-1 text-content-muted hover:bg-surface-hover hover:text-content lg:hidden"
        >
          <X size={18} />
        </button>
      </div>

      <nav className="flex flex-1 flex-col gap-1 px-3 py-2">
        {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
          <NavLink key={to} to={to} end={end} className={linkClasses} onClick={onClose}>
            <Icon size={18} />
            {label}
          </NavLink>
        ))}
      </nav>

      <p className="px-5 py-4 text-xs text-content-muted">Lokal · keine Cloud</p>
    </aside>
  );
}
