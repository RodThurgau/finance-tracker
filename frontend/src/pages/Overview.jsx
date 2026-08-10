import { useQuery } from '@tanstack/react-query';

import { api } from '../api/client.js';
import { PageHeader } from '../components/PageHeader.jsx';
import { Placeholder } from '../components/Placeholder.jsx';

export function Overview() {
  // Smoke test for the whole data path: Vite proxy → FastAPI → React Query.
  const { data, isPending, isError, error } = useQuery({
    queryKey: ['health'],
    queryFn: () => api.get('/health'),
  });

  let status = 'Backend wird geprüft …';
  if (isError) status = `Backend nicht erreichbar: ${error.message}`;
  else if (!isPending) status = `Backend erreichbar (${data.status})`;

  return (
    <>
      <PageHeader title="Übersicht" description="Einnahmen, Ausgaben und Auswertungen." />
      <Placeholder step="4.1">
        Diagramme und Kennzahlen folgen. {status}
      </Placeholder>
    </>
  );
}
