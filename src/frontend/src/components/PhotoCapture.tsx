import { useRef, useState, type ChangeEvent } from "react";

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
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const libraryInputRef = useRef<HTMLInputElement>(null);

  function handlePick(e: ChangeEvent<HTMLInputElement>) {
    const picked = e.target.files?.[0];
    if (!picked) return;
    setFile(picked);
    setPreviewUrl(URL.createObjectURL(picked));
    e.target.value = "";
  }

  function retake() {
    setFile(null);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
  }

  return (
    <div className="capture-shell">
      <div className="capture-prompt">{prompt}</div>

      {previewUrl ? (
        <div className="capture-preview">
          <img src={previewUrl} alt="Captured preview" />
        </div>
      ) : (
        <div className="capture-placeholder">
          <span className="glyph">{glyph}</span>
          <span>No photo yet</span>
        </div>
      )}

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
