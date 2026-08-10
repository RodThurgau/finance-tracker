import { PageHeader } from '../components/PageHeader.jsx';
import { Placeholder } from '../components/Placeholder.jsx';

export function ImportExport() {
  return (
    <>
      <PageHeader
        title="Import/Export"
        description="CSV-Dateien von ING und PayPal einlesen, gefilterte Daten exportieren."
      />
      <Placeholder step="3.4 / 3.5">Upload, Vorschau und CSV-Export folgen.</Placeholder>
    </>
  );
}
