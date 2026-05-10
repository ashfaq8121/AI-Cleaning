"""
core/visualizer.py — Power BI-Quality Chart Generator v2.0
===========================================================
Design principles:
- Business-style color palette (muted, professional)
- Clean white backgrounds with subtle grid
- Proper titles, subtitles, axis labels
- Sorted bars, top-N handling
- Trend lines on time series
- Annotated correlation heatmap
- KPI summary chart
"""

import os
import uuid
import warnings
import textwrap

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import seaborn as sns
from scipy import stats as sp_stats

warnings.filterwarnings('ignore')

# ── Professional color palette (Power BI–style) ────────────────────────────────
PALETTE = {
    'primary':   '#2563EB',   # Microsoft blue
    'secondary': '#0EA5E9',   # Sky blue
    'accent':    '#F59E0B',   # Amber
    'success':   '#16A34A',   # Green
    'danger':    '#DC2626',   # Red
    'neutral':   '#64748B',   # Slate
    'bg':        '#FFFFFF',
    'surface':   '#F8FAFC',
    'grid':      '#E2E8F0',
    'text':      '#1E293B',
    'text2':     '#475569',
    'border':    '#CBD5E1',
}

# Categorical sequence (7 distinct, colorblind-friendly)
CAT_COLORS = [
    '#2563EB','#0EA5E9','#16A34A','#F59E0B',
    '#7C3AED','#DC2626','#0891B2',
]

FONT_FAMILY = 'DejaVu Sans'


def _base_style():
    """Apply global matplotlib style."""
    plt.rcParams.update({
        'figure.facecolor':    PALETTE['bg'],
        'axes.facecolor':      PALETTE['surface'],
        'axes.edgecolor':      PALETTE['border'],
        'axes.labelcolor':     PALETTE['text2'],
        'axes.labelsize':      10,
        'axes.titlesize':      13,
        'axes.titlecolor':     PALETTE['text'],
        'axes.titleweight':    'bold',
        'axes.titlepad':       12,
        'axes.spines.top':     False,
        'axes.spines.right':   False,
        'axes.grid':           True,
        'axes.axisbelow':      True,
        'grid.color':          PALETTE['grid'],
        'grid.linewidth':      0.7,
        'grid.alpha':          1.0,
        'text.color':          PALETTE['text'],
        'xtick.color':         PALETTE['text2'],
        'ytick.color':         PALETTE['text2'],
        'xtick.labelsize':     9,
        'ytick.labelsize':     9,
        'font.family':         FONT_FAMILY,
        'font.size':           10,
        'legend.fontsize':     9,
        'legend.framealpha':   0.9,
        'legend.edgecolor':    PALETTE['border'],
        'figure.dpi':          110,
    })


def _add_subtitle(ax, text: str, fontsize: int = 9):
    ax.text(0, 1.02, text, transform=ax.transAxes,
            fontsize=fontsize, color=PALETTE['text2'],
            va='bottom', ha='left')


def _watermark(fig):
    fig.text(0.99, 0.01, 'AI Smart Data Analyzer',
             ha='right', va='bottom', fontsize=7,
             color=PALETTE['border'], style='italic')


