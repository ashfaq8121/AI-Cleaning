"""
DataCleaner — Intelligent data cleaning pipeline
Steps:
  1. Detect & fill missing values (smart strategy per column type)
  2. Remove duplicate rows
  3. Fix inconsistent text formatting
  4. Fix date formats
  5. Detect & cap outliers (IQR method)
"""

import pandas as pd
import numpy as np
import re
from datetime import datetime


class DataCleaner:
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.report = {
            'missing_handled': {},
            'duplicates_removed': 0,
            'text_fixed': [],
            'dates_fixed': [],
            'outliers_capped': {},
            'steps': []
        }

    def clean(self):
        self._step_missing_values()
        self._step_remove_duplicates()
        self._step_fix_text()
        self._step_fix_dates()
        self._step_outliers()
        return self.df, self.report

    # ── Step 1: Missing Values ─────────────────────────────────────────────────
    def _step_missing_values(self):
        """
        Strategy per column type:
          - Numeric  → fill with MEDIAN  (robust to skew)
          - Category → fill with MODE    (most common value)
          - DateTime → fill with forward-fill, then drop remaining
          - If >50% missing → drop column entirely
        """
        missing_before = self.df.isnull().sum()
        dropped_cols = []
        filled = {}

        for col in self.df.columns:
            null_count = self.df[col].isnull().sum()
            if null_count == 0:
                continue

            pct_missing = null_count / len(self.df)

            # Drop column if >50% missing
            if pct_missing > 0.5:
                self.df.drop(columns=[col], inplace=True)
                dropped_cols.append(col)
                continue

            dtype = self.df[col].dtype

            if pd.api.types.is_numeric_dtype(dtype):
                fill_val = self.df[col].median()
                self.df[col].fillna(fill_val, inplace=True)
                filled[col] = {
                    'strategy': 'median',
                    'fill_value': round(float(fill_val), 4),
                    'count': int(null_count)
                }

            elif pd.api.types.is_datetime64_any_dtype(dtype):
                self.df[col].fillna(method='ffill', inplace=True)
                self.df[col].fillna(method='bfill', inplace=True)
                filled[col] = {'strategy': 'forward-fill', 'count': int(null_count)}

            else:
                # Categorical / object
                mode_vals = self.df[col].mode()
                if len(mode_vals) > 0:
                    self.df[col].fillna(mode_vals[0], inplace=True)
                    filled[col] = {
                        'strategy': 'mode',
                        'fill_value': str(mode_vals[0]),
                        'count': int(null_count)
                    }
                else:
                    self.df[col].fillna('Unknown', inplace=True)
                    filled[col] = {
                        'strategy': 'constant (Unknown)',
                        'count': int(null_count)
                    }

        self.report['missing_handled'] = filled
        if dropped_cols:
            self.report['steps'].append(
                f"Dropped {len(dropped_cols)} column(s) with >50% missing: {', '.join(dropped_cols)}"
            )
        if filled:
            self.report['steps'].append(
                f"Filled missing values in {len(filled)} column(s) using smart strategies"
            )

    # ── Step 2: Remove Duplicates ──────────────────────────────────────────────
    def _step_remove_duplicates(self):
        """Remove completely duplicate rows, keep first occurrence."""
        before = len(self.df)
        self.df.drop_duplicates(inplace=True)
        self.df.reset_index(drop=True, inplace=True)
        removed = before - len(self.df)
        self.report['duplicates_removed'] = removed
        if removed > 0:
            self.report['steps'].append(f"Removed {removed} duplicate row(s)")

    # ── Step 3: Fix Text Formatting ───────────────────────────────────────────
    def _step_fix_text(self):
        """
        For object (text) columns:
          - Strip leading/trailing whitespace
          - Fix inconsistent casing → Title Case (for names/categories)
          - Normalize multiple spaces
        """
        fixed_cols = []
        for col in self.df.select_dtypes(include='object').columns:
            original = self.df[col].copy()

            self.df[col] = self.df[col].astype(str).str.strip()
            self.df[col] = self.df[col].str.replace(r'\s+', ' ', regex=True)

            # Detect if column looks like names/categories (not emails/URLs)
            sample = self.df[col].dropna().head(20).tolist()
            looks_like_category = all(
                len(str(v)) < 50 and not ('@' in str(v)) and not ('http' in str(v))
                for v in sample
            )
            if looks_like_category:
                self.df[col] = self.df[col].str.title()

            # Replace 'nan', 'none', 'null' strings introduced by str conversion
            self.df[col] = self.df[col].replace(
                ['Nan', 'nan', 'None', 'none', 'NULL', 'null', 'Na', 'N/A', 'n/a'],
                np.nan
            )

            if not original.equals(self.df[col]):
                fixed_cols.append(col)

        self.report['text_fixed'] = fixed_cols
        if fixed_cols:
            self.report['steps'].append(
                f"Fixed text formatting in {len(fixed_cols)} column(s): {', '.join(fixed_cols[:5])}"
            )

    # ── Step 4: Fix Date Formats ──────────────────────────────────────────────
    def _step_fix_dates(self):
        """
        Auto-detect columns that look like dates and parse them
        into a uniform YYYY-MM-DD format.
        """
        DATE_PATTERNS = [
            r'\d{4}-\d{2}-\d{2}',
            r'\d{2}/\d{2}/\d{4}',
            r'\d{2}-\d{2}-\d{4}',
            r'\d{1,2} \w+ \d{4}',
        ]
        date_cols = []

        for col in self.df.select_dtypes(include='object').columns:
            sample = self.df[col].dropna().astype(str).head(20).tolist()
            if not sample:
                continue

            matches = sum(
                any(re.search(p, s) for p in DATE_PATTERNS)
                for s in sample
            )
            if matches / max(len(sample), 1) >= 0.6:
                try:
                    parsed = pd.to_datetime(self.df[col], infer_datetime_format=True, errors='coerce')
                    success_rate = parsed.notna().sum() / len(parsed)
                    if success_rate >= 0.5:
                        self.df[col] = parsed
                        date_cols.append(col)
                except Exception:
                    pass

        self.report['dates_fixed'] = date_cols
        if date_cols:
            self.report['steps'].append(
                f"Parsed {len(date_cols)} date column(s): {', '.join(date_cols)}"
            )

    # ── Step 5: Outlier Detection & Capping ───────────────────────────────────
    def _step_outliers(self):
        """
        IQR method (Tukey fences):
          lower = Q1 - 1.5 * IQR
          upper = Q3 + 1.5 * IQR
        Values outside are capped (Winsorization) rather than deleted.
        Only applied to numeric columns with >10 unique values (skip flags/IDs).
        """
        outlier_info = {}

        for col in self.df.select_dtypes(include='number').columns:
            if self.df[col].nunique() <= 10:
                continue  # Skip binary / low-cardinality

            Q1 = self.df[col].quantile(0.25)
            Q3 = self.df[col].quantile(0.75)
            IQR = Q3 - Q1

            if IQR == 0:
                continue

            lower = Q1 - 1.5 * IQR
            upper = Q3 + 1.5 * IQR

            outlier_mask = (self.df[col] < lower) | (self.df[col] > upper)
            count = int(outlier_mask.sum())

            if count > 0:
                self.df[col] = self.df[col].clip(lower=lower, upper=upper)
                outlier_info[col] = {
                    'count': count,
                    'lower_fence': round(float(lower), 4),
                    'upper_fence': round(float(upper), 4)
                }

        self.report['outliers_capped'] = outlier_info
        if outlier_info:
            total = sum(v['count'] for v in outlier_info.values())
            self.report['steps'].append(
                f"Capped {total} outlier(s) across {len(outlier_info)} column(s) using IQR method"
            )
