/** Trigger a browser download for a same-origin API export (CSV/JSON). */
export async function downloadFrom(path: string, filename: string): Promise<void> {
  const res = await fetch(path, { cache: "no-store" });
  if (!res.ok) throw new Error(`Export failed (${res.status})`);
  const blob = await res.blob();
  downloadBlob(blob, filename);
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
