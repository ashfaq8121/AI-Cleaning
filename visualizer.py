"""
DataVisualizer — Auto-detects column types and generates appropriate charts:
  - Numeric      → Histogram + KDE overlay
  - Categorical   → Horizontal Bar Chart (top 10 categories)
  - DateTime      → Line Chart (trend over time)
  - Correlation   → Heatmap (if 2+ numeric columns)
  - Distribution  → Box Plot (numeric outlier view)
"""

import os
import uuid
import warnings
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns

warnings.filterwarnings('ignore')

# ── Design System ──────────────────────────────────────────────────────────────
PALETTE = {
    'primary':   '#6C63FF',
    'secondary': '#2DD4BF',
    'accent':    '#F59E0B',
    'danger':    '#EF4444',
    'bg':        '#0F0F1A',
    'surface':   '#1A1A2E',
    'card':      '#16213E',
    'text':      '#E2E8F0',
    'muted':     '#94A3B8',
    'grid':      '#1E293B',
}

BAR_COLORS = [
    '#6C63FF','#2DD4BF','#F59E0B','#EF4444','#8B5CF6',
    '#06B6D4','#10B981','#F97316','#EC4899','#14B8A6'
]

def _setup_style():
    plt.rcParams.update({
        'figure.facecolor':  PALETTE['surface'],
        'axes.facecolor':    PALETTE['card'],
        'axes.edgecolor':    PALETTE['grid'],
        'axes.labelcolor':   PALETTE['text'],
        'text.color':        PALETTE['text'],
        'xtick.color':       PALETTE['muted'],
        'ytick.color':       PALETTE['muted'],
        'grid.color':        PALETTE['grid'],
        'grid.linewidth':    0.5,
        'axes.grid':         True,
        'grid.alpha':        0.4,
        'font.family':       'DejaVu Sans',
        'font.size':         10,
        'axes.titlesize':    13,
        'axes.titleweight':  'bold',
        'axes.titlecolor':   PALETTE['text'],
        'axes.spines.top':   False,
        'axes.spines.right': False,
        'axes.spines.left':  False,
        'axes.spines.bottom':False,
    })