# ══════════════════════════════════════════════════════════════════════════════
class DataVisualizer:

    def __init__(self, df: pd.DataFrame, charts_dir: str, schema: dict = None):
        self.df         = df
        self.charts_dir = charts_dir
        self.schema     = schema or {}
        os.makedirs(charts_dir, exist_ok=True)
        _base_style()

        # Derived column lists
        self.num_cols  = [c for c in df.select_dtypes(include='number').columns
                          if self.schema.get(c, {}).get('role') not in ('id',)]
        self.cat_cols  = [c for c in df.select_dtypes(include='object').columns
                          if self.schema.get(c, {}).get('role') not in ('id','email','phone')]
        self.date_cols = list(df.select_dtypes(include='datetime').columns)

    # ── Public ─────────────────────────────────────────────────────────────────
    def generate_all_charts(self) -> list:
        charts = []

        # KPI summary strip
        if self.num_cols:
            c = self._kpi_summary()
            if c: charts.append(c)

        # Histograms (top 4 numeric)
        for col in self.num_cols[:4]:
            c = self._histogram(col)
            if c: charts.append(c)

        # Bar charts (top 4 categorical, sorted, top-N)
        for col in self.cat_cols[:4]:
            c = self._bar_chart(col)
            if c: charts.append(c)

        # Time-series (first date × first 2 numeric)
        for date_col in self.date_cols[:1]:
            for val_col in self.num_cols[:2]:
                c = self._line_chart(date_col, val_col)
                if c: charts.append(c)

        # Correlation heatmap
        if len(self.num_cols) >= 2:
            c = self._correlation_heatmap()
            if c: charts.append(c)

        # Box plot comparison
        if len(self.num_cols) >= 2:
            c = self._box_plot()
            if c: charts.append(c)

        # Category × numeric (grouped bar) if both exist
        if self.cat_cols and len(self.num_cols) >= 1:
            c = self._grouped_summary()
            if c: charts.append(c)

        return charts

    # ── KPI Summary Card ───────────────────────────────────────────────────────
    def _kpi_summary(self):
        try:
            cols = self.num_cols[:5]
            n    = len(cols)
            fig, axes = plt.subplots(1, n, figsize=(n * 2.8, 2.2))
            if n == 1:
                axes = [axes]
            fig.patch.set_facecolor(PALETTE['bg'])

            for ax, col in zip(axes, cols):
                s     = self.df[col].dropna()
                val   = s.sum() if s.sum() > 9999 else s.mean()
                label = 'Total' if s.sum() > 9999 else 'Mean'
                ax.set_facecolor('#EFF6FF')
                ax.axis('off')

                # Big number
                ax.text(0.5, 0.6, _fmt_number(val),
                        ha='center', va='center',
                        fontsize=16, fontweight='bold',
                        color=PALETTE['primary'], transform=ax.transAxes)
                # Label
                ax.text(0.5, 0.22, f'{label} {_truncate(col, 14)}',
                        ha='center', va='center',
                        fontsize=8, color=PALETTE['text2'],
                        transform=ax.transAxes)

                # Subtle border
                for spine in ax.spines.values():
                    spine.set_visible(True)
                    spine.set_color(PALETTE['primary'])
                    spine.set_linewidth(0.8)

            fig.suptitle('Key Metrics at a Glance', fontsize=11,
                         fontweight='bold', color=PALETTE['text'], y=1.02)
            plt.tight_layout(pad=0.4)
            _watermark(fig)
            return self._save(fig, 'kpi_summary', 'kpi', 'Key Performance Indicators')
        except Exception as e:
            return None

    # ── Histogram ──────────────────────────────────────────────────────────────
    def _histogram(self, col: str):
        try:
            data = self.df[col].dropna()
            if len(data) < 5:
                return None

            fig, ax = plt.subplots(figsize=(7, 4.2))

            # Histogram
            n, bins, patches = ax.hist(data, bins='auto',
                                       color=PALETTE['primary'], alpha=0.82,
                                       edgecolor='white', linewidth=0.5)

            # KDE curve
            try:
                from scipy.stats import gaussian_kde
                kde_x = np.linspace(data.min(), data.max(), 300)
                kde   = gaussian_kde(data, bw_method='scott')
                scale = len(data) * (bins[1] - bins[0])
                ax.plot(kde_x, kde(kde_x) * scale,
                        color=PALETTE['danger'], lw=2, label='Density')
            except Exception:
                pass

            # Mean & median
            ax.axvline(data.mean(),   color=PALETTE['accent'], lw=1.8,
                       ls='--', label=f'Mean: {data.mean():.1f}')
            ax.axvline(data.median(), color=PALETTE['success'], lw=1.8,
                       ls='--', label=f'Median: {data.median():.1f}')

            ax.set_title(f'Distribution of {_humanize(col)}')
            _add_subtitle(ax, f'n={len(data):,}  |  Std Dev: {data.std():.2f}  |  '
                              f'Skew: {data.skew():.2f}')
            ax.set_xlabel(_humanize(col))
            ax.set_ylabel('Frequency')
            ax.legend()
            ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda x, _: f'{int(x):,}'))
            plt.tight_layout()
            _watermark(fig)
            return self._save(fig, col, 'histogram', f'Distribution of {_humanize(col)}')
        except Exception:
            return None

    # ── Bar Chart ──────────────────────────────────────────────────────────────
    def _bar_chart(self, col: str):
        try:
            vc = self.df[col].dropna().value_counts()
            if len(vc) < 2:
                return None

            TOP_N = 12
            if len(vc) > TOP_N:
                other = vc.iloc[TOP_N:].sum()
                vc    = vc.head(TOP_N)
                vc['Other'] = other

            # Sort ascending for horizontal bar (so largest is on top)
            vc = vc.sort_values(ascending=True)

            fig, ax = plt.subplots(figsize=(8, max(3.5, len(vc) * 0.42)))

            colors = [PALETTE['primary']] * len(vc)
            if 'Other' in vc.index:
                colors[-1] = PALETTE['neutral']   # Grey out "Other"

            bars = ax.barh(vc.index.astype(str), vc.values,
                           color=colors, height=0.62, alpha=0.90)

            # Value labels
            x_max = vc.values.max()
            for bar, val in zip(bars, vc.values):
                pct = val / vc.sum() * 100
                ax.text(bar.get_width() + x_max * 0.01,
                        bar.get_y() + bar.get_height() / 2,
                        f'{val:,} ({pct:.1f}%)',
                        va='center', fontsize=8, color=PALETTE['text2'])

            ax.set_xlim(0, x_max * 1.25)
            ax.set_title(f'Category Breakdown — {_humanize(col)}')
            _add_subtitle(ax, f'{vc.sum():,} total records · Top {min(TOP_N, len(vc))} shown')
            ax.set_xlabel('Count')
            ax.xaxis.set_major_formatter(mtick.FuncFormatter(lambda x, _: f'{int(x):,}'))
            ax.spines['left'].set_visible(False)
            ax.tick_params(axis='y', length=0)
            plt.tight_layout()
            _watermark(fig)
            return self._save(fig, col, 'bar', f'Category Breakdown — {_humanize(col)}')
        except Exception:
            return None

    # ── Line Chart ─────────────────────────────────────────────────────────────
    def _line_chart(self, date_col: str, val_col: str):
        try:
            df_t = self.df[[date_col, val_col]].dropna().copy()
            df_t = df_t.sort_values(date_col).set_index(date_col)

            # Resample monthly
            monthly = df_t[val_col].resample('M').mean().dropna()
            if len(monthly) < 3:
                return None

            fig, ax = plt.subplots(figsize=(9, 4.5))

            ax.plot(monthly.index, monthly.values,
                    color=PALETTE['primary'], lw=2.2, zorder=3, label='Monthly Average')
            ax.fill_between(monthly.index, monthly.values,
                            alpha=0.10, color=PALETTE['primary'])

            # Rolling average
            if len(monthly) >= 4:
                roll = monthly.rolling(3, min_periods=1).mean()
                ax.plot(roll.index, roll.values,
                        color=PALETTE['accent'], lw=1.5, ls='--',
                        label='3-Month Rolling Avg', alpha=0.85)

            # Trend line
            x_num = np.arange(len(monthly))
            try:
                slope, intercept, r, *_ = sp_stats.linregress(x_num, monthly.values)
                trend = slope * x_num + intercept
                direction = '↑' if slope > 0 else '↓'
                ax.plot(monthly.index, trend, color=PALETTE['danger'],
                        lw=1.2, ls=':', alpha=0.7, label=f'Trend {direction}')
            except Exception:
                pass

            ax.set_title(f'{_humanize(val_col)} Over Time')
            _add_subtitle(ax, f'Monthly aggregation  |  '
                              f'{monthly.index.min().strftime("%b %Y")} – '
                              f'{monthly.index.max().strftime("%b %Y")}')
            ax.set_ylabel(_humanize(val_col))
            ax.legend(loc='upper left')
            ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda x, _: _fmt_number(x)))
            plt.xticks(rotation=30, ha='right', fontsize=8)
            plt.tight_layout()
            _watermark(fig)
            return self._save(fig, f'{date_col}_{val_col}', 'line',
                              f'{_humanize(val_col)} Over Time')
        except Exception:
            return None

    # ── Correlation Heatmap ────────────────────────────────────────────────────
    def _correlation_heatmap(self):
        try:
            cols = self.num_cols[:10]
            corr = self.df[cols].corr()
            if corr.isnull().all().all():
                return None

            n    = len(cols)
            size = max(5, min(n + 1, 9))
            fig, ax = plt.subplots(figsize=(size, size * 0.85))

            mask = np.triu(np.ones_like(corr, dtype=bool))
            cmap = sns.diverging_palette(230, 20, as_cmap=True)

            sns.heatmap(corr, ax=ax, mask=mask, cmap=cmap,
                        annot=True, fmt='.2f', annot_kws={'size': 8.5, 'weight': 'bold'},
                        linewidths=0.8, linecolor='white',
                        cbar_kws={'shrink': 0.75, 'label': 'Pearson r'},
                        vmin=-1, vmax=1, center=0, square=True)

            ax.set_title('Correlation Matrix')
            _add_subtitle(ax, 'Lower triangle only  |  Values ≥ 0.7 indicate strong correlation')
            plt.tight_layout()
            _watermark(fig)
            return self._save(fig, 'correlation_heatmap', 'heatmap', 'Correlation Matrix')
        except Exception:
            return None

    # ── Box Plot ───────────────────────────────────────────────────────────────
    def _box_plot(self):
        try:
            cols = self.num_cols[:7]
            # Normalize each column for comparison
            data_norm = self.df[cols].apply(
                lambda c: (c - c.mean()) / c.std() if c.std() > 0 else c)

            fig, ax = plt.subplots(figsize=(max(6, len(cols) * 1.3), 5))

            bp = ax.boxplot(
                [data_norm[c].dropna() for c in cols],
                labels=[_truncate(_humanize(c), 12) for c in cols],
                patch_artist=True,
                notch=False,
                medianprops=dict(color=PALETTE['danger'], linewidth=2.2),
                whiskerprops=dict(color=PALETTE['neutral'], linewidth=1.2),
                capprops=dict(color=PALETTE['neutral'], linewidth=1.2),
                flierprops=dict(marker='o', markersize=3.5,
                                markerfacecolor=PALETTE['accent'],
                                markeredgecolor='none', alpha=0.6)
            )

            for patch, color in zip(bp['boxes'], CAT_COLORS):
                patch.set_facecolor(color)
                patch.set_alpha(0.55)
                patch.set_linewidth(0.8)
                patch.set_edgecolor(PALETTE['text2'])

            ax.axhline(0, color=PALETTE['neutral'], lw=0.8, ls='--', alpha=0.5)
            ax.set_title('Distribution Comparison (Normalized)')
            _add_subtitle(ax, 'Z-score normalized to enable cross-column comparison  |  '
                              'Red line = median')
            ax.set_ylabel('Z-score')
            plt.xticks(rotation=25, ha='right')
            plt.tight_layout()
            _watermark(fig)
            return self._save(fig, 'boxplot_comparison', 'box', 'Distribution Comparison')
        except Exception:
            return None

    # ── Grouped Summary (Category × Numeric) ───────────────────────────────────
    def _grouped_summary(self):
        try:
            cat_col = self.cat_cols[0]
            num_col = self.num_cols[0]

            # Top 8 categories only
            top_cats = self.df[cat_col].value_counts().head(8).index
            df_f     = self.df[self.df[cat_col].isin(top_cats)].copy()

            grp   = df_f.groupby(cat_col)[num_col].agg(['mean','sum','count'])
            grp   = grp.sort_values('sum', ascending=False)

            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.5))

            # Left: mean by category
            colors1 = CAT_COLORS[:len(grp)]
            ax1.bar(grp.index.astype(str), grp['mean'], color=colors1, alpha=0.85)
            ax1.set_title(f'Average {_humanize(num_col)} by {_humanize(cat_col)}')
            _add_subtitle(ax1, 'Mean value per category')
            ax1.set_ylabel(f'Avg {_humanize(num_col)}')
            ax1.yaxis.set_major_formatter(mtick.FuncFormatter(lambda x, _: _fmt_number(x)))
            plt.setp(ax1.get_xticklabels(), rotation=30, ha='right', fontsize=8)

            # Right: share of total (donut-style pie)
            wedges, texts, autotexts = ax2.pie(
                grp['sum'], labels=grp.index.astype(str),
                colors=colors1, autopct='%1.1f%%',
                pctdistance=0.82, startangle=90,
                wedgeprops=dict(width=0.5, edgecolor='white', linewidth=1.5)
            )
            for at in autotexts:
                at.set_fontsize(8)
            ax2.set_title(f'Share of Total {_humanize(num_col)} by {_humanize(cat_col)}')
            _add_subtitle(ax2, 'Proportion of total sum')

            plt.tight_layout()
            _watermark(fig)
            return self._save(fig, f'{cat_col}_{num_col}_summary', 'grouped',
                              f'{_humanize(num_col)} by {_humanize(cat_col)}')
        except Exception:
            return None

    # ── Save ───────────────────────────────────────────────────────────────────
    def _save(self, fig, col: str, chart_type: str, title: str) -> dict:
        safe   = re.sub(r'[^\w]', '_', str(col))[:25]
        fname  = f'{chart_type}_{safe}_{uuid.uuid4().hex[:6]}.png'
        fpath  = os.path.join(self.charts_dir, fname)
        fig.savefig(fpath, dpi=130, bbox_inches='tight',
                    facecolor=PALETTE['bg'])
        plt.close(fig)
        return {
            'type':   chart_type,
            'column': col,
            'url':    f'/static/charts/{fname}',
            'title':  title,
        }


# ── Utilities ──────────────────────────────────────────────────────────────────
import re

def _humanize(col: str) -> str:
    """snake_case → Title Case."""
    return col.replace('_', ' ').title()

def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[:n-1] + '…'

def _fmt_number(v) -> str:
    try:
        v = float(v)
        if abs(v) >= 1_000_000:
            return f'{v/1_000_000:.1f}M'
        if abs(v) >= 1_000:
            return f'{v/1_000:.1f}K'
        if abs(v) < 1 and v != 0:
            return f'{v:.3f}'
        return f'{v:,.1f}'
    except Exception:
        return str(v)
