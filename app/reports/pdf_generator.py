import io
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def generate_business_pdf_report(
    business_name: str,
    report_title: str,
    kpis: list[dict[str, str | float | int]],
    table_headers: list[str],
    table_rows: list[list[str]],
    insights: list[str] | None = None,
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )
    story = []
    styles = getSampleStyleSheet()

    # Title style
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0f172a"),
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#64748b"),
    )
    section_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=12,
        spaceAfter=6,
    )
    cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#334155"),
    )
    header_cell_style = ParagraphStyle(
        "HeaderCell",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        textColor=colors.white,
    )

    # Header
    story.append(Paragraph(business_name.upper(), subtitle_style))
    story.append(Spacer(1, 2))
    story.append(Paragraph(report_title, title_style))
    story.append(Paragraph(f"Generated on {datetime.now().strftime('%B %d, %Y at %H:%M')}", subtitle_style))
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e2e8f0"), spaceAfter=15))

    # KPI Summary Cards Grid
    if kpis:
        story.append(Paragraph("Executive Summary KPIs", section_style))
        kpi_cells = []
        for k in kpis:
            raw_val = k.get("value")
            if raw_val is None:
                val_str = "—"
            elif k.get("format") == "currency":
                try:
                    val_str = f"₹{float(raw_val):,.2f}"
                except (ValueError, TypeError):
                    val_str = str(raw_val)
            elif k.get("format") == "percentage":
                try:
                    val_str = f"{float(raw_val):.1f}%"
                except (ValueError, TypeError):
                    val_str = str(raw_val)
            elif k.get("format") == "number":
                try:
                    val_str = f"{int(float(raw_val)):,}"
                except (ValueError, TypeError):
                    val_str = str(raw_val)
            else:
                val_str = str(raw_val)

            card_text = f"<b>{k.get('label', '')}</b><br/><font size=12 color='#0f172a'><b>{val_str}</b></font>"
            kpi_cells.append(Paragraph(card_text, cell_style))

        # Chunk KPIs into rows of 3
        grid_data = []
        for i in range(0, len(kpi_cells), 3):
            chunk = kpi_cells[i:i+3]
            while len(chunk) < 3:
                chunk.append(Paragraph("", cell_style))
            grid_data.append(chunk)

        kpi_table = Table(grid_data, colWidths=[180, 180, 180])
        kpi_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ]))
        story.append(kpi_table)
        story.append(Spacer(1, 15))

    # Business Insights Section
    if insights:
        story.append(Paragraph("Automated Business Insights", section_style))
        for ins in insights:
            story.append(Paragraph(f"• {ins}", cell_style))
            story.append(Spacer(1, 3))
        story.append(Spacer(1, 10))

    # Data Table Section
    if table_headers and table_rows:
        story.append(Paragraph("Detailed Data Report", section_style))
        formatted_table = [[Paragraph(h, header_cell_style) for h in table_headers]]
        for row in table_rows[:100]: # Cap at 100 rows for PDF rendering efficiency
            formatted_table.append([Paragraph(str(c), cell_style) for c in row])

        col_w = 540 / len(table_headers)
        data_table = Table(formatted_table, colWidths=[col_w] * len(table_headers))
        data_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ]))
        story.append(data_table)

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