class DataVisualizer:
    def __init__(self, df: pd.DataFrame, charts_dir: str):
        self.df = df
        self.charts_dir = charts_dir
        os.makedirs(charts_dir, exist_ok=True)
        _setup_style()

    def generate_all_charts(self):
        charts = []
        numeric_cols = list(self.df.select_dtypes(include='number').columns)
        cat_cols = list(self.df.select_dtypes(include='object').columns)
        date_cols = list(self.df.select_dtypes(include='datetime').columns)

        # Histograms for numeric (max 6)
        for col in numeric_cols[:6]:
            info = self._histogram(col)
            if info:
                charts.append(info)

        # Bar charts for categorical (max 4)
        for col in cat_cols[:4]:
            info = self._bar_chart(col)
            if info:
                charts.append(info)

        # Line charts for datetime (max 2)
        for col in date_cols[:2]:
            # Pair with first numeric col
            if numeric_cols:
                info = self._line_chart(col, numeric_cols[0])
                if info:
                    charts.append(info)

        # Correlation heatmap (if 2+ numeric)
        if len(numeric_cols) >= 2:
            info = self._correlation_heatmap(numeric_cols[:10])
            if info:
                charts.append(info)

        # Box plot (if 2+ numeric)
        if len(numeric_cols) >= 2:
            info = self._box_plot(numeric_cols[:8])
            if info:
                charts.append(info)

        return charts

    # ── Histogram ──────────────────────────────────────────────────────────────
    def _histogram(self, col):
        try:
            data = self.df[col].dropna()
            if len(data) < 3:
                return None

            fig, ax = plt.subplots(figsize=(7, 4))
            fig.patch.set_facecolor(PALETTE['surface'])

            n, bins, patches = ax.hist(data, bins='auto', color=PALETTE['primary'],
                                       alpha=0.75, edgecolor='none')

            # KDE overlay
            try:
                from scipy.stats import gaussian_kde
                kde_x = np.linspace(data.min(), data.max(), 200)
                kde = gaussian_kde(data)
                kde_y = kde(kde_x) * len(data) * (bins[1] - bins[0])
                ax.plot(kde_x, kde_y, color=PALETTE['secondary'], lw=2, alpha=0.9)
            except Exception:
                pass

            # Mean & median lines
            ax.axvline(data.mean(), color=PALETTE['accent'], lw=1.5,
                       linestyle='--', alpha=0.8, label=f'Mean: {data.mean():.2f}')
            ax.axvline(data.median(), color=PALETTE['danger'], lw=1.5,
                       linestyle='--', alpha=0.8, label=f'Median: {data.median():.2f}')

            ax.set_title(f'Distribution of {col}')
            ax.set_xlabel(col)
            ax.set_ylabel('Frequency')
            ax.legend(fontsize=8, framealpha=0.3)
            plt.tight_layout()

            return self._save(fig, col, 'histogram')
        except Exception:
            return None

    # ── Bar Chart ──────────────────────────────────────────────────────────────
    def _bar_chart(self, col):
        try:
            data = self.df[col].dropna()
            vc = data.value_counts().head(10)
            if len(vc) < 2:
                return None

            fig, ax = plt.subplots(figsize=(7, 4))
            fig.patch.set_facecolor(PALETTE['surface'])

            bars = ax.barh(vc.index.astype(str), vc.values,
                           color=BAR_COLORS[:len(vc)], alpha=0.85, height=0.65)

            # Value labels
            for bar, val in zip(bars, vc.values):
                ax.text(bar.get_width() + max(vc.values) * 0.01, bar.get_y() + bar.get_height() / 2,
                        f'{val:,}', va='center', fontsize=8, color=PALETTE['muted'])

            ax.set_title(f'Top Categories — {col}')
            ax.set_xlabel('Count')
            ax.invert_yaxis()
            plt.tight_layout()

            return self._save(fig, col, 'bar')
        except Exception:
            return None

    # ── Line Chart ─────────────────────────────────────────────────────────────
    def _line_chart(self, date_col, value_col):
        try:
            df_t = self.df[[date_col, value_col]].dropna()
            df_t = df_t.sort_values(date_col)
            df_t = df_t.set_index(date_col)[value_col].resample('M').mean()

            if len(df_t) < 2:
                return None

            fig, ax = plt.subplots(figsize=(8, 4))
            fig.patch.set_facecolor(PALETTE['surface'])

            ax.plot(df_t.index, df_t.values, color=PALETTE['primary'],
                    lw=2, alpha=0.9)
            ax.fill_between(df_t.index, df_t.values, alpha=0.15, color=PALETTE['primary'])

            # Trend line
            x_num = np.arange(len(df_t))
            z = np.polyfit(x_num, df_t.values, 1)
            p = np.poly1d(z)
            ax.plot(df_t.index, p(x_num), color=PALETTE['secondary'],
                    lw=1.5, linestyle='--', alpha=0.7, label='Trend')

            ax.set_title(f'{value_col} Over Time')
            ax.set_xlabel(date_col)
            ax.set_ylabel(value_col)
            ax.legend(fontsize=8, framealpha=0.3)
            plt.xticks(rotation=30, ha='right')
            plt.tight_layout()

            return self._save(fig, f'{date_col}_{value_col}', 'line')
        except Exception:
            return None

    # ── Correlation Heatmap ────────────────────────────────────────────────────
    def _correlation_heatmap(self, cols):
        try:
            corr = self.df[cols].corr()
            if corr.isnull().all().all():
                return None

            n = len(cols)
            size = max(5, min(n, 8))
            fig, ax = plt.subplots(figsize=(size, size * 0.8))
            fig.patch.set_facecolor(PALETTE['surface'])

            cmap = sns.diverging_palette(260, 10, as_cmap=True)
            mask = np.triu(np.ones_like(corr, dtype=bool))
            sns.heatmap(corr, ax=ax, mask=mask, cmap=cmap,
                        annot=True, fmt='.2f', annot_kws={'size': 8},
                        linewidths=0.5, linecolor=PALETTE['grid'],
                        cbar_kws={'shrink': 0.8},
                        vmin=-1, vmax=1, center=0)

            ax.set_title('Correlation Matrix')
            plt.tight_layout()

            return self._save(fig, 'correlation', 'heatmap')
        except Exception:
            return None

    # ── Box Plot ───────────────────────────────────────────────────────────────
    def _box_plot(self, cols):
        try:
            data = self.df[cols].dropna()
            if data.empty:
                return None

            fig, ax = plt.subplots(figsize=(max(6, len(cols) * 1.2), 5))
            fig.patch.set_facecolor(PALETTE['surface'])

            bp = ax.boxplot(
                [data[col].dropna() for col in cols],
                labels=cols,
                patch_artist=True,
                medianprops=dict(color=PALETTE['accent'], linewidth=2),
                whiskerprops=dict(color=PALETTE['muted']),
                capprops=dict(color=PALETTE['muted']),
                flierprops=dict(marker='o', markersize=3,
                                markerfacecolor=PALETTE['danger'], alpha=0.5)
            )
            for patch, color in zip(bp['boxes'], BAR_COLORS[:len(cols)]):
                patch.set_facecolor(color)
                patch.set_alpha(0.6)

            ax.set_title('Distribution Overview (Box Plot)')
            plt.xticks(rotation=30, ha='right')
            plt.tight_layout()

            return self._save(fig, 'boxplot', 'box')
        except Exception:
            return None

    # ── Save ───────────────────────────────────────────────────────────────────
    def _save(self, fig, col, chart_type):
        filename = f"{chart_type}_{col[:20]}_{uuid.uuid4().hex[:6]}.png"
        path = os.path.join(self.charts_dir, filename)
        fig.savefig(path, dpi=120, bbox_inches='tight',
                    facecolor=PALETTE['surface'])
        plt.close(fig)
        return {
            'type': chart_type,
            'column': col,
            'url': f'/static/charts/{filename}',
            'title': self._title(chart_type, col)
        }

    def _title(self, chart_type, col):
        titles = {
            'histogram': f'Distribution of {col}',
            'bar': f'Category Breakdown — {col}',
            'line': f'Time Series — {col}',
            'heatmap': 'Correlation Matrix',
            'box': 'Distribution Overview',
        }
        return titles.get(chart_type, col)
