"""
core/reporter.py — Professional Analyst PDF Report Generator v2.0
=================================================================
Produces a multi-section report that reads like a manually prepared
business analyst deliverable:

  Page 1 : Cover
  Page 2 : Executive Summary + Quality Score
  Page 3 : Data Overview & Cleaning Before/After
  Page 4+: Key Findings (Insights) — analyst-style prose
  Page N : Visualizations (curated, not every chart)
  Last   : Methodology & Technical Appendix
"""

import os
import uuid
from datetime import datetime

import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, HRFlowable, PageBreak, KeepTogether
)

W, H = A4

# ── Brand colors ───────────────────────────────────────────────────────────────
C = {
    'navy':    colors.HexColor('#1E3A5F'),
    'blue':    colors.HexColor('#2563EB'),
    'sky':     colors.HexColor('#0EA5E9'),
    'teal':    colors.HexColor('#0D9488'),
    'green':   colors.HexColor('#16A34A'),
    'amber':   colors.HexColor('#D97706'),
    'red':     colors.HexColor('#DC2626'),
    'slate':   colors.HexColor('#475569'),
    'muted':   colors.HexColor('#94A3B8'),
    'surface': colors.HexColor('#F8FAFC'),
    'border':  colors.HexColor('#E2E8F0'),
    'white':   colors.white,
    'black':   colors.HexColor('#0F172A'),
}

SEV = {
    'info':    C['blue'],
    'success': C['green'],
    'warning': C['amber'],
    'error':   C['red'],
}

USABLE_WIDTH = W - 3.6 * cm


def _h(col: str) -> str:
    return col.replace('_', ' ').title()

def _fmt(v, decimals=1) -> str:
    try:
        v = float(v)
        if abs(v) >= 1_000_000: return f'{v/1_000_000:.{decimals}f}M'
        if abs(v) >= 1_000:     return f'{v/1_000:.{decimals}f}K'
        return f'{v:,.{decimals}f}'
    except Exception:
        return str(v)


