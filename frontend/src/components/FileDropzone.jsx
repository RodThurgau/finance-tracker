import { useRef, useState } from 'react';
import { FileUp, UploadCloud } from 'lucide-react';

/** Drag-and-drop / click file picker. Accepts a single CSV file. */
export function FileDropzone({ onFile, selectedFile, disabled }) {
  const inputRef = useRef(null);
  const [isDragging, setDragging] = useState(false);

  function handleFiles(fileList) {
    const file = fileList?.[0];
    if (file) onFile(file);
  }

  return (
    <div
      onClick={() => !disabled && inputRef.current?.click()}
      onDragOver={(event) => {
        event.preventDefault();
        if (!disabled) setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(event) => {
        event.preventDefault();
        setDragging(false);
        if (!disabled) handleFiles(event.dataTransfer.files);
      }}
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-disabled={disabled}
      onKeyDown={(event) => {
        if (!disabled && (event.key === 'Enter' || event.key === ' ')) {
          event.preventDefault();
          inputRef.current?.click();
        }
      }}
      className={`flex cursor-pointer flex-col items-center gap-3 rounded-xl border-2 border-dashed p-10 text-center transition-colors ${
        disabled ? 'cursor-not-allowed opacity-60' : ''
      } ${
        isDragging
          ? 'border-accent bg-accent-soft'
          : 'border-line bg-surface-raised hover:border-content-muted'
      }`}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".csv,.CSV,text/csv"
        className="hidden"
        disabled={disabled}
        onChange={(event) => handleFiles(event.target.files)}
      />

      {selectedFile ? (
        <>
          <FileUp size={28} className="text-accent" />
          <p className="font-medium">{selectedFile.name}</p>
          <p className="text-sm text-content-muted">
            Klicken oder eine andere Datei hierher ziehen, um sie zu ersetzen.
          </p>
        </>
      ) : (
        <>
          <UploadCloud size={28} className="text-content-muted" />
          <p className="font-medium">CSV-Datei hierher ziehen oder klicken</p>
          <p className="text-sm text-content-muted">ING- oder PayPal-Export (.csv)</p>
        </>
      )}
    </div>
  );
}
