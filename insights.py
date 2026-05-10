"""
InsightEngine — Generates human-readable AI insights from data analysis.
Produces structured insights covering:
  - Dataset overview
  - Data quality findings
  - Statistical highlights
  - Column-level patterns
  - Recommendations
"""

import pandas as pd
import numpy as np


class InsightEngine:
    def __init__(self, df: pd.DataFrame, cleaning_report: dict):
        self.df = df
        self.report = cleaning_report
        self.numeric_cols = list(df.select_dtypes(include='number').columns)
        self.cat_cols = list(df.select_dtypes(include='object').columns)
        self.date_cols = list(df.select_dtypes(include='datetime').columns)

    def generate_insights(self):
        insights = []
        insights.extend(self._overview_insights())
        insights.extend(self._quality_insights())
        insights.extend(self._statistical_insights())
        insights.extend(self._pattern_insights())
        insights.extend(self._recommendation_insights())
        return insights

    # ── Overview ──────────────────────────────────────────────────────────────
    def _overview_insights(self):
        rows, cols = self.df.shape
        completeness = (1 - self.df.isnull().sum().sum() / (rows * cols)) * 100

        return [{
            'category': 'Dataset Overview',
            'icon': '🗂️',
            'title': f'Dataset contains {rows:,} rows and {cols} columns',
            'detail': (
                f'The dataset has {len(self.numeric_cols)} numeric, '
                f'{len(self.cat_cols)} text, and {len(self.date_cols)} date column(s). '
                f'Overall data completeness is {completeness:.1f}%.'
            ),
            'severity': 'info'
        }]

    # ── Data Quality ──────────────────────────────────────────────────────────
    def _quality_insights(self):
        insights = []
        cleaned = self.report.get('missing_handled', {})
        dups = self.report.get('duplicates_removed', 0)
        outliers = self.report.get('outliers_capped', {})

        if cleaned:
            cols_list = ', '.join(list(cleaned.keys())[:4])
            total_filled = sum(v.get('count', 0) for v in cleaned.values())
            insights.append({
                'category': 'Data Quality',
                'icon': '🔧',
                'title': f'{total_filled:,} missing value(s) filled across {len(cleaned)} column(s)',
                'detail': (
                    f'Columns affected: {cols_list}. '
                    'Numeric columns were filled with the median, '
                    'while categorical columns used the most frequent value (mode).'
                ),
                'severity': 'warning'
            })
        else:
            insights.append({
                'category': 'Data Quality',
                'icon': '✅',
                'title': 'No missing values detected',
                'detail': 'Your dataset is complete — no imputation was required.',
                'severity': 'success'
            })

        if dups > 0:
            insights.append({
                'category': 'Data Quality',
                'icon': '🗑️',
                'title': f'{dups:,} duplicate row(s) removed',
                'detail': (
                    f'{dups} exact duplicate records were found and removed '
                    'to prevent statistical bias in the analysis.'
                ),
                'severity': 'warning'
            })

        if outliers:
            total_outliers = sum(v['count'] for v in outliers.values())
            cols_list = ', '.join(list(outliers.keys())[:3])
            insights.append({
                'category': 'Data Quality',
                'icon': '📊',
                'title': f'{total_outliers:,} outlier(s) detected and capped in {len(outliers)} column(s)',
                'detail': (
                    f'Columns: {cols_list}. Outliers were capped using the IQR method '
                    '(Tukey fences: Q1 − 1.5×IQR to Q3 + 1.5×IQR) '
                    'to preserve data without distorting statistics.'
                ),
                'severity': 'warning'
            })

        return insights

    # ── Statistical Insights ──────────────────────────────────────────────────
    def _statistical_insights(self):
        insights = []
        if not self.numeric_cols:
            return insights

        for col in self.numeric_cols[:5]:
            series = self.df[col].dropna()
            if len(series) < 3:
                continue

            mean = series.mean()
            median = series.median()
            std = series.std()
            skew = series.skew()
            cv = (std / mean * 100) if mean != 0 else 0

            # Skewness insight
            if abs(skew) > 1:
                direction = 'right (positive)' if skew > 0 else 'left (negative)'
                insights.append({
                    'category': 'Statistics',
                    'icon': '📈',
                    'title': f'"{col}" has a {direction} skewed distribution',
                    'detail': (
                        f'Skewness = {skew:.2f}. Mean ({mean:.2f}) ≠ Median ({median:.2f}), '
                        f'indicating the data is not normally distributed. '
                        f'Consider log-transformation if using this in ML models.'
                    ),
                    'severity': 'info'
                })

            # High variability
            if cv > 50:
                insights.append({
                    'category': 'Statistics',
                    'icon': '⚡',
                    'title': f'"{col}" shows high variability (CV = {cv:.1f}%)',
                    'detail': (
                        f'Coefficient of Variation = {cv:.1f}%. '
                        f'Range: {series.min():.2f} to {series.max():.2f}, '
                        f'Std Dev: {std:.2f}. This column has significant spread.'
                    ),
                    'severity': 'info'
                })

        # Correlation insight
        if len(self.numeric_cols) >= 2:
            corr_matrix = self.df[self.numeric_cols].corr()
            high_corr = []
            for i in range(len(corr_matrix.columns)):
                for j in range(i + 1, len(corr_matrix.columns)):
                    val = corr_matrix.iloc[i, j]
                    if abs(val) >= 0.7:
                        high_corr.append((
                            corr_matrix.columns[i],
                            corr_matrix.columns[j],
                            val
                        ))

            if high_corr:
                pairs = '; '.join(
                    f'"{a}" & "{b}" ({v:.2f})'
                    for a, b, v in high_corr[:3]
                )
                insights.append({
                    'category': 'Statistics',
                    'icon': '🔗',
                    'title': f'{len(high_corr)} strongly correlated column pair(s) found',
                    'detail': (
                        f'Pairs: {pairs}. '
                        'Strong correlations (|r| ≥ 0.7) can indicate multicollinearity — '
                        'consider removing one column from each pair for ML models.'
                    ),
                    'severity': 'info'
                })

        return insights

    # ── Pattern Insights ──────────────────────────────────────────────────────
    def _pattern_insights(self):
        insights = []

        # Categorical cardinality
        for col in self.cat_cols[:4]:
            n_unique = self.df[col].nunique()
            n_rows = len(self.df)
            if n_unique == n_rows:
                insights.append({
                    'category': 'Patterns',
                    'icon': '🔑',
                    'title': f'"{col}" appears to be a unique identifier',
                    'detail': (
                        f'Every value in "{col}" is unique ({n_unique} distinct values in {n_rows} rows). '
                        'This column is likely an ID/key and may not be useful for analysis.'
                    ),
                    'severity': 'info'
                })
            elif n_unique <= 5:
                top = self.df[col].value_counts().head(3)
                top_str = ', '.join([f'"{k}" ({v})' for k, v in top.items()])
                insights.append({
                    'category': 'Patterns',
                    'icon': '🏷️',
                    'title': f'"{col}" is a low-cardinality category ({n_unique} values)',
                    'detail': f'Top values: {top_str}. Good candidate for one-hot encoding in ML.',
                    'severity': 'success'
                })

        # Date range insight
        for col in self.date_cols[:2]:
            try:
                date_range = self.df[col].max() - self.df[col].min()
                insights.append({
                    'category': 'Patterns',
                    'icon': '📅',
                    'title': f'"{col}" spans {date_range.days} days of data',
                    'detail': (
                        f'Date range: {self.df[col].min().strftime("%b %d, %Y")} '
                        f'to {self.df[col].max().strftime("%b %d, %Y")}. '
                        'Time-series analysis and trend forecasting are possible.'
                    ),
                    'severity': 'info'
                })
            except Exception:
                pass

        return insights

    # ── Recommendations ───────────────────────────────────────────────────────
    def _recommendation_insights(self):
        recs = []

        if len(self.numeric_cols) >= 2:
            recs.append({
                'category': 'Recommendation',
                'icon': '💡',
                'title': 'This dataset is ready for regression modeling',
                'detail': (
                    f'With {len(self.numeric_cols)} numeric columns, you can build '
                    'predictive regression models. Consider using scikit-learn\'s '
                    'Linear Regression or Random Forest Regressor.'
                ),
                'severity': 'success'
            })

        if self.cat_cols and self.numeric_cols:
            recs.append({
                'category': 'Recommendation',
                'icon': '💡',
                'title': 'Suitable for classification and segmentation analysis',
                'detail': (
                    f'Mixed numeric and categorical columns make this dataset ideal for '
                    'classification models. Apply one-hot encoding on categorical columns '
                    'before training.'
                ),
                'severity': 'success'
            })

        if len(self.df) > 10000:
            recs.append({
                'category': 'Recommendation',
                'icon': '🚀',
                'title': 'Large dataset — consider sampling for EDA',
                'detail': (
                    f'With {len(self.df):,} rows, visualizations and EDA can be slow. '
                    'Use stratified sampling (e.g., 10%) for quick exploration, '
                    'then train on the full dataset.'
                ),
                'severity': 'info'
            })

        return recs
