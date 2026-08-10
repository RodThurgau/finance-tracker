import { Link } from 'react-router-dom';

import { PageHeader } from '../components/PageHeader.jsx';

export function NotFound() {
  return (
    <>
      <PageHeader title="Seite nicht gefunden" description="Diese Adresse gibt es nicht." />
      <Link to="/" className="text-sm font-medium text-accent hover:underline">
        Zurück zur Übersicht
      </Link>
    </>
  );
}
