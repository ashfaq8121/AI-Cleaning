"""
core/insights.py — Analyst-Style Insight Engine v2.0
=====================================================
Generates structured, business-analyst-toned observations.
Reads like a human-reviewed data memo, not generic AI output.
"""

import numpy as np
import pandas as pd
from scipy import stats as sp_stats


def _humanize(col: str) -> str:
    return col.replace('_', ' ').title()

def _fmt(v, decimals=2) -> str:
    try:
        v = float(v)
        if abs(v) >= 1_000_000: return f'{v/1_000_000:.1f}M'
        if abs(v) >= 1_000:     return f'{v/1_000:.1f}K'
        return f'{v:,.{decimals}f}'
    except Exception:
        return str(v)


class InsightEngine:
    def __init__(self, df: pd.DataFrame, cleaning_report: dict):
        self.df      = df
        self.report  = cleaning_report
        self.num_cols  = list(df.select_dtypes(include='number').columns)
        self.cat_cols  = list(df.select_dtypes(include='object').columns)
        self.date_cols = list(df.select_dtypes(include='datetime').columns)

    def generate_insights(self) -> list:
        insights = []
        insights += self._overview()
        insights += self._quality_summary()
        insights += self._statistical_highlights()
        insights += self._distribution_insights()
        insights += self._correlation_insights()
        insights += self._categorical_insights()
        insights += self._time_insights()
        insights += self._recommendations()
        return insights

    # ── Overview ──────────────────────────────────────────────────────────────
    def _overview(self):
        rows, cols    = self.df.shape
        n_cells       = rows * cols
        null_total    = int(self.df.isnull().sum().sum())
        completeness  = (1 - null_total / max(n_cells, 1)) * 100
        q_before      = self.report.get('quality_before', 0)
        q_after       = self.report.get('quality_after', 0)

        return [{
            'category': 'Executive Overview',
            'icon':     '🗂️',
            'title':    f'Dataset contains {rows:,} records across {cols} fields',
            'detail':   (
                f'The dataset spans {len(self.num_cols)} numeric, '
                f'{len(self.cat_cols)} categorical, and {len(self.date_cols)} date field(s). '
                f'Post-cleaning completeness is {completeness:.1f}%. '
                f'Data quality score improved from {q_before} → {q_after} / 100.'
            ),
            'severity': 'info'
        }]

    # ── Quality Summary ───────────────────────────────────────────────────────
    def _quality_summary(self):
        insights = []
        cr   = self.report
        missing  = cr.get('missing_handled', {})
        dups     = cr.get('duplicates_removed', 0)
        biz_dups = cr.get('business_key_dups', 0)
        outliers = cr.get('outliers_capped', {})
        currency = cr.get('currency_cols', [])
        pct_cols = cr.get('pct_cols', [])
        derived  = cr.get('date_features', [])
        dropped  = cr.get('dropped_cols', [])

        q_before = cr.get('quality_before', 0)
        q_after  = cr.get('quality_after', 0)
        delta    = q_after - q_before

        if delta > 0:
            insights.append({
                'category': 'Data Quality',
                'icon':     '📈',
                'title':    f'Quality score improved by {delta:.1f} points ({q_before} → {q_after}/100)',
                'detail':   (
                    'The cleaning pipeline significantly improved dataset reliability. '
                    f'Key contributors: missing value imputation, duplicate removal, '
                    'and outlier capping.'
                ),
                'severity': 'success'
            })

        if missing:
            total_filled = sum(v.get('count', 0) for v in missing.values())
            strategies   = list({v['strategy'] for v in missing.values()})
            cols_sample  = list(missing.keys())[:3]
            insights.append({
                'category': 'Data Quality',
                'icon':     '🔧',
                'title':    f'{total_filled:,} missing values filled across {len(missing)} field(s)',
                'detail':   (
                    f'Imputation strategies applied: {", ".join(strategies)}. '
                    f'Fields treated: {", ".join(cols_sample)}'
                    + (f' and {len(missing)-3} more.' if len(missing) > 3 else '.')
                    + ' Median was preferred over mean for skewed distributions.'
                ),
                'severity': 'warning'
            })

        if dups + biz_dups > 0:
            insights.append({
                'category': 'Data Quality',
                'icon':     '🗑️',
                'title':    f'{dups + biz_dups:,} duplicate record(s) removed',
                'detail':   (
                    f'{dups} exact duplicates and {biz_dups} business-key duplicates were '
                    'detected and removed to prevent double-counting in aggregations.'
                ),
                'severity': 'warning' if dups + biz_dups < 10 else 'error'
            })

        if outliers:
            total_out = sum(v['iqr_count'] for v in outliers.values())
            worst_col = max(outliers, key=lambda c: outliers[c]['iqr_count'])
            insights.append({
                'category': 'Data Quality',
                'icon':     '📊',
                'title':    f'{total_out:,} outlier(s) detected and capped in {len(outliers)} field(s)',
                'detail':   (
                    f'"{_humanize(worst_col)}" had the most outliers '
                    f'({outliers[worst_col]["iqr_count"]}, '
                    f'{outliers[worst_col]["pct_affected"]:.1f}% of rows). '
                    'Values were capped using IQR Tukey fences rather than deleted, '
                    'preserving sample size while limiting distortion.'
                ),
                'severity': 'warning'
            })

        if currency:
            insights.append({
                'category': 'Data Quality',
                'icon':     '💰',
                'title':    f'{len(currency)} currency field(s) standardized',
                'detail':   (
                    f'Currency symbols and formatting stripped from: '
                    f'{", ".join(currency[:3])}. '
                    'Values are now clean floats ready for aggregation.'
                ),
                'severity': 'info'
            })

        if derived:
            insights.append({
                'category': 'Data Quality',
                'icon':     '📅',
                'title':    f'{len(derived)} date-derived feature(s) created',
                'detail':   (
                    f'Temporal features added: {", ".join(derived[:5])}. '
                    'These enable year-over-year, quarterly, and monthly analyses.'
                ),
                'severity': 'success'
            })

        if not missing and not dups and not outliers:
            insights.append({
                'category': 'Data Quality',
                'icon':     '✅',
                'title':    'Dataset arrived in excellent condition',
                'detail':   (
                    'No significant quality issues were detected. '
                    'Minimal cleaning was required — the data appears well-maintained.'
                ),
                'severity': 'success'
            })

        return insights

    # ── Statistical Highlights ────────────────────────────────────────────────
    def _statistical_highlights(self):
        insights = []
        if not self.num_cols:
            return insights

        for col in self.num_cols[:5]:
            s = self.df[col].dropna()
            if len(s) < 5:
                continue

            mean, median = s.mean(), s.median()
            std, cv      = s.std(), (s.std() / s.mean() * 100) if s.mean() != 0 else 0
            skew         = s.skew()

            if abs(skew) > 1.5:
                direction = 'right-skewed (long right tail)' if skew > 0 else 'left-skewed (long left tail)'
                impact    = ('high values are pulling the mean above the median'
                             if skew > 0 else
                             'low values are pulling the mean below the median')
                insights.append({
                    'category': 'Statistical Highlights',
                    'icon':     '📉',
                    'title':    f'"{_humanize(col)}" is {direction}',
                    'detail':   (
                        f'Skewness = {skew:.2f}. Mean ({_fmt(mean)}) differs from '
                        f'median ({_fmt(median)}), meaning {impact}. '
                        'For modeling: consider log transformation.'
                    ),
                    'severity': 'info'
                })

            if cv > 60:
                insights.append({
                    'category': 'Statistical Highlights',
                    'icon':     '⚡',
                    'title':    f'"{_humanize(col)}" shows high variability (CV = {cv:.0f}%)',
                    'detail':   (
                        f'Range: {_fmt(s.min())} to {_fmt(s.max())}. '
                        f'Coefficient of Variation = {cv:.0f}% indicates this field '
                        'is highly dispersed — segment analysis may reveal subgroup patterns.'
                    ),
                    'severity': 'info'
                })

        return insights

    # ── Distribution Insights ─────────────────────────────────────────────────
    def _distribution_insights(self):
        insights = []
        for col in self.num_cols[:3]:
            s = self.df[col].dropna()
            if len(s) < 10:
                continue
            try:
                _, p = sp_stats.shapiro(s.sample(min(50, len(s)), random_state=42))
                normality = 'approximately normally distributed' if p > 0.05 else 'not normally distributed'
                insights.append({
                    'category': 'Distribution Analysis',
                    'icon':     '🔔',
                    'title':    f'"{_humanize(col)}" is {normality} (Shapiro p={p:.3f})',
                    'detail':   (
                        f'p-value = {p:.4f}. '
                        + ('This supports using mean-based statistics.'
                           if p > 0.05 else
                           'Median-based statistics and non-parametric tests are more appropriate.')
                    ),
                    'severity': 'info'
                })
            except Exception:
                pass
        return insights

    # ── Correlation Insights ──────────────────────────────────────────────────
    def _correlation_insights(self):
        insights = []
        if len(self.num_cols) < 2:
            return insights

        corr = self.df[self.num_cols].corr()
        strong, moderate = [], []

        for i in range(len(corr.columns)):
            for j in range(i + 1, len(corr.columns)):
                r   = corr.iloc[i, j]
                a,b = corr.columns[i], corr.columns[j]
                if abs(r) >= 0.70:
                    strong.append((a, b, r))
                elif abs(r) >= 0.40:
                    moderate.append((a, b, r))

        if strong:
            pair = strong[0]
            direction = 'positively' if pair[2] > 0 else 'negatively'
            insights.append({
                'category': 'Correlation Analysis',
                'icon':     '🔗',
                'title':    f'Strong correlation: "{_humanize(pair[0])}" & "{_humanize(pair[1])}" (r={pair[2]:.2f})',
                'detail':   (
                    f'These fields are {direction} correlated (|r| = {abs(pair[2]):.2f}). '
                    + (f'{len(strong)-1} additional strong pair(s) found. ' if len(strong) > 1 else '')
                    + 'In ML models, consider removing one to reduce multicollinearity.'
                ),
                'severity': 'warning' if abs(pair[2]) > 0.9 else 'info'
            })

        if moderate:
            pairs_str = '; '.join(
                f'"{_humanize(a)}" & "{_humanize(b)}" (r={r:.2f})'
                for a, b, r in moderate[:3]
            )
            insights.append({
                'category': 'Correlation Analysis',
                'icon':     '🔗',
                'title':    f'{len(moderate)} moderate correlation(s) identified',
                'detail':   f'Pairs: {pairs_str}. These relationships may be analytically useful.',
                'severity': 'info'
            })

        if not strong and not moderate:
            insights.append({
                'category': 'Correlation Analysis',
                'icon':     '📊',
                'title':    'No strong correlations detected among numeric fields',
                'detail':   (
                    'Numeric fields appear largely independent of one another. '
                    'This is favorable for feature independence in predictive models.'
                ),
                'severity': 'success'
            })

        return insights

    # ── Categorical Insights ──────────────────────────────────────────────────
    def _categorical_insights(self):
        insights = []
        for col in self.cat_cols[:4]:
            vc     = self.df[col].value_counts()
            n_uniq = self.df[col].nunique()
            n_rows = len(self.df)

            if n_uniq == n_rows:
                insights.append({
                    'category': 'Field Analysis',
                    'icon':     '🔑',
                    'title':    f'"{_humanize(col)}" appears to be a unique identifier',
                    'detail':   (
                        'Every value is distinct — this column functions as a primary key. '
                        'Exclude from groupby, aggregations, and model training.'
                    ),
                    'severity': 'info'
                })

            elif n_uniq <= 2:
                dominant = vc.index[0]
                dom_pct  = vc.iloc[0] / n_rows * 100
                insights.append({
                    'category': 'Field Analysis',
                    'icon':     '⚠️',
                    'title':    f'"{_humanize(col)}" is dominated by "{dominant}" ({dom_pct:.0f}%)',
                    'detail':   (
                        f'With {dom_pct:.0f}% of records sharing the top value, '
                        'this field has very low variance. It may have limited predictive value.'
                    ),
                    'severity': 'warning' if dom_pct > 80 else 'info'
                })

            elif vc.iloc[0] / n_rows > 0.5:
                insights.append({
                    'category': 'Field Analysis',
                    'icon':     '🏷️',
                    'title':    f'"{_humanize(col)}" has a dominant category: "{vc.index[0]}" ({vc.iloc[0]/n_rows*100:.0f}%)',
                    'detail':   (
                        f'Top 3 values: '
                        + ', '.join(f'"{v}" ({c:,})' for v, c in vc.head(3).items())
                        + '. Consider whether this imbalance affects your analysis.'
                    ),
                    'severity': 'info'
                })

        return insights

    # ── Time Insights ─────────────────────────────────────────────────────────
    def _time_insights(self):
        insights = []
        for col in self.date_cols[:2]:
            try:
                s = self.df[col].dropna()
                span = (s.max() - s.min()).days
                insights.append({
                    'category': 'Time Analysis',
                    'icon':     '📅',
                    'title':    f'"{_humanize(col)}" spans {span:,} days of data',
                    'detail':   (
                        f'Date range: {s.min().strftime("%d %b %Y")} to '
                        f'{s.max().strftime("%d %b %Y")}. '
                        'Time-series analysis, trend forecasting, and seasonal '
                        'decomposition are applicable.'
                    ),
                    'severity': 'info'
                })
            except Exception:
                pass
        return insights

    # ── Recommendations ───────────────────────────────────────────────────────
    def _recommendations(self):
        recs = []
        has_num  = len(self.num_cols) >= 2
        has_cat  = bool(self.cat_cols)
        has_date = bool(self.date_cols)
        n_rows   = len(self.df)

        if has_num and has_cat:
            recs.append({
                'category': 'Recommendation',
                'icon':     '💡',
                'title':    'Dataset is ready for classification or regression modeling',
                'detail':   (
                    f'With {len(self.num_cols)} numeric and {len(self.cat_cols)} categorical '
                    'fields, this dataset supports supervised ML. '
                    'Suggested next steps: encode categoricals, scale numerics, '
                    'split train/test, and evaluate with cross-validation.'
                ),
                'severity': 'success'
            })

        if has_date:
            recs.append({
                'category': 'Recommendation',
                'icon':     '📈',
                'title':    'Time-series modeling and trend analysis are viable',
                'detail':   (
                    'Date fields are present and parsed. Consider ARIMA, Prophet, '
                    'or simple moving averages for forecasting. '
                    'Derived date features (year, month, quarter) have been added to support this.'
                ),
                'severity': 'success'
            })

        if n_rows > 50_000:
            recs.append({
                'category': 'Recommendation',
                'icon':     '🚀',
                'title':    f'Large dataset ({n_rows:,} rows) — consider stratified sampling for EDA',
                'detail':   (
                    'For exploration and visualization, a 10–20% stratified sample '
                    'will be significantly faster. Train final models on the full dataset.'
                ),
                'severity': 'info'
            })

        if not recs:
            recs.append({
                'category': 'Recommendation',
                'icon':     '💡',
                'title':    'Load the cleaned CSV into Power BI or Excel for visual exploration',
                'detail':   (
                    'The cleaned dataset is analysis-ready. '
                    'For deeper exploration, connect to Power BI Desktop or '
                    'use pandas + matplotlib in a Jupyter Notebook.'
                ),
                'severity': 'info'
            })

        return recs
