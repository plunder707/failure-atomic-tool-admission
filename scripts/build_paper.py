#!/usr/bin/env python3
"""Render the Markdown manuscript as a publication PDF using ReportLab."""

from __future__ import annotations

import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
)
from reportlab.pdfgen.canvas import Canvas


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "paper/paper.md"
OUTPUT = ROOT / "paper/paper.pdf"
NAVY = colors.HexColor("#17324D")
BLUE = colors.HexColor("#2C6E9F")
GRAY = colors.HexColor("#5D6872")
LIGHT = colors.HexColor("#E3E8EC")
GREEN = colors.HexColor("#2E7D5B")


def inline_markup(text: str) -> str:
    text = latex_plain(text)
    escaped = html.escape(text, quote=False)
    escaped = re.sub(
        r"\[([^\]]+)\]\((https?://[^)]+)\)",
        r'<link href="\2" color="#2C6E9F">\1</link>',
        escaped,
    )
    escaped = re.sub(r"`([^`]+)`", r'<font name="Courier">\1</font>', escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", escaped)
    return escaped


def latex_plain(text: str) -> str:
    """Render the manuscript's small math vocabulary as readable plain text."""

    replacements = (
        (r"\(", ""),
        (r"\)", ""),
        (r"\leftarrow", "<-"),
        (r"\Longrightarrow", "implies"),
        (r"\bigwedge_{i=1}^{n}", "ALL(i=1..n)"),
        (r"\forall", "for all"),
        (r"\notin", "not in"),
        (r"\in", "in"),
        (r"\land", "and"),
        (r"\ldots", "..."),
        (r"\mathbin{\|}", "||"),
        (r"\quad", "    "),
        (r"\neg", "NOT"),
    )
    for source, target in replacements:
        text = text.replace(source, target)
    text = re.sub(r"\\text\{([^}]+)\}", r"\1", text)
    text = text.replace(r"\{", "{").replace(r"\}", "}")
    return text.replace("\\", "")


def styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "PaperTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=23,
            leading=27,
            textColor=NAVY,
            alignment=TA_LEFT,
            spaceAfter=13,
        ),
        "subtitle": ParagraphStyle(
            "PaperSubtitle",
            parent=base["Heading2"],
            fontName="Helvetica",
            fontSize=13.5,
            leading=18,
            textColor=GRAY,
            spaceAfter=22,
        ),
        "author": ParagraphStyle(
            "Author",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10.5,
            leading=15,
            textColor=GRAY,
            spaceAfter=3,
        ),
        "h1": ParagraphStyle(
            "H1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=19,
            textColor=NAVY,
            spaceBefore=13,
            spaceAfter=7,
            keepWithNext=True,
        ),
        "h2": ParagraphStyle(
            "H2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11.5,
            leading=15,
            textColor=BLUE,
            spaceBefore=10,
            spaceAfter=5,
            keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName="Times-Roman",
            fontSize=9.4,
            leading=13.2,
            textColor=colors.HexColor("#22272B"),
            alignment=TA_LEFT,
            spaceAfter=6,
            allowWidows=0,
            allowOrphans=0,
        ),
        "abstract": ParagraphStyle(
            "Abstract",
            parent=base["BodyText"],
            fontName="Times-Roman",
            fontSize=9.2,
            leading=13,
            leftIndent=18,
            rightIndent=18,
            textColor=colors.HexColor("#2A3137"),
            spaceAfter=6,
        ),
        "quote": ParagraphStyle(
            "Quote",
            parent=base["BodyText"],
            fontName="Times-Italic",
            fontSize=10,
            leading=14,
            leftIndent=22,
            rightIndent=22,
            borderColor=BLUE,
            borderWidth=0,
            borderPadding=7,
            textColor=NAVY,
            spaceBefore=4,
            spaceAfter=8,
        ),
        "caption": ParagraphStyle(
            "Caption",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=10.5,
            textColor=GRAY,
            leftIndent=8,
            rightIndent=8,
            spaceAfter=9,
        ),
        "code": ParagraphStyle(
            "Code",
            parent=base["Code"],
            fontName="Courier",
            fontSize=7.7,
            leading=10,
            leftIndent=14,
            rightIndent=14,
            borderColor=LIGHT,
            borderWidth=0.6,
            borderPadding=8,
            backColor=colors.HexColor("#F7F8F9"),
            spaceBefore=4,
            spaceAfter=8,
        ),
        "math": ParagraphStyle(
            "Math",
            parent=base["Code"],
            fontName="Courier",
            fontSize=8.2,
            leading=11,
            alignment=TA_CENTER,
            textColor=NAVY,
            spaceBefore=4,
            spaceAfter=8,
        ),
        "list": ParagraphStyle(
            "List",
            parent=base["BodyText"],
            fontName="Times-Roman",
            fontSize=9.4,
            leading=13.2,
            textColor=colors.HexColor("#22272B"),
        ),
    }


def page_footer(canvas, doc) -> None:
    canvas.saveState()
    width, _ = LETTER
    canvas.setStrokeColor(LIGHT)
    canvas.line(0.68 * inch, 0.52 * inch, width - 0.68 * inch, 0.52 * inch)
    canvas.setFillColor(GRAY)
    canvas.setFont("Helvetica", 7.5)
    canvas.drawString(
        0.7 * inch,
        0.34 * inch,
        "Andrew Gracey | Continuous Cognition, Failure-Atomic Actuation | v0.1.2",
    )
    canvas.drawRightString(width - 0.7 * inch, 0.34 * inch, f"Page {doc.page}")
    canvas.restoreState()


def flush_paragraph(
    story: list,
    pending: list[str],
    style: ParagraphStyle,
) -> None:
    if pending:
        story.append(Paragraph(inline_markup(" ".join(pending)), style))
        pending.clear()


