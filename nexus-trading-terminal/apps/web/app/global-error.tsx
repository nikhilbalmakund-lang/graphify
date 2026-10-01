"use client";

// Last-resort boundary (root layout failed). Plain markup, no app chrome.
export default function GlobalError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <html lang="en">
      <body style={{ background: "#07090d", color: "#d6dee9", fontFamily: "system-ui, sans-serif", display: "grid", placeItems: "center", minHeight: "100vh", margin: 0 }}>
        <div style={{ textAlign: "center" }}>
          <p style={{ fontWeight: 600 }}>The application failed to load.</p>
          <button type="button" onClick={reset} style={{ marginTop: 12, padding: "6px 12px", background: "#141c28", color: "#d6dee9", border: "1px solid #283446", borderRadius: 4, cursor: "pointer" }}>
            Reload
          </button>
        </div>
      </body>
    </html>
  );
}
