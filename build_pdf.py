"""
Convert END_TO_END_WORKFLOW.md to a print-quality PDF.

Pipeline:
  1. Extract ```mermaid fenced blocks so they survive Markdown conversion.
  2. Convert Markdown -> HTML (tables, fenced code, TOC, syntax highlighting).
  3. Re-insert Mermaid blocks as <div class="mermaid"> and add mermaid.js.
  4. Render with headless Chromium (Edge/Chrome) and print to PDF, giving
     the diagrams time to draw via --virtual-time-budget.

Usage:
    python build_pdf.py [source.md] [output.pdf]
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import markdown
from pygments.formatters import HtmlFormatter


ROOT = Path(__file__).resolve().parent
BROWSERS = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
]


def find_browser() -> Path:
    for b in BROWSERS:
        if b.exists():
            return b
    raise SystemExit("No Chromium-based browser (Chrome/Edge) found for PDF export.")


def build_html(md_text: str, title: str) -> str:
    # 1) Protect mermaid blocks from the Markdown/code processors.
    mermaid_blocks: list[str] = []

    def _stash(match: re.Match) -> str:
        mermaid_blocks.append(match.group(1).strip())
        return f"\n\nMERMAIDPLACEHOLDER{len(mermaid_blocks) - 1}\n\n"

    md_text = re.sub(r"```mermaid\s*\n(.*?)```", _stash, md_text, flags=re.DOTALL)

    # 2) Markdown -> HTML.
    html_body = markdown.markdown(
        md_text,
        extensions=["extra", "tables", "fenced_code", "codehilite", "toc", "sane_lists"],
        extension_configs={"codehilite": {"guess_lang": False}},
    )

    # 3) Swap placeholders for real mermaid containers (paragraph-wrapped by md).
    def _restore(match: re.Match) -> str:
        idx = int(match.group(1))
        return f'<div class="mermaid">\n{mermaid_blocks[idx]}\n</div>'

    html_body = re.sub(r"<p>\s*MERMAIDPLACEHOLDER(\d+)\s*</p>", _restore, html_body)
    html_body = re.sub(r"MERMAIDPLACEHOLDER(\d+)", _restore, html_body)

    pygments_css = HtmlFormatter(style="friendly").get_style_defs(".codehilite")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>
  mermaid.initialize({{ startOnLoad: true, theme: 'neutral', securityLevel: 'loose',
                        flowchart: {{ useMaxWidth: true }}, sequence: {{ useMaxWidth: true }} }});
</script>
<style>
  :root {{
    --ink:#1a2230; --dim:#5b6675; --brd:#dde3ec; --accent:#0f6cbd; --accent-soft:#eaf3fb;
    --code-bg:#f6f8fb; --th:#f2f6fb;
  }}
  * {{ box-sizing:border-box; }}
  html {{ -webkit-print-color-adjust:exact; print-color-adjust:exact; }}
  body {{
    font-family:"Segoe UI",-apple-system,Roboto,Helvetica,Arial,sans-serif;
    color:var(--ink); line-height:1.6; font-size:11pt; margin:0;
  }}
  .page {{ max-width:820px; margin:0 auto; padding:8px 20px 40px; }}

  h1 {{ font-size:26pt; line-height:1.15; margin:0 0 6px; color:#0b1a2b; letter-spacing:-.5px; }}
  h2 {{ font-size:17pt; margin:30px 0 10px; padding-bottom:6px; border-bottom:2px solid var(--accent);
        color:#0b1a2b; }}
  h3 {{ font-size:13.5pt; margin:20px 0 6px; color:#12324f; }}
  h4 {{ font-size:11.5pt; margin:14px 0 4px; color:#26405c; }}
  h2, h3, h4 {{ page-break-after:avoid; }}
  p, li {{ orphans:3; widows:3; }}
  a {{ color:var(--accent); text-decoration:none; }}

  blockquote {{
    margin:14px 0; padding:10px 16px; background:var(--accent-soft);
    border-left:4px solid var(--accent); border-radius:4px; color:#294a66;
  }}
  blockquote p {{ margin:4px 0; }}

  hr {{ border:none; border-top:1px solid var(--brd); margin:26px 0; }}

  code {{ font-family:"Cascadia Code",Consolas,"SF Mono",Menlo,monospace; font-size:9.5pt;
          background:var(--code-bg); padding:1.5px 5px; border-radius:4px; color:#b5297b; }}
  pre {{ background:var(--code-bg); border:1px solid var(--brd); border-radius:8px;
         padding:12px 14px; overflow:auto; page-break-inside:avoid; }}
  pre code {{ background:none; padding:0; color:#1a2230; font-size:9pt; line-height:1.5; }}
  .codehilite {{ background:var(--code-bg); border:1px solid var(--brd); border-radius:8px;
                 padding:12px 14px; margin:12px 0; page-break-inside:avoid; }}
  .codehilite pre {{ border:none; padding:0; margin:0; background:none; }}
  {pygments_css}

  table {{ border-collapse:collapse; width:100%; margin:14px 0; font-size:9.5pt;
           page-break-inside:avoid; }}
  th, td {{ border:1px solid var(--brd); padding:7px 10px; text-align:left; vertical-align:top; }}
  th {{ background:var(--th); font-weight:700; color:#12324f; }}
  tr:nth-child(even) td {{ background:#fafcfe; }}

  ul, ol {{ padding-left:22px; }}
  li {{ margin:4px 0; }}

  .mermaid {{ text-align:center; margin:18px 0; page-break-inside:avoid; }}
  .mermaid svg {{ max-width:100%; height:auto; }}

  @page {{ size:A4; margin:16mm 14mm 18mm; }}
  @media print {{ .page {{ padding:0; }} a {{ color:var(--ink); }} }}
</style>
</head>
<body>
  <div class="page">
{html_body}
  </div>
</body>
</html>"""


def main() -> None:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "END_TO_END_WORKFLOW.md"
    out_pdf = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "END_TO_END_WORKFLOW.pdf"

    md_text = src.read_text(encoding="utf-8")
    html = build_html(md_text, title=src.stem.replace("_", " ").title())

    tmp_html = ROOT / "_pdf_build.html"
    tmp_html.write_text(html, encoding="utf-8")

    browser = find_browser()
    print(f"Rendering with {browser.name} ...")
    subprocess.run(
        [
            str(browser),
            "--headless=new",
            "--disable-gpu",
            "--no-pdf-header-footer",
            "--virtual-time-budget=20000",
            f"--print-to-pdf={out_pdf}",
            tmp_html.resolve().as_uri(),
        ],
        check=True,
    )

    tmp_html.unlink(missing_ok=True)
    size_kb = out_pdf.stat().st_size / 1024
    print(f"[OK] {out_pdf.name} ({size_kb:.0f} KB)")


if __name__ == "__main__":
    main()
