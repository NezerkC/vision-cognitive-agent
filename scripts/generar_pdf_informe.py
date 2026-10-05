import os
import re
import sys

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):  # noqa: N802 - overrides reportlab Canvas.showPage
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))

        # Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(54, 750, "Visión OS (Vision Cognitive Agent) - Informe Técnico Integral")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(54, 742, 558, 742)

        # Footer
        footer_text = f"Página {self._pageNumber} de {page_count}"
        self.drawRightString(558, 36, footer_text)
        self.drawString(54, 36, "CONFIDENCIAL / DOCUMENTACIÓN TÉCNICA DE VISIÓN OS")
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(54, 48, 558, 48)

        self.restoreState()


def format_inline(text):
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # Backticks `code`
    def code_repl(m):
        val = m.group(1)
        return f'<font face="Courier" color="#0F766E"><b>{val}</b></font>'

    text = re.sub(r"`([^`]+)`", code_repl, text)

    # Bold **text**
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)

    # Italic *text*
    text = re.sub(r"(?<!\S)\*([^*]+)\*(?!\S)", r"<i>\1</i>", text)
    return text


def build_pdf(md_filepath, pdf_filepath):
    doc = SimpleDocTemplate(pdf_filepath, pagesize=letter, leftMargin=54, rightMargin=54, topMargin=54, bottomMargin=54)

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=8,
    )

    h1_style = ParagraphStyle(
        "H1",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#1E293B"),
        spaceBefore=12,
        spaceAfter=5,
        keepWithNext=True,
    )

    h2_style = ParagraphStyle(
        "H2",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#0F766E"),
        spaceBefore=9,
        spaceAfter=4,
        keepWithNext=True,
    )

    body_style = ParagraphStyle(
        "Body",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#334155"),
        spaceAfter=4,
    )

    bullet_style = ParagraphStyle("Bullet", parent=body_style, leftIndent=12, spaceAfter=3)

    code_style = ParagraphStyle(
        "CodeStyle",
        parent=styles["Code"],
        fontName="Courier",
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#0F172A"),
        backColor=colors.HexColor("#F1F5F9"),
        borderColor=colors.HexColor("#E2E8F0"),
        borderWidth=0.5,
        borderPadding=6,
        spaceBefore=5,
        spaceAfter=5,
    )

    table_cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10.5,
        textColor=colors.HexColor("#1E293B"),
    )

    table_header_style = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.white,
    )

    story = []

    with open(md_filepath, encoding="utf-8") as f:
        lines = f.readlines()

    in_code_block = False
    code_lines = []
    in_table = False
    table_data = []

    for line in lines:
        raw_line = line.rstrip("\n")

        # Code blocks
        if raw_line.startswith("```"):
            if in_code_block:
                in_code_block = False
                code_text = "<br/>".join(code_lines).replace(" ", "&nbsp;")
                story.append(Paragraph(code_text, code_style))
                code_lines = []
            else:
                in_code_block = True
                code_lines = []
            continue

        if in_code_block:
            escaped = raw_line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            code_lines.append(escaped)
            continue

        # Tables
        if "|" in raw_line and not raw_line.strip().startswith("```"):
            parts = [p.strip() for p in raw_line.strip().split("|")[1:-1]]
            if parts and not all(c in ":- " for c in "".join(parts)):
                if not in_table:
                    in_table = True
                    table_data = []
                table_data.append(parts)
            continue
        else:
            if in_table:
                in_table = False
                formatted_table = []
                for row_idx, row in enumerate(table_data):
                    formatted_row = []
                    for cell in row:
                        cell_fmt = format_inline(cell)
                        if row_idx == 0:
                            formatted_row.append(Paragraph(cell_fmt, table_header_style))
                        else:
                            formatted_row.append(Paragraph(cell_fmt, table_cell_style))
                    formatted_table.append(formatted_row)

                t = Table(formatted_table, colWidths=[160, 80, 264])
                t.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                            ("TOPPADDING", (0, 0), (-1, -1), 5),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                        ]
                    )
                )
                story.append(Spacer(1, 4))
                story.append(t)
                story.append(Spacer(1, 6))
                table_data = []

        # Empty lines
        if not raw_line.strip():
            story.append(Spacer(1, 2))
            continue

        # Horizontal Rule
        if raw_line.strip() == "---":
            story.append(
                HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CBD5E1"), spaceBefore=5, spaceAfter=5)
            )
            continue

        text = raw_line.strip()

        # Headings
        if text.startswith("# "):
            story.append(Paragraph(format_inline(text[2:]), title_style))
        elif text.startswith("## "):
            story.append(Spacer(1, 4))
            story.append(Paragraph(format_inline(text[3:]), h1_style))
        elif text.startswith("### "):
            story.append(Paragraph(format_inline(text[4:]), h2_style))
        elif text.startswith("- ") or text.startswith("* "):
            story.append(Paragraph(f"• {format_inline(text[2:])}", bullet_style))
        elif re.match(r"^\d+\.\s", text):
            num = text.split(".")[0]
            rest = text[len(num) + 2 :]
            story.append(Paragraph(f"<b>{num}.</b> {format_inline(rest)}", bullet_style))
        else:
            story.append(Paragraph(format_inline(text), body_style))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"PDF generado exitosamente en: {pdf_filepath}")


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.abspath(os.path.join(script_dir, ".."))

    md_file = os.path.join(base_dir, "material_complementario", "informe_general_vision_os.md")
    pdf_file = os.path.join(base_dir, "material_complementario", "informe_general_vision_os.pdf")

    if not os.path.exists(md_file):
        print(f"ERROR: No se encuentra el archivo markdown: {md_file}")
        sys.exit(1)

    build_pdf(md_file, pdf_file)
