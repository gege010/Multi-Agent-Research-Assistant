"""Report generation service — markdown to PDF."""
from __future__ import annotations
import base64
import re
from datetime import datetime
import structlog

logger = structlog.get_logger()


class ReportService:
    def markdown_to_html(self, markdown_text: str) -> str:
        html = markdown_text
        html = re.sub(r"```(\w*)\n(.*?)```", r"<pre><code>\2</code></pre>", html, flags=re.DOTALL)
        html = re.sub(r"`([^`]+)`", r"<code>\1</code>", html)
        html = re.sub(r"^###### (.+)$", r"<h6>\1</h6>", html, flags=re.MULTILINE)
        html = re.sub(r"^##### (.+)$", r"<h5>\1</h5>", html, flags=re.MULTILINE)
        html = re.sub(r"^#### (.+)$", r"<h4>\1</h4>", html, flags=re.MULTILINE)
        html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
        html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
        html = re.sub(r"^# (.+)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)
        html = re.sub(r"\*\*\*([^*]+)\*\*\*", r"<strong><em>\1</em></strong>", html)
        html = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", html)
        html = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", html)
        html = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', html)
        html = re.sub(r"^> (.+)$", r"<blockquote>\1</blockquote>", html, flags=re.MULTILINE)
        html = re.sub(r"^- (.+)$", r"<li>\1</li>", html, flags=re.MULTILINE)
        html = re.sub(r"^(\d+)\. (.+)$", r"<li>\2</li>", html, flags=re.MULTILINE)
        html = re.sub(r"\n\n+", r"</p><p>", html)
        html = f"<p>{html}</p>"
        html = html.replace("<p></p>", "").replace("<p><br></p>", "")
        return html

    def markdown_to_pdf(self, markdown_text: str) -> bytes:
        """Convert markdown to PDF using fpdf2 (pure Python, no GTK needed)."""
        try:
            from fpdf import FPDF
        except Exception as exc:
            logger.error("fpdf2_import_failed", error=str(exc))
            raise RuntimeError("PDF generation requires fpdf2: pip install fpdf2") from exc

        def safe_cell(text: str, indent: int = 0) -> None:
            """Write text safely — width is always guaranteed >= 20."""
            w = pdf.w - pdf.l_margin - pdf.r_margin - indent
            if w < 20:
                w = pdf.w - pdf.l_margin - pdf.r_margin  # fall back to full width
            if w < 20:
                return  # skip if still too narrow
            pdf.set_x(pdf.l_margin + indent)
            pdf.multi_cell(w, 5, text)

        def safe_line(text: str) -> None:
            """Single-line cell, no wrap, same safe-width logic."""
            w = pdf.w - pdf.l_margin - pdf.r_margin
            if w < 20:
                return
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(w, 5, text)

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.add_page()

        # Title
        first_line = markdown_text.split("\n", 1)[0].lstrip("# ").strip()
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_text_color(22, 33, 62)
        pdf.set_margins(20, 20, 20)
        safe_line(first_line)
        pdf.ln(4)

        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(51, 51, 51)

        in_code = False
        for raw in markdown_text.split("\n"):
            line = raw.rstrip()

            # Fenced code blocks
            if line.startswith("```"):
                in_code = not in_code
                if in_code:
                    pdf.ln(2)
                continue

            if in_code:
                pdf.set_font("Courier", "", 9)
                pdf.set_text_color(80, 80, 80)
                safe_line(line)
                pdf.set_font("Helvetica", "", 10)
                pdf.set_text_color(51, 51, 51)
                continue

            # Strip markdown formatting before writing
            clean = self._strip_inline_md(line)

            # Headings
            if line.startswith("### "):
                pdf.ln(3)
                pdf.set_font("Helvetica", "B", 14)
                pdf.set_text_color(22, 33, 62)
                safe_line(clean)
                pdf.ln(2)
            elif line.startswith("## "):
                pdf.ln(4)
                pdf.set_font("Helvetica", "B", 16)
                pdf.set_text_color(22, 33, 62)
                safe_line(clean)
                pdf.set_draw_color(200, 200, 200)
                pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
                pdf.ln(3)
            elif line.startswith("# "):
                pass  # title already rendered
            elif line.startswith("####### ") or line.startswith("###### ") or line.startswith("##### ") or line.startswith("#### "):
                pdf.set_font("Helvetica", "B", 12)
                pdf.set_text_color(50, 50, 50)
                safe_line(clean)
            # Horizontal rule
            elif line in ("---", "***", "___"):
                pdf.ln(2)
                pdf.set_draw_color(200, 200, 200)
                pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
                pdf.ln(2)
            # List items — indent only, not with multi_cell
            elif line.startswith("- ") or line.startswith("* ") or re.match(r"^\d+\. ", line):
                pdf.set_font("Helvetica", "", 10)
                pdf.set_text_color(51, 51, 51)
                prefix = line[:2]
                safe_cell(clean, indent=5)
            # Blockquote
            elif line.startswith(">"):
                pdf.set_font("Helvetica", "I", 10)
                pdf.set_text_color(100, 100, 100)
                safe_cell(clean.lstrip("> "), indent=5)
            # Empty / whitespace-only
            elif not clean.strip():
                pass
            # Normal paragraph
            else:
                pdf.set_font("Helvetica", "", 10)
                pdf.set_text_color(51, 51, 51)
                safe_line(clean)

        # Footer
        pdf.ln(8)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(150, 150, 150)
        footer_text = f"Generated by Multi-Agent Research Assistant | {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
        pdf.cell(0, 5, footer_text, align="C")

        return pdf.output()

    def _strip_inline_md(self, text: str) -> str:
        """Remove bold, italic, inline code, links and sanitize unicode from text."""
        text = re.sub(r"\*\*\*(.+?)\*\*\*", r"\1", text)
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
        text = re.sub(r"\*(.+?)\*", r"\1", text)
        text = re.sub(r"`([^`]+)`", r"\1", text)
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        
        # Sanitize common Unicode characters unsupported by standard PDF fonts
        replacements = {
            '\u2013': '-',   # en-dash
            '\u2014': '--',  # em-dash
            '\u2018': "'",   # left single quote
            '\u2019': "'",   # right single quote
            '\u201c': '"',   # left double quote
            '\u201d': '"',   # right double quote
            '\u2026': '...', # ellipsis
            '\u2022': '-',   # bullet
            '\u00a0': ' ',   # non-breaking space
        }
        for unicode_char, ascii_char in replacements.items():
            text = text.replace(unicode_char, ascii_char)
            
        # Encode and decode to ASCII to blindly drop any remaining unsupported chars
        return text.encode('ascii', 'ignore').decode('ascii')

    def markdown_to_base64_pdf(self, markdown_text: str) -> str:
        pdf_bytes = self.markdown_to_pdf(markdown_text)
        return base64.b64encode(pdf_bytes).decode("utf-8")