def image_flowable(markdown_path: str) -> Image:
    path = (SOURCE.parent / markdown_path).resolve()
    if path.suffix.lower() == ".svg":
        path = path.with_suffix(".png")
    image = Image(str(path))
    max_width = 6.65 * inch
    max_height = 4.3 * inch
    scale = min(max_width / image.imageWidth, max_height / image.imageHeight)
    image.drawWidth = image.imageWidth * scale
    image.drawHeight = image.imageHeight * scale
    image.hAlign = "CENTER"
    return image


def build_story() -> list:
    style = styles()
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    story: list = []
    pending: list[str] = []
    list_texts: list[str] = []
    list_kind = "bullet"
    in_code = False
    in_math = False
    code_lines: list[str] = []
    abstract_mode = False
    figure_pending: Image | None = None

    def flush_list() -> None:
        nonlocal list_texts
        if list_texts:
            items = [
                ListItem(Paragraph(inline_markup(item), style["list"]))
                for item in list_texts
            ]
            options = {
                "bulletType": list_kind,
                "leftIndent": 20,
                "bulletFontName": "Helvetica",
                "bulletFontSize": 8,
                "spaceAfter": 6,
            }
            if list_kind == "1":
                options["start"] = "1"
            story.append(ListFlowable(items, **options))
            list_texts = []

    for raw in lines:
        line = raw.rstrip()
        if in_code:
            if line.startswith("```"):
                story.append(Preformatted("\n".join(code_lines), style["code"]))
                code_lines = []
                in_code = False
            else:
                code_lines.append(line)
            continue
        if in_math:
            if line == r"\]":
                story.append(
                    Preformatted(latex_plain("\n".join(code_lines)), style["math"])
                )
                code_lines = []
                in_math = False
            else:
                code_lines.append(line)
            continue
        if line.startswith("```"):
            flush_paragraph(story, pending, style["abstract"] if abstract_mode else style["body"])
            flush_list()
            in_code = True
            continue
        if line == r"\[":
            flush_paragraph(story, pending, style["abstract"] if abstract_mode else style["body"])
            flush_list()
            in_math = True
            continue
        if not line:
            flush_paragraph(story, pending, style["abstract"] if abstract_mode else style["body"])
            flush_list()
            continue

        image_match = re.fullmatch(r"!\[([^\]]*)\]\(([^)]+)\)", line)
        if image_match:
            flush_paragraph(story, pending, style["body"])
            flush_list()
            figure_pending = image_flowable(image_match.group(2))
            continue
        if line.startswith("**Figure ") and figure_pending is not None:
            caption = Paragraph(inline_markup(line), style["caption"])
            story.append(KeepTogether([figure_pending, Spacer(1, 4), caption]))
            figure_pending = None
            continue

        if line.startswith("# "):
            flush_paragraph(story, pending, style["body"])
            if story:
                story.append(PageBreak())
            story.append(Spacer(1, 0.38 * inch))
            story.append(Paragraph(inline_markup(line[2:]), style["title"]))
            story.append(HRFlowable(width="100%", thickness=1.1, color=GREEN, spaceAfter=14))
            continue
        if line.startswith("## "):
            flush_paragraph(story, pending, style["body"])
            flush_list()
            heading = line[3:]
            if heading == "Abstract":
                abstract_mode = True
                story.append(Paragraph(heading, style["h1"]))
            elif re.match(r"\d+\.", heading):
                abstract_mode = False
                story.append(Paragraph(inline_markup(heading), style["h1"]))
            else:
                story.append(Paragraph(inline_markup(heading), style["subtitle"]))
            continue
        if line.startswith("### "):
            flush_paragraph(story, pending, style["body"])
            flush_list()
            story.append(Paragraph(inline_markup(line[4:]), style["h2"]))
            continue
        if line.startswith("**") and line.endswith("**") and len(story) < 10:
            flush_paragraph(story, pending, style["body"])
            story.append(Paragraph(inline_markup(line), style["author"]))
            continue
        if line.startswith("> "):
            flush_paragraph(story, pending, style["body"])
            flush_list()
            story.append(Paragraph(inline_markup(line[2:]), style["quote"]))
            continue
        ordered = re.match(r"^(\d+)\.\s+(.*)$", line)
        bullet = re.match(r"^-\s+(.*)$", line)
        if ordered or bullet:
            flush_paragraph(story, pending, style["body"])
            kind = "1" if ordered else "bullet"
            if list_texts and list_kind != kind:
                flush_list()
            list_kind = kind
            content = ordered.group(2) if ordered else bullet.group(1)
            list_texts.append(content)
            continue
        if line.startswith("   ") and list_texts:
            list_texts[-1] = f"{list_texts[-1]} {line.strip()}"
            continue
        pending.append(line.strip())

    flush_paragraph(story, pending, style["abstract"] if abstract_mode else style["body"])
    flush_list()
    if figure_pending is not None:
        story.append(figure_pending)
    return story


def main() -> None:
    document = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=LETTER,
        rightMargin=0.72 * inch,
        leftMargin=0.72 * inch,
        topMargin=0.66 * inch,
        bottomMargin=0.68 * inch,
        title="Continuous Cognition, Failure-Atomic Actuation",
        author="Andrew Gracey",
        subject="Failure-atomic admission for generated tool-call batches",
        creator="Failure-Atomic Tool Admission reproducible build",
    )
    def deterministic_canvas(*args, **kwargs):
        kwargs["invariant"] = 1
        return Canvas(*args, **kwargs)

    document.build(
        build_story(),
        onFirstPage=page_footer,
        onLaterPages=page_footer,
        canvasmaker=deterministic_canvas,
    )
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()
