"""Build Matric Rewrite HQ into a single self-contained HTML file.

    python build.py                 # writes index.html (open it in any browser)
    python build.py --fragment OUT  # also writes a head/body-less copy for
                                    # publishing as a claude.ai Artifact

Everything (styles, data, code) is inlined so the file works offline, from a
phone's file manager, a USB stick or any static host. The only external
requests are Google Fonts (with system-font fallbacks) and the links the
learner taps (YouTube videos and DBE past-paper PDFs).
"""

import argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "src"
SCRIPTS = [
    "topics_maths.js",
    "topics_physics.js",
    "papers.js",
    "plan.js",
    "cards.js",
    "sheets.js",
    "app.js",
]
FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    "family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,700;12..96,800"
    "&family=IBM+Plex+Mono:wght@500"
    '&family=Lexend:wght@400;500;600;700&display=swap">'
)


def page_content() -> str:
    css = (SRC / "styles.css").read_text()
    js = "\n".join((SRC / name).read_text() for name in SCRIPTS)
    if "</script" in js.lower():
        raise SystemExit("a source file contains '</script', which would end the inline script early")
    return (
        "<title>Matric Rewrite HQ</title>\n"
        f"{FONTS}\n"
        f"<style>\n{css}</style>\n"
        '<div id="app"><p style="padding:24px;font-family:system-ui,sans-serif">'
        "Loading your study plan…</p></div>\n"
        '<noscript><p style="padding:24px">Matric Rewrite HQ needs JavaScript. '
        "Open this file in Chrome, Firefox, Safari or Edge.</p></noscript>\n"
        f"<script>\n{js}\n</script>\n"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fragment", type=Path, help="also write an Artifact-ready copy here")
    args = ap.parse_args()

    content = page_content()
    full = (
        "<!doctype html>\n"
        '<html lang="en-ZA">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
        '<meta name="description" content="A 25-day NSC rewrite study system for Mathematics and Physical Sciences.">\n'
        "</head>\n<body>\n"
        f"{content}"
        "</body>\n</html>\n"
    )
    out = HERE / "index.html"
    out.write_text(full)
    print(f"wrote {out} ({len(full.encode()) // 1024} KB)")
    if args.fragment:
        args.fragment.write_text(content)
        print(f"wrote {args.fragment}")


if __name__ == "__main__":
    main()
