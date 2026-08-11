import { useEffect, useRef, useState, type ChangeEvent, type DragEvent } from "react";

interface Props {
  prompt: string;
  glyph: string;
  onContinue: (file: File) => void;
  continueLabel?: string;
  busy?: boolean;
}

export default function PhotoCapture({ prompt, glyph, onContinue, continueLabel = "Continue", busy }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const libraryInputRef = useRef<HTMLInputElement>(null);
  // Counts nested dragenter/dragleave pairs so a drag over a child element
  // (e.g. the preview <img>) doesn't flicker the highlight off.
  const dragDepth = useRef(0);

  // Revoke the blob URL when this step is torn down (e.g. remounted with a
  // new `key` for the next step) instead of only on an explicit Retake.
  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  function useFile(picked: File | null | undefined) {
    if (!picked || !picked.type.startsWith("image/")) return;
    setFile(picked);
    setPreviewUrl(URL.createObjectURL(picked));
  }

  function handlePick(e: ChangeEvent<HTMLInputElement>) {
    useFile(e.target.files?.[0]);
    e.target.value = "";
  }

  function retake() {
    setFile(null);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
  }

  function handleDragEnter(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    if (!e.dataTransfer.types.includes("Files")) return;
    dragDepth.current += 1;
    setIsDragging(true);
  }

  function handleDragOver(e: DragEvent<HTMLDivElement>) {
    // Required for onDrop to fire at all -- browsers reject drops by default.
    e.preventDefault();
  }

  function handleDragLeave(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    dragDepth.current = Math.max(0, dragDepth.current - 1);
    if (dragDepth.current === 0) setIsDragging(false);
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    dragDepth.current = 0;
    setIsDragging(false);
    const dropped = Array.from(e.dataTransfer.files).find((f) => f.type.startsWith("image/"));
    useFile(dropped);
  }

  return (
    <div className="capture-shell">
      <div className="capture-prompt">{prompt}</div>

      <div
        onDragEnter={handleDragEnter}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {previewUrl ? (
          <div className={`capture-preview${isDragging ? " drag-active" : ""}`}>
            <img src={previewUrl} alt="Captured preview" />
          </div>
        ) : (
          <div className={`capture-placeholder${isDragging ? " drag-active" : ""}`}>
            <span className="glyph">{glyph}</span>
            <span>{isDragging ? "Drop photo here" : "No photo yet"}</span>
            <span className="capture-placeholder-hint">or drag and drop an image</span>
          </div>
        )}
      </div>

      <input
        ref={cameraInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        style={{ display: "none" }}
        onChange={handlePick}
      />
      <input
        ref={libraryInputRef}
        type="file"
        accept="image/*"
        style={{ display: "none" }}
        onChange={handlePick}
      />

      {file ? (
        <div className="btn-row">
          <button className="btn btn-secondary" onClick={retake} disabled={busy}>
            Retake
          </button>
          <button className="btn btn-primary" onClick={() => onContinue(file)} disabled={busy}>
            {busy ? "Working…" : continueLabel}
          </button>
        </div>
      ) : (
        <div className="btn-row">
          <button className="btn btn-primary" onClick={() => cameraInputRef.current?.click()}>
            📷 Take Photo
          </button>
          <button className="btn btn-secondary" onClick={() => libraryInputRef.current?.click()}>
            🖼️ Upload
          </button>
        </div>
      )}
    </div>
  );
}