class ReportGenerator:

    def __init__(self, df, insights, charts, cleaning_report,
                 filename, original_rows, cleaned_rows):
        self.df              = df
        self.insights        = insights
        self.charts          = charts
        self.cleaning        = cleaning_report
        self.filename        = filename
        self.original_rows   = original_rows
        self.cleaned_rows    = cleaned_rows
        self.generated_at    = datetime.now()
        self.out_dir         = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 'static', 'uploads')
        os.makedirs(self.out_dir, exist_ok=True)

    # ── Public ─────────────────────────────────────────────────────────────────
    def generate(self) -> str:
        out_path = os.path.join(self.out_dir, f'report_{uuid.uuid4().hex}.pdf')

        doc = SimpleDocTemplate(
            out_path, pagesize=A4,
            leftMargin=1.8 * cm, rightMargin=1.8 * cm,
            topMargin=2.2 * cm, bottomMargin=1.8 * cm,
            title=f'Data Analysis Report — {self.filename}',
            author='AI Smart Data Analyzer',
        )

        story = []
        story += self._cover()
        story.append(PageBreak())
        story += self._executive_summary()
        story.append(PageBreak())
        story += self._data_overview()
        story += self._cleaning_comparison()
        story.append(PageBreak())
        story += self._findings_section()
        story.append(PageBreak())
        story += self._charts_section()
        story.append(PageBreak())
        story += self._methodology()

        doc.build(story,
                  onFirstPage=self._first_page_decor,
                  onLaterPages=self._running_header_footer)
        return out_path

    # ── Page decorators ────────────────────────────────────────────────────────
    def _first_page_decor(self, canvas, doc):
        """Decorative cover background."""
        canvas.saveState()
        # Navy top banner
        canvas.setFillColor(C['navy'])
        canvas.rect(0, H - 7 * cm, W, 7 * cm, fill=1, stroke=0)
        # Accent stripe
        canvas.setFillColor(C['blue'])
        canvas.rect(0, H - 7.3 * cm, W, 0.3 * cm, fill=1, stroke=0)
        # Bottom footer bar
        canvas.setFillColor(C['navy'])
        canvas.rect(0, 0, W, 1.2 * cm, fill=1, stroke=0)
        canvas.setFillColor(C['muted'])
        canvas.setFont('Helvetica', 7.5)
        canvas.drawString(1.8 * cm, 0.42 * cm, 'Confidential — For internal use only')
        canvas.drawRightString(W - 1.8 * cm, 0.42 * cm,
                               f'Generated: {self.generated_at.strftime("%d %B %Y")}')
        canvas.restoreState()

    def _running_header_footer(self, canvas, doc):
        canvas.saveState()
        # Header
        canvas.setFillColor(C['navy'])
        canvas.rect(0, H - 1.1 * cm, W, 1.1 * cm, fill=1, stroke=0)
        canvas.setFillColor(C['white'])
        canvas.setFont('Helvetica-Bold', 8)
        canvas.drawString(1.8 * cm, H - 0.72 * cm, 'AI Smart Data Analyzer')
        canvas.setFont('Helvetica', 8)
        canvas.drawCentredString(W / 2, H - 0.72 * cm, f'Analysis Report — {self.filename}')
        canvas.drawRightString(W - 1.8 * cm, H - 0.72 * cm,
                               self.generated_at.strftime('%d %b %Y'))

        # Footer
        canvas.setFillColor(C['surface'])
        canvas.rect(0, 0, W, 0.9 * cm, fill=1, stroke=0)
        canvas.setFillColor(C['slate'])
        canvas.setFont('Helvetica', 7.5)
        canvas.drawString(1.8 * cm, 0.32 * cm, 'Confidential')
        canvas.drawCentredString(W / 2, 0.32 * cm, f'Page {doc.page}')
        canvas.drawRightString(W - 1.8 * cm, 0.32 * cm,
                               'AI Smart Data Analyzer')
        canvas.restoreState()

    # ── Styles ─────────────────────────────────────────────────────────────────
    def _styles(self):
        s = getSampleStyleSheet()
        def p(name, **kw):
            base = kw.pop('parent', 'Normal')
            return ParagraphStyle(name, parent=s[base], **kw)
        return {
            'cover_title': p('ct', fontSize=28, textColor=C['white'],
                             fontName='Helvetica-Bold', alignment=TA_LEFT,
                             spaceAfter=10, leading=34),
            'cover_sub':   p('cs', fontSize=13, textColor=C['muted'],
                             alignment=TA_LEFT, spaceAfter=6),
            'cover_meta':  p('cm', fontSize=10, textColor=C['white'],
                             alignment=TA_LEFT, spaceAfter=4),
            'h1':          p('h1', fontSize=16, fontName='Helvetica-Bold',
                             textColor=C['navy'], spaceBefore=16, spaceAfter=6),
            'h2':          p('h2', fontSize=12, fontName='Helvetica-Bold',
                             textColor=C['blue'], spaceBefore=10, spaceAfter=4),
            'body':        p('body', fontSize=10, textColor=C['black'],
                             leading=15, spaceAfter=6, alignment=TA_JUSTIFY),
            'body_sm':     p('bsm', fontSize=9, textColor=C['slate'],
                             leading=13, spaceAfter=4),
            'label':       p('lbl', fontSize=8, textColor=C['muted'],
                             fontName='Helvetica-Bold',
                             spaceBefore=6, spaceAfter=2,
                             textTransform='uppercase'),
            'caption':     p('cap', fontSize=8, textColor=C['muted'],
                             alignment=TA_CENTER, spaceBefore=4, spaceAfter=12),
            'kpi_num':     p('kn', fontSize=22, fontName='Helvetica-Bold',
                             textColor=C['blue'], alignment=TA_CENTER),
            'kpi_lbl':     p('kl', fontSize=8, textColor=C['slate'],
                             alignment=TA_CENTER),
            'ins_title':   p('it', fontSize=10, fontName='Helvetica-Bold',
                             textColor=C['black'], spaceAfter=3),
            'ins_detail':  p('id', fontSize=9, textColor=C['slate'],
                             leading=13, spaceAfter=6),
        }

    # ── Cover ─────────────────────────────────────────────────────────────────
    def _cover(self):
        st = self._styles()
        items = [
            Spacer(1, 4.2 * cm),
            Paragraph('Data Analysis Report', st['cover_title']),
            Paragraph(self.filename, st['cover_sub']),
            Spacer(1, 0.6 * cm),
            Paragraph(f'Prepared by AI Smart Data Analyzer', st['cover_meta']),
            Paragraph(f'Date: {self.generated_at.strftime("%d %B %Y")}', st['cover_meta']),
            Paragraph(f'Records analyzed: {self.original_rows:,}', st['cover_meta']),
            Spacer(1, 4 * cm),
        ]

        # Quality score box (bottom of cover area)
        q_before = self.cleaning.get('quality_before', 0)
        q_after  = self.cleaning.get('quality_after', 0)
        score_data = [[
            Paragraph(f'<font color="#FFFFFF"><b>{q_after}/100</b></font>',
                      ParagraphStyle('qs', fontSize=28, alignment=TA_CENTER)),
            Paragraph(
                f'<font color="#94A3B8">Data Quality Score</font><br/>'
                f'<font color="#FFFFFF" size="9">Improved from {q_before} → {q_after}</font>',
                ParagraphStyle('qd', fontSize=10, alignment=TA_LEFT, leading=14))
        ]]
        score_tbl = Table(score_data, colWidths=[4 * cm, 8 * cm])
        score_tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), C['navy']),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 14),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 14),
            ('LEFTPADDING', (0, 0), (-1, -1), 16),
            ('RIGHTPADDING', (0, 0), (-1, -1), 16),
        ]))
        items.append(score_tbl)
        return items

    # ── Executive Summary ──────────────────────────────────────────────────────
    def _executive_summary(self):
        st   = self._styles()
        df   = self.df
        cr   = self.cleaning
        rows, cols = df.shape
        num_cols = df.select_dtypes(include='number').columns
        null_pct = df.isnull().sum().sum() / max(rows * cols, 1) * 100

        items = [
            Paragraph('Executive Summary', st['h1']),
            HRFlowable(width='100%', thickness=1.5, color=C['blue'], spaceAfter=10),
        ]

        # KPI cards row
        kpi_data = [[
            Paragraph(f'{rows:,}',          st['kpi_num']),
            Paragraph(f'{cols}',             st['kpi_num']),
            Paragraph(f'{len(num_cols)}',    st['kpi_num']),
            Paragraph(f'{100-null_pct:.1f}%',st['kpi_num']),
        ],[
            Paragraph('Clean Rows',          st['kpi_lbl']),
            Paragraph('Columns',             st['kpi_lbl']),
            Paragraph('Numeric Fields',      st['kpi_lbl']),
            Paragraph('Completeness',        st['kpi_lbl']),
        ]]
        kpi_tbl = Table(kpi_data, colWidths=[USABLE_WIDTH / 4] * 4,
                        rowHeights=[1.3 * cm, 0.6 * cm])
        kpi_style = [
            ('BACKGROUND', (i, 0), (i, 1), [C['blue'], C['teal'],
             C['green'], C['amber']][i]) for i in range(4)
        ] + [
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('ALIGN',    (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN',   (0, 0), (-1, -1), 'MIDDLE'),
            ('TEXTCOLOR',(0, 0), (-1, -1), C['white']),
            ('TOPPADDING',   (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING',(0, 0), (-1, -1), 8),
            ('LEFTPADDING',  (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]
        kpi_tbl.setStyle(TableStyle(kpi_style))
        items.append(kpi_tbl)
        items.append(Spacer(1, 0.5 * cm))

        # Summary prose
        overview = next((i for i in self.insights
                         if i.get('category') == 'Executive Overview'), None)
        if overview:
            items.append(Paragraph(overview['detail'], st['body']))

        # Key actions taken
        steps = cr.get('steps', [])
        if steps:
            items.append(Paragraph('Cleaning Actions Performed', st['h2']))
            for step in steps[:8]:
                items.append(Paragraph(f'• {step}', st['body_sm']))

        return items

    # ── Data Overview ──────────────────────────────────────────────────────────
    def _data_overview(self):
        st = self._styles()
        df = self.df
        items = [
            Paragraph('Data Overview', st['h1']),
            HRFlowable(width='100%', thickness=1.5, color=C['blue'], spaceAfter=10),
        ]

        # Schema table
        num_cols = list(df.select_dtypes(include='number').columns)
        schema   = self.cleaning.get('schema', {})

        hdr = ['Field Name', 'Type', 'Role', 'Non-Null', 'Unique', 'Sample Value']
        rows_data = [hdr]

        for col in list(df.columns)[:20]:   # cap at 20 cols
            role = schema.get(col, {}).get('role', '—')
            dtype = str(df[col].dtype)
            non_null = f'{df[col].notna().sum():,}'
            uniq     = f'{df[col].nunique():,}'
            try:
                sample = str(df[col].dropna().iloc[0])[:20]
            except Exception:
                sample = '—'
            rows_data.append([col[:22], dtype[:12], role, non_null, uniq, sample])

        col_widths = [4.8*cm, 2.2*cm, 2.2*cm, 2.0*cm, 1.8*cm, 3.2*cm]
        tbl = Table(rows_data, colWidths=col_widths, repeatRows=1)
        tbl.setStyle(self._table_style())
        items += [tbl, Spacer(1, 0.4 * cm)]

        # Descriptive stats for numeric
        if num_cols:
            items.append(Paragraph('Descriptive Statistics', st['h2']))
            desc = df[num_cols[:8]].describe().round(2)
            stat_hdr = ['Statistic'] + [col[:14] for col in num_cols[:8]]
            stat_rows = [stat_hdr]
            for stat in ['mean', 'std', 'min', '25%', '50%', '75%', 'max']:
                if stat in desc.index:
                    row = [stat]
                    for col in num_cols[:8]:
                        row.append(f'{desc.loc[stat, col]:,.2f}')
                    stat_rows.append(row)

            n_num = min(8, len(num_cols))
            stat_col_widths = [2.4*cm] + [(USABLE_WIDTH - 2.4*cm) / n_num] * n_num
            stat_tbl = Table(stat_rows, colWidths=stat_col_widths, repeatRows=1)
            stat_tbl.setStyle(self._table_style())
            items.append(stat_tbl)

        return items

    # ── Cleaning Before / After ────────────────────────────────────────────────
    def _cleaning_comparison(self):
        st = self._styles()
        cr = self.cleaning
        items = [
            Spacer(1, 0.5 * cm),
            Paragraph('Data Quality — Before vs After', st['h1']),
            HRFlowable(width='100%', thickness=1.5, color=C['blue'], spaceAfter=10),
        ]

        null_b = sum(cr.get('null_before', {}).values())
        null_a = sum(cr.get('null_after',  {}).values())
        dup_b  = cr.get('dup_before', 0)
        dup_a  = cr.get('dup_after', 0)
        q_b    = cr.get('quality_before', 0)
        q_a    = cr.get('quality_after', 0)

        comp_data = [
            ['Metric',          'Before Cleaning',   'After Cleaning',   'Improvement'],
            ['Total Rows',      f'{self.original_rows:,}', f'{self.cleaned_rows:,}',
             f'−{self.original_rows - self.cleaned_rows:,}'],
            ['Missing Values',  f'{null_b:,}',        f'{null_a:,}',
             f'−{null_b - null_a:,}'],
            ['Duplicate Rows',  f'{dup_b:,}',         f'{dup_a:,}',
             f'−{dup_b - dup_a:,}'],
            ['Quality Score',   f'{q_b}/100',         f'{q_a}/100',
             f'+{q_a - q_b:.1f} pts'],
        ]

        col_w = [4.5*cm, 3.5*cm, 3.5*cm, 3.5*cm]
        tbl   = Table(comp_data, colWidths=col_w)
        style = self._table_style()
        style.add('BACKGROUND', (3, 1), (3, -1), colors.HexColor('#ECFDF5'))
        style.add('TEXTCOLOR',  (3, 1), (3, -1), C['green'])
        style.add('FONTNAME',   (3, 1), (3, -1), 'Helvetica-Bold')
        tbl.setStyle(style)
        items.append(tbl)

        # Missing value detail
        missing = cr.get('missing_handled', {})
        if missing:
            items += [
                Spacer(1, 0.4 * cm),
                Paragraph('Missing Value Imputation Detail', st['h2'])
            ]
            m_hdr  = ['Field', 'Count', '% Missing', 'Strategy', 'Fill Value']
            m_rows = [m_hdr]
            for col, info in list(missing.items())[:12]:
                m_rows.append([
                    col[:22],
                    f'{info["count"]:,}',
                    f'{info["pct"]:.1f}%',
                    info['strategy'][:30],
                    str(info.get('fill_value', ''))[:20],
                ])
            m_tbl = Table(m_rows,
                          colWidths=[4.5*cm, 1.8*cm, 2.0*cm, 4.5*cm, 3.2*cm],
                          repeatRows=1)
            m_tbl.setStyle(self._table_style())
            items.append(m_tbl)

        return items

    # ── Key Findings ───────────────────────────────────────────────────────────
    def _findings_section(self):
        st    = self._styles()
        items = [
            Paragraph('Key Findings', st['h1']),
            HRFlowable(width='100%', thickness=1.5, color=C['blue'], spaceAfter=12),
        ]

        # Group insights by category
        categories = {}
        for ins in self.insights:
            cat = ins.get('category', 'Other')
            categories.setdefault(cat, []).append(ins)

        for cat, cat_insights in categories.items():
            if cat == 'Executive Overview':
                continue    # Already in exec summary

            items.append(Paragraph(cat, st['h2']))

            for ins in cat_insights:
                sev_color = SEV.get(ins.get('severity', 'info'), C['blue'])
                icon  = ins.get('icon', '•')
                title = ins.get('title', '')
                detail= ins.get('detail', '')

                # Colour-coded left border via a 2-col mini-table
                inner = Table(
                    [[Paragraph(f'{icon}  {title}', st['ins_title']),
                      Paragraph(detail, st['ins_detail'])]],
                    colWidths=[USABLE_WIDTH * 0.35, USABLE_WIDTH * 0.65]
                )
                inner.setStyle(TableStyle([
                    ('VALIGN',  (0, 0), (-1, -1), 'TOP'),
                    ('LEFTPADDING',  (0, 0), (-1, -1), 6),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                    ('TOPPADDING',   (0, 0), (-1, -1), 6),
                    ('BOTTOMPADDING',(0, 0), (-1, -1), 6),
                ]))

                wrapper = Table(
                    [[inner]],
                    colWidths=[USABLE_WIDTH]
                )
                wrapper.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), C['surface']),
                    ('LINEAFTER',  (0, 0), (0, -1), 3, sev_color),
                    ('LEFTPADDING',(0, 0), (-1, -1), 0),
                    ('TOPPADDING', (0, 0), (-1, -1), 0),
                    ('BOTTOMPADDING',(0, 0), (-1, -1), 0),
                ]))
                items.append(KeepTogether([wrapper, Spacer(1, 6)]))

        return items

    # ── Charts ─────────────────────────────────────────────────────────────────
    def _charts_section(self):
        st    = self._styles()
        items = [
            Paragraph('Visualizations', st['h1']),
            HRFlowable(width='100%', thickness=1.5, color=C['blue'], spaceAfter=10),
        ]

        charts_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 'static', 'charts')

        # Skip KPI chart in PDF (it's tiny), prioritize meaningful charts
        priority_types = ['histogram', 'bar', 'line', 'grouped', 'heatmap', 'box']
        sorted_charts  = sorted(
            self.charts,
            key=lambda c: priority_types.index(c['type'])
                          if c['type'] in priority_types else 99
        )

        for chart in sorted_charts[:8]:    # Max 8 charts
            url  = chart.get('url', '')
            rel  = os.path.basename(url)
            path = os.path.join(charts_dir, rel)

            if not os.path.exists(path):
                continue
            try:
                img = Image(path, width=15 * cm, height=8.2 * cm)
                img.hAlign = 'CENTER'
                items += [
                    KeepTogether([
                        img,
                        Paragraph(chart.get('title', ''), st['caption']),
                    ]),
                    Spacer(1, 0.3 * cm),
                ]
            except Exception:
                pass

        return items

    # ── Methodology ───────────────────────────────────────────────────────────
    def _methodology(self):
        st = self._styles()
        cr = self.cleaning
        items = [
            Paragraph('Methodology & Technical Appendix', st['h1']),
            HRFlowable(width='100%', thickness=1.5, color=C['blue'], spaceAfter=10),
            Paragraph(
                'This report was generated by the AI Smart Data Analyzer pipeline. '
                'The following methodology was applied:', st['body']),
            Spacer(1, 0.3 * cm),
        ]

        steps = [
            ('Schema Normalization',
             'Column names standardized to snake_case. Data types classified by content analysis '
             'into roles: numeric, categorical, date, currency, percentage, identifier, email, phone.'),
            ('Missing Value Imputation',
             'Strategy selected per column: median for skewed numeric distributions, mean for '
             'near-normal distributions, mode for low-sparsity categoricals, "Unknown" for '
             'high-sparsity categoricals, forward/backward fill for temporal fields.'),
            ('Duplicate Resolution',
             'Exact row duplicates removed. Business-key duplicates identified using '
             'ID + date combinations where present.'),
            ('Text Normalization',
             'Hidden Unicode characters removed. Categorical labels normalized to Title Case. '
             'Whitespace standardized. Fake null strings (null, n/a, —, etc.) converted to NaN.'),
            ('Date Parsing & Enrichment',
             'Mixed date formats parsed via infer_datetime_format. Derived temporal features '
             '(year, month, quarter) created for columns with ≥10 unique dates.'),
            ('Outlier Treatment',
             'IQR Tukey fences applied (Q1 − 1.5×IQR, Q3 + 1.5×IQR). '
             'Z-score cross-validation performed. Values capped (Winsorized) rather than deleted. '
             'Identifier and protected columns excluded.'),
            ('Quality Scoring',
             'Composite score out of 100: Completeness (40 pts), Uniqueness (20 pts), '
             'Consistency (30 pts), Validity baseline (10 pts).'),
        ]

        for title, detail in steps:
            items += [
                Paragraph(title, st['h2']),
                Paragraph(detail, st['body_sm']),
                Spacer(1, 0.2 * cm),
            ]

        # Column rename log
        renames = cr.get('column_renames', {})
        if renames:
            items += [
                Paragraph('Column Renames Applied', st['h2']),
                Table(
                    [['Original Name', 'Standardized Name']] +
                    [[k, v] for k, v in list(renames.items())[:15]],
                    colWidths=[8*cm, 8*cm],
                    style=self._table_style()
                ),
            ]

        items += [
            Spacer(1, 1.5 * cm),
            Paragraph(
                f'Report generated: {self.generated_at.strftime("%d %B %Y at %H:%M:%S")}',
                st['body_sm']),
            Paragraph('AI Smart Data Analyzer — Portfolio Project', st['body_sm']),
        ]
        return items

    # ── Table style ────────────────────────────────────────────────────────────
    def _table_style(self) -> TableStyle:
        return TableStyle([
            ('BACKGROUND',    (0, 0), (-1, 0),  C['navy']),
            ('TEXTCOLOR',     (0, 0), (-1, 0),  C['white']),
            ('FONTNAME',      (0, 0), (-1, 0),  'Helvetica-Bold'),
            ('FONTSIZE',      (0, 0), (-1, -1), 8),
            ('ALIGN',         (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING',    (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING',   (0, 0), (-1, -1), 6),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
            ('ROWBACKGROUNDS',(0, 1), (-1, -1),
             [C['white'], C['surface']]),
            ('TEXTCOLOR',     (0, 1), (-1, -1), C['black']),
            ('GRID',          (0, 0), (-1, -1), 0.4, C['border']),
            ('LINEBELOW',     (0, 0), (-1, 0),  1.0, C['blue']),
        ])
