"""
ReportGenerator — Creates a beautiful PDF analysis report using ReportLab.
"""

import os
import uuid
from datetime import datetime
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, HRFlowable, PageBreak
)

W, H = A4

# ── Color Palette ─────────────────────────────────────────────────────────────
C = {
    'bg':       colors.HexColor('#0F0F1A'),
    'surface':  colors.HexColor('#1A1A2E'),
    'primary':  colors.HexColor('#6C63FF'),
    'secondary':colors.HexColor('#2DD4BF'),
    'accent':   colors.HexColor('#F59E0B'),
    'danger':   colors.HexColor('#EF4444'),
    'success':  colors.HexColor('#10B981'),
    'warning':  colors.HexColor('#F59E0B'),
    'text':     colors.HexColor('#E2E8F0'),
    'muted':    colors.HexColor('#94A3B8'),
    'white':    colors.white,
    'dark':     colors.HexColor('#0D0D1A'),
}

SEV_COLOR = {
    'info':    C['primary'],
    'warning': C['warning'],
    'success': C['success'],
    'error':   C['danger'],
}


class ReportGenerator:
    def __init__(self, df, insights, charts, cleaning_report,
                 filename, original_rows, cleaned_rows):
        self.df = df
        self.insights = insights
        self.charts = charts
        self.cleaning = cleaning_report
        self.filename = filename
        self.original_rows = original_rows
        self.cleaned_rows = cleaned_rows
        self.out_dir = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
        os.makedirs(self.out_dir, exist_ok=True)

    def generate(self):
        out_path = os.path.join(self.out_dir, f'report_{uuid.uuid4().hex}.pdf')
        doc = SimpleDocTemplate(
            out_path, pagesize=A4,
            leftMargin=1.8*cm, rightMargin=1.8*cm,
            topMargin=2*cm, bottomMargin=2*cm,
            title='AI Smart Data Analyzer Report'
        )

        styles = getSampleStyleSheet()
        story = []

        # ── Cover ─────────────────────────────────────────────────────────────
        story += self._cover(styles)
        story.append(PageBreak())

        # ── Summary Cards ─────────────────────────────────────────────────────
        story += self._summary_section(styles)
        story.append(Spacer(1, 0.5*cm))

        # ── Cleaning Report ───────────────────────────────────────────────────
        story += self._cleaning_section(styles)
        story.append(Spacer(1, 0.4*cm))

        # ── Stats Table ───────────────────────────────────────────────────────
        story += self._stats_section(styles)
        story.append(PageBreak())

        # ── AI Insights ───────────────────────────────────────────────────────
        story += self._insights_section(styles)
        story.append(PageBreak())

        # ── Charts ────────────────────────────────────────────────────────────
        story += self._charts_section(styles)

        doc.build(story, onFirstPage=self._header_footer,
                  onLaterPages=self._header_footer)
        return out_path

    def _header_footer(self, canvas, doc):
        canvas.saveState()
        # Header bar
        canvas.setFillColor(C['surface'])
        canvas.rect(0, H - 1.2*cm, W, 1.2*cm, fill=1, stroke=0)
        canvas.setFillColor(C['primary'])
        canvas.setFont('Helvetica-Bold', 9)
        canvas.drawString(1.8*cm, H - 0.8*cm, 'AI Smart Data Analyzer')
        canvas.setFillColor(C['muted'])
        canvas.setFont('Helvetica', 8)
        canvas.drawRightString(W - 1.8*cm, H - 0.8*cm,
                               datetime.now().strftime('%B %d, %Y'))

        # Footer bar
        canvas.setFillColor(C['surface'])
        canvas.rect(0, 0, W, 1*cm, fill=1, stroke=0)
        canvas.setFillColor(C['muted'])
        canvas.setFont('Helvetica', 8)
        canvas.drawString(1.8*cm, 0.35*cm, f'Source: {self.filename}')
        canvas.drawRightString(W - 1.8*cm, 0.35*cm, f'Page {doc.page}')
        canvas.restoreState()

    def _cover(self, styles):
        title_s = ParagraphStyle('ct', fontSize=28, textColor=C['primary'],
                                 alignment=TA_CENTER, fontName='Helvetica-Bold',
                                 spaceAfter=8)
        sub_s = ParagraphStyle('cs', fontSize=13, textColor=C['muted'],
                               alignment=TA_CENTER, spaceAfter=30)
        meta_s = ParagraphStyle('cm', fontSize=10, textColor=C['muted'],
                                alignment=TA_CENTER, spaceAfter=6)

        items = [
            Spacer(1, 2.5*cm),
            Paragraph('AI Smart Data Analyzer', title_s),
            Paragraph('Automated Data Analysis Report', sub_s),
            HRFlowable(width='80%', thickness=1.5, color=C['primary'],
                       hAlign='CENTER'),
            Spacer(1, 0.8*cm),
            Paragraph(f'<b>File:</b> {self.filename}', meta_s),
            Paragraph(f'<b>Generated:</b> {datetime.now().strftime("%B %d, %Y at %H:%M")}', meta_s),
            Paragraph(f'<b>Original Rows:</b> {self.original_rows:,}', meta_s),
            Paragraph(f'<b>Cleaned Rows:</b> {self.cleaned_rows:,}', meta_s),
            Paragraph(f'<b>Columns Analyzed:</b> {len(self.df.columns)}', meta_s),
        ]
        return items

    def _summary_section(self, styles):
        h2 = ParagraphStyle('h2', fontSize=14, fontName='Helvetica-Bold',
                             textColor=C['primary'], spaceBefore=10, spaceAfter=8)
        items = [Paragraph('Executive Summary', h2)]

        numeric_cols = list(self.df.select_dtypes(include='number').columns)
        cat_cols = list(self.df.select_dtypes(include='object').columns)
        date_cols = list(self.df.select_dtypes(include='datetime').columns)
        completeness = (1 - self.df.isnull().sum().sum() / (self.df.shape[0] * self.df.shape[1])) * 100

        cards = [
            ('Total Rows', f'{self.cleaned_rows:,}', C['primary']),
            ('Columns', f'{len(self.df.columns)}', C['secondary']),
            ('Numeric', f'{len(numeric_cols)}', C['accent']),
            ('Completeness', f'{completeness:.1f}%', C['success']),
        ]

        tdata = [[Paragraph(f'<font color="white"><b>{v}</b><br/><font size="8" color="#94A3B8">{l}</font></font>', 
                            ParagraphStyle('cd', fontSize=16, alignment=TA_CENTER)) 
                  for l, v, c in cards]]
        tcolors_row = [c for l, v, c in cards]

        tbl = Table([tdata[0]], colWidths=[(W - 3.6*cm) / 4] * 4, rowHeights=[2*cm])
        style = [
            ('BACKGROUND', (i, 0), (i, 0), tcolors_row[i]) for i in range(4)
        ] + [
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ROUNDEDCORNERS', [6]),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]
        tbl.setStyle(TableStyle(style))
        items.append(tbl)
        return items

    def _cleaning_section(self, styles):
        h2 = ParagraphStyle('h2c', fontSize=14, fontName='Helvetica-Bold',
                             textColor=C['primary'], spaceBefore=16, spaceAfter=8)
        body = ParagraphStyle('body', fontSize=9, textColor=C['text'], leading=14)
        items = [Paragraph('Data Cleaning Summary', h2)]

        steps = self.cleaning.get('steps', [])
        if steps:
            for step in steps:
                items.append(Paragraph(f'• {step}', body))
                items.append(Spacer(1, 2))
        else:
            items.append(Paragraph('• No cleaning steps were required.', body))

        return items

    def _stats_section(self, styles):
        h2 = ParagraphStyle('h2s', fontSize=14, fontName='Helvetica-Bold',
                             textColor=C['primary'], spaceBefore=16, spaceAfter=8)
        items = [Paragraph('Descriptive Statistics', h2)]

        numeric_cols = list(self.df.select_dtypes(include='number').columns)
        if not numeric_cols:
            return items

        header = ['Column', 'Mean', 'Median', 'Std Dev', 'Min', 'Max', 'Missing']
        data = [header]
        for col in numeric_cols[:10]:
            s = self.df[col]
            data.append([
                col[:18],
                f'{s.mean():.2f}',
                f'{s.median():.2f}',
                f'{s.std():.2f}',
                f'{s.min():.2f}',
                f'{s.max():.2f}',
                str(int(s.isnull().sum())),
            ])

        col_w = (W - 3.6*cm) / 7
        tbl = Table(data, colWidths=[col_w * 2.2] + [col_w * 0.8] * 6,
                    repeatRows=1)
        style = [
            ('BACKGROUND', (0, 0), (-1, 0), C['primary']),
            ('TEXTCOLOR', (0, 0), (-1, 0), C['white']),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#1A1A2E'), colors.HexColor('#16213E')]),
            ('TEXTCOLOR', (0, 1), (-1, -1), C['text']),
            ('GRID', (0, 0), (-1, -1), 0.3, C['muted']),
        ]
        tbl.setStyle(TableStyle(style))
        items.append(tbl)
        return items

    def _insights_section(self, styles):
        h2 = ParagraphStyle('h2i', fontSize=14, fontName='Helvetica-Bold',
                             textColor=C['primary'], spaceBefore=16, spaceAfter=8)
        title_s = ParagraphStyle('it', fontSize=10, fontName='Helvetica-Bold',
                                 textColor=C['text'], spaceAfter=3)
        detail_s = ParagraphStyle('id', fontSize=9, textColor=C['muted'],
                                  leading=13, spaceAfter=8)
        cat_s = ParagraphStyle('ic', fontSize=7, textColor=C['muted'],
                               spaceAfter=2)

        items = [Paragraph('AI-Generated Insights', h2)]

        for ins in self.insights:
            sev_color = SEV_COLOR.get(ins.get('severity', 'info'), C['primary'])
            cat = ins.get('category', '')
            icon = ins.get('icon', '•')
            title = ins.get('title', '')
            detail = ins.get('detail', '')

            items.append(Paragraph(
                f'<font color="#{sev_color.hexval()[2:]}">{icon}</font>  '
                f'<font color="#94A3B8">{cat}</font>', cat_s))
            items.append(Paragraph(title, title_s))
            items.append(Paragraph(detail, detail_s))
            items.append(HRFlowable(width='100%', thickness=0.3,
                                    color=colors.HexColor('#1E293B')))
            items.append(Spacer(1, 4))

        return items

    def _charts_section(self, styles):
        h2 = ParagraphStyle('h2ch', fontSize=14, fontName='Helvetica-Bold',
                             textColor=C['primary'], spaceBefore=16, spaceAfter=8)
        cap = ParagraphStyle('cap', fontSize=8, textColor=C['muted'],
                             alignment=TA_CENTER, spaceBefore=4, spaceAfter=16)

        items = [Paragraph('Visualizations', h2)]

        charts_dir = os.path.join(os.path.dirname(__file__), 'static', 'charts')

        for chart in self.charts:
            url = chart.get('url', '')
            # Convert URL to absolute path
            rel = url.replace('/static/charts/', '')
            path = os.path.join(charts_dir, rel)

            if os.path.exists(path):
                try:
                    img = Image(path, width=15*cm, height=8*cm)
                    img.hAlign = 'CENTER'
                    items.append(img)
                    items.append(Paragraph(chart.get('title', ''), cap))
                except Exception:
                    pass

        return items
