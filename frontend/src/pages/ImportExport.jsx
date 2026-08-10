import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { RotateCcw } from 'lucide-react';

import { importCsv, previewImport } from '../api/imports.js';
import { FileDropzone } from '../components/FileDropzone.jsx';
import { ImportPreview } from '../components/ImportPreview.jsx';
import { ImportSummary } from '../components/ImportSummary.jsx';
import { PageHeader } from '../components/PageHeader.jsx';
import { Placeholder } from '../components/Placeholder.jsx';

export function ImportExport() {
  const queryClient = useQueryClient();
  const [file, setFile] = useState(null);
  const [summary, setSummary] = useState(null);

  const previewMutation = useMutation({ mutationFn: previewImport });
  const importMutation = useMutation({
    mutationFn: () => importCsv(file),
    onSuccess: (result) => {
      setSummary(result);
      // Counts on the categories/tags pages and filter dropdowns move too.
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['categories'] });
      queryClient.invalidateQueries({ queryKey: ['tags'] });
    },
  });

  function selectFile(nextFile) {
    setFile(nextFile);
    setSummary(null);
    previewMutation.mutate(nextFile);
  }

  function reset() {
    setFile(null);
    setSummary(null);
    previewMutation.reset();
    importMutation.reset();
  }

  const isBusy = previewMutation.isPending || importMutation.isPending;
  const canImport = file && previewMutation.isSuccess && !summary;

  return (
    <>
      <PageHeader
        title="Import/Export"
        description="CSV-Dateien von ING und PayPal einlesen, gefilterte Daten exportieren."
      />

      <section className="mb-10">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Import</h2>
          {(file || summary) && (
            <button
              type="button"
              onClick={reset}
              className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-content-muted hover:bg-surface-hover hover:text-content"
            >
              <RotateCcw size={14} />
              Neue Datei
            </button>
          )}
        </div>

        <FileDropzone onFile={selectFile} selectedFile={file} disabled={isBusy} />

        {previewMutation.isPending && (
          <p className="mt-4 text-sm text-content-muted">Datei wird gelesen …</p>
        )}

        {previewMutation.isError && (
          <p className="mt-4 whitespace-pre-wrap rounded-lg border border-negative/40 bg-negative/10 px-3 py-2 text-sm text-negative">
            {previewMutation.error.message}
          </p>
        )}

        {previewMutation.isSuccess && !summary && (
          <>
            <ImportPreview preview={previewMutation.data} />

            <div className="mt-4 flex items-center gap-3">
              <button
                type="button"
                onClick={() => importMutation.mutate()}
                disabled={!canImport || importMutation.isPending}
                className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-surface disabled:opacity-50"
              >
                {importMutation.isPending ? 'Wird importiert …' : 'Importieren'}
              </button>
              {previewMutation.data.errors.length > 0 && (
                <span className="text-sm text-content-muted">
                  Fehlerhafte Zeilen werden übersprungen, der Rest wird importiert.
                </span>
              )}
            </div>
          </>
        )}

        {importMutation.isError && (
          <p className="mt-4 rounded-lg border border-negative/40 bg-negative/10 px-3 py-2 text-sm text-negative">
            Import fehlgeschlagen: {importMutation.error.message}
          </p>
        )}

        {summary && <ImportSummary summary={summary} />}
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold">Export</h2>
        <Placeholder step="3.5">Filter, Vorschau und CSV-Export folgen.</Placeholder>
      </section>
    </>
  );
}
