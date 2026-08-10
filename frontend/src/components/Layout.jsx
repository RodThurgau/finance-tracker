import { useEffect, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Menu } from 'lucide-react';

import { Sidebar } from './Sidebar.jsx';

export function Layout() {
  const [isNavOpen, setNavOpen] = useState(false);
  const { pathname } = useLocation();

  // Navigating on mobile should dismiss the overlay sidebar.
  useEffect(() => {
    setNavOpen(false);
  }, [pathname]);

  return (
    <div className="min-h-screen lg:flex">
      <header className="flex items-center gap-3 border-b border-line bg-surface-raised px-4 py-3 lg:hidden">
        <button
          type="button"
          onClick={() => setNavOpen(true)}
          aria-label="Navigation öffnen"
          className="rounded-md p-1 text-content-muted hover:bg-surface-hover hover:text-content"
        >
          <Menu size={20} />
        </button>
        <span className="font-semibold tracking-tight">Finanzen</span>
      </header>

      {isNavOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/60 lg:hidden"
          onClick={() => setNavOpen(false)}
          aria-hidden="true"
        />
      )}

      <Sidebar isOpen={isNavOpen} onClose={() => setNavOpen(false)} />

      <main className="min-w-0 flex-1 px-4 py-6 sm:px-6 lg:px-8">
        <Outlet />
      </main>
    </div>
  );
}
