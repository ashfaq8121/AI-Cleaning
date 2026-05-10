"""
core/cleaner.py — Advanced Data Cleaning Engine v2.0
=====================================================
Implements a production-grade, multi-pass cleaning pipeline:

Pass 1 : Schema normalization (column names, types, detection)
Pass 2 : Value-level cleaning (currency, %, phone, email, text)
Pass 3 : Missing value imputation (smart, group-wise where possible)
Pass 4 : Duplicate resolution (exact + business-key)
Pass 5 : Date enrichment (derived features)
Pass 6 : Outlier capping (IQR + z-score, skip ID-like cols)
Pass 7 : Quality scoring + detailed audit log
"""

import re
import logging
import unicodedata
from datetime import datetime

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
CURRENCY_SYMBOLS = r'[\$€£¥₹₩₪₺,]'
FAKE_NULLS       = {'', 'nan', 'none', 'null', 'na', 'n/a', 'n.a.', '-', '--',
                    'nil', 'undefined', 'unknown', '#n/a', 'missing', 'not available'}
MAX_CATEGORIES   = 50   # above this → treat as free-text / identifier
ID_PATTERNS      = re.compile(
    r'(?i)(^id$|_id$|^id_|uuid|guid|key|code|sku|ref|serial|phone|mobile|email|url|link)')
DATE_FORMATS = [
    '%Y-%m-%d','%d-%m-%Y','%m-%d-%Y','%d/%m/%Y','%m/%d/%Y',
    '%Y/%m/%d','%d %b %Y','%d %B %Y','%b %d, %Y','%B %d, %Y',
    '%Y%m%d','%d-%b-%Y','%d-%B-%Y',
]


# ═══════════════════════════════════════════════════════════════════════════════
class DataCleaner:
    """
    Usage:
        cleaner = DataCleaner(df)
        df_clean, report = cleaner.clean()
    """

    def __init__(self, df: pd.DataFrame):
        self.original   = df.copy()
        self.df         = df.copy()
        self.log: list  = []           # human-readable audit log
        self.report: dict = self._empty_report()

    # ── Public ─────────────────────────────────────────────────────────────────
    def clean(self):
        self._snapshot('before')

        self._pass1_schema()
        self._pass2_value_cleaning()
        self._pass3_missing_values()
        self._pass4_duplicates()
        self._pass5_date_enrichment()
        self._pass6_outliers()

        self._snapshot('after')
        self._pass7_quality_score()

        self.report['log'] = self.log
        return self.df, self.report

    # ── Report skeleton ────────────────────────────────────────────────────────
    def _empty_report(self):
        return {
            'schema':           {},
            'column_renames':   {},
            'type_coercions':   {},
            'currency_cols':    [],
            'pct_cols':         [],
            'protected_cols':   [],
            'missing_handled':  {},
            'duplicates_removed': 0,
            'business_key_dups':  0,
            'text_fixed':       [],
            'dates_parsed':     [],
            'date_features':    [],
            'outliers_capped':  {},
            'dropped_cols':     [],
            'steps':            [],
            'quality_before':   0,
            'quality_after':    0,
            'null_before':      {},
            'null_after':       {},
            'dup_before':       0,
            'dup_after':        0,
            'log':              [],
        }

    # ── Snapshot ───────────────────────────────────────────────────────────────
    def _snapshot(self, when: str):
        null_map = self.df.isnull().sum().to_dict()
        dups     = int(self.df.duplicated().sum())
        self.report[f'null_{when}']  = {k: int(v) for k, v in null_map.items()}
        self.report[f'dup_{when}']   = dups

    # ══════════════════════════════════════════════════════════════════════════
    # PASS 1 — Schema normalization
    # ══════════════════════════════════════════════════════════════════════════
    def _pass1_schema(self):
        self._log_section('PASS 1 — Schema Normalization')

        # 1a. Standardize column names
        renames = {}
        for col in self.df.columns:
            clean = self._normalize_col_name(col)
            if clean != col:
                renames[col] = clean

        if renames:
            self.df.rename(columns=renames, inplace=True)
            self.report['column_renames'] = renames
            self._log(f"Renamed {len(renames)} column(s): "
                      + ', '.join(f'"{k}" → "{v}"' for k, v in list(renames.items())[:5]))
            self._step(f'Standardized {len(renames)} column name(s) to snake_case')

        # 1b. Classify each column
        schema = {}
        for col in self.df.columns:
            schema[col] = self._classify_column(col, self.df[col])
        self.report['schema'] = schema
        self._log(f"Schema classified: "
                  + str({k: v['role'] for k, v in schema.items()}))

    def _normalize_col_name(self, name: str) -> str:
        name = str(name).strip()
        name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode()
        name = re.sub(r'[^\w\s]', '_', name)
        name = re.sub(r'\s+', '_', name)
        name = re.sub(r'_+', '_', name)
        name = name.strip('_').lower()
        return name or 'col'

    def _classify_column(self, col: str, series: pd.Series) -> dict:
        """Returns role: id | email | phone | currency | pct | date | numeric | categorical | text"""
        col_l   = col.lower()
        sample  = series.dropna().astype(str).head(50).tolist()
        n_uniq  = series.nunique()
        n_total = len(series)

        if ID_PATTERNS.search(col_l):
            return {'role': 'id', 'protect': True}

        # Email
        if 'email' in col_l or (sample and sum('@' in s for s in sample) / max(len(sample),1) > 0.5):
            return {'role': 'email', 'protect': True}

        # Phone
        if re.search(r'phone|mobile|tel|fax', col_l):
            return {'role': 'phone', 'protect': True}

        # Currency — value test
        if sample:
            curr_hits = sum(bool(re.search(r'[\$€£¥₹]|^\d[\d,]+\.\d{2}$', s)) for s in sample)
            if curr_hits / max(len(sample),1) > 0.3:
                return {'role': 'currency', 'protect': False}

        # Percentage
        if sample:
            pct_hits = sum(s.strip().endswith('%') for s in sample)
            if pct_hits / max(len(sample),1) > 0.3:
                return {'role': 'pct', 'protect': False}

        dtype = series.dtype
        if pd.api.types.is_numeric_dtype(dtype):
            return {'role': 'numeric', 'protect': False}

        # Date attempt
        if pd.api.types.is_datetime64_any_dtype(dtype):
            return {'role': 'date', 'protect': False}

        if sample:
            date_hits = sum(self._looks_like_date(s) for s in sample[:20])
            if date_hits / max(min(len(sample),20),1) > 0.6:
                return {'role': 'date', 'protect': False}

        # Categorical vs free text
        if n_uniq <= MAX_CATEGORIES and n_uniq / max(n_total,1) < 0.5:
            return {'role': 'categorical', 'protect': False}

        return {'role': 'text', 'protect': False}

    def _looks_like_date(self, s: str) -> bool:
        s = s.strip()
        for fmt in DATE_FORMATS:
            try:
                datetime.strptime(s, fmt)
                return True
            except ValueError:
                pass
        return bool(re.search(r'\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}[-/]\d{4}', s))

    # ══════════════════════════════════════════════════════════════════════════
    # PASS 2 — Value-level cleaning
    # ══════════════════════════════════════════════════════════════════════════
    def _pass2_value_cleaning(self):
        self._log_section('PASS 2 — Value Cleaning')
        schema = self.report['schema']

        curr_cols, pct_cols, text_cols, prot_cols = [], [], [], []

        for col in self.df.columns:
            role = schema.get(col, {}).get('role', 'text')
            prot = schema.get(col, {}).get('protect', False)

            if prot:
                prot_cols.append(col)
                continue

            # Fake-null normalization (all types)
            self.df[col] = self.df[col].apply(self._normalize_fake_nulls)

            if role == 'currency':
                self._clean_currency(col)
                curr_cols.append(col)

            elif role == 'pct':
                self._clean_percentage(col)
                pct_cols.append(col)

            elif role in ('categorical', 'text'):
                self._clean_text_col(col)
                text_cols.append(col)

            elif role == 'numeric':
                self._coerce_numeric(col)

        self.report['currency_cols']   = curr_cols
        self.report['pct_cols']        = pct_cols
        self.report['text_fixed']      = text_cols
        self.report['protected_cols']  = prot_cols

        if curr_cols:
            self._step(f'Stripped currency symbols from {len(curr_cols)} column(s): {", ".join(curr_cols[:3])}')
        if pct_cols:
            self._step(f'Converted percentage strings to decimals in {len(pct_cols)} column(s)')
        if text_cols:
            self._step(f'Normalized text casing and whitespace in {len(text_cols)} column(s)')

    def _normalize_fake_nulls(self, val):
        if pd.isna(val):
            return np.nan
        s = str(val).strip().lower()
        if s in FAKE_NULLS:
            return np.nan
        return val

    def _clean_currency(self, col: str):
        def parse_currency(v):
            if pd.isna(v):
                return np.nan
            s = re.sub(CURRENCY_SYMBOLS, '', str(v)).strip()
            s = re.sub(r'\s+', '', s)
            try:
                return float(s)
            except ValueError:
                return np.nan
        self.df[col] = self.df[col].apply(parse_currency)
        self._log(f'Currency col "{col}" → stripped symbols, cast to float')

    def _clean_percentage(self, col: str):
        def parse_pct(v):
            if pd.isna(v):
                return np.nan
            s = str(v).strip().rstrip('%')
            try:
                return float(s) / 100.0
            except ValueError:
                return np.nan
        self.df[col] = self.df[col].apply(parse_pct)
        self._log(f'Pct col "{col}" → converted to decimal (e.g. 25% → 0.25)')

    def _clean_text_col(self, col: str):
        orig = self.df[col].copy()
        # Remove hidden / control characters
        self.df[col] = self.df[col].apply(lambda v: self._clean_text_value(v))
        # Normalize whitespace
        self.df[col] = self.df[col].str.strip().str.replace(r'\s+', ' ', regex=True)
        # Consistent casing: Title Case for categorical, leave text as-is
        role = self.report['schema'].get(col, {}).get('role', 'text')
        if role == 'categorical':
            self.df[col] = self.df[col].str.title()

    def _clean_text_value(self, v):
        if pd.isna(v):
            return v
        # Remove control characters (keep printable + standard spaces)
        cleaned = ''.join(c for c in str(v) if unicodedata.category(c)[0] != 'C' or c in '\t\n ')
        cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', cleaned)
        return cleaned.strip() or np.nan

    def _coerce_numeric(self, col: str):
        if not pd.api.types.is_numeric_dtype(self.df[col]):
            coerced = pd.to_numeric(self.df[col], errors='coerce')
            success = coerced.notna().sum()
            if success / max(len(self.df), 1) > 0.5:
                self.df[col] = coerced
                self.report['type_coercions'][col] = 'string → numeric'
                self._log(f'Coerced "{col}" to numeric ({success} values converted)')

    # ══════════════════════════════════════════════════════════════════════════
    # PASS 3 — Missing value imputation
    # ══════════════════════════════════════════════════════════════════════════
    def _pass3_missing_values(self):
        self._log_section('PASS 3 — Missing Value Imputation')
        schema   = self.report['schema']
        filled   = {}
        dropped  = []

        for col in list(self.df.columns):
            null_ct = int(self.df[col].isnull().sum())
            if null_ct == 0:
                continue

            pct_null = null_ct / len(self.df)
            role     = schema.get(col, {}).get('role', 'text')
            protect  = schema.get(col, {}).get('protect', False)

            # Drop if >60% missing and not protected
            if pct_null > 0.60 and not protect:
                self.df.drop(columns=[col], inplace=True)
                dropped.append(col)
                self._log(f'Dropped "{col}" — {pct_null:.0%} missing (exceeds 60% threshold)')
                continue

            if role in ('id', 'email', 'phone') or protect:
                # Leave nulls in protected columns untouched
                continue

            if role == 'numeric' or role == 'currency' or role == 'pct':
                strategy, fill_val = self._impute_numeric(col)
            elif role == 'date':
                strategy, fill_val = self._impute_date(col)
            else:
                strategy, fill_val = self._impute_categorical(col)

            filled[col] = {
                'strategy':   strategy,
                'fill_value': str(fill_val)[:40] if fill_val is not None else None,
                'count':      null_ct,
                'pct':        round(pct_null * 100, 1)
            }
            self._log(f'"{col}": filled {null_ct} nulls using {strategy} '
                      f'(fill={str(fill_val)[:30]})')

        self.report['missing_handled'] = filled
        self.report['dropped_cols']    = dropped

        if filled:
            total = sum(v['count'] for v in filled.values())
            self._step(f'Imputed {total:,} missing values across {len(filled)} column(s) '
                       f'using smart per-column strategies')
        if dropped:
            self._step(f'Dropped {len(dropped)} column(s) with >60% missing data: '
                       + ', '.join(dropped[:4]))

    def _impute_numeric(self, col: str):
        s = self.df[col].dropna()
        if len(s) < 3:
            self.df[col].fillna(0, inplace=True)
            return 'constant (0)', 0

        skewness = abs(s.skew())
        if skewness < 0.5:
            # Near-normal → mean
            fill_val = round(float(s.mean()), 4)
            self.df[col].fillna(fill_val, inplace=True)
            return 'mean (near-normal dist.)', fill_val
        else:
            # Skewed → median
            fill_val = round(float(s.median()), 4)
            self.df[col].fillna(fill_val, inplace=True)
            return 'median (skewed dist.)', fill_val

    def _impute_date(self, col: str):
        before = self.df[col].isnull().sum()
        self.df[col] = self.df[col].ffill()
        self.df[col] = self.df[col].bfill()
        after = self.df[col].isnull().sum()
        filled = before - after
        if after > 0:
            # Still some nulls — leave them (better than inventing dates)
            pass
        return 'forward-fill / backward-fill', f'{filled} filled, {after} left null'

    def _impute_categorical(self, col: str):
        s       = self.df[col].dropna()
        pct_null= self.df[col].isnull().sum() / len(self.df)
        modes   = s.mode()

        if len(modes) == 0 or pct_null > 0.3:
            # Very sparse — mark explicitly
            self.df[col].fillna('Unknown', inplace=True)
            return 'constant (Unknown)', 'Unknown'
        else:
            fill_val = modes.iloc[0]
            self.df[col].fillna(fill_val, inplace=True)
            return 'mode', fill_val

    # ══════════════════════════════════════════════════════════════════════════
    # PASS 4 — Duplicate resolution
    # ══════════════════════════════════════════════════════════════════════════
    def _pass4_duplicates(self):
        self._log_section('PASS 4 — Duplicate Resolution')

        # 4a. Exact duplicates
        before       = len(self.df)
        self.df.drop_duplicates(inplace=True)
        self.df.reset_index(drop=True, inplace=True)
        exact_removed = before - len(self.df)
        self.report['duplicates_removed'] = exact_removed

        if exact_removed:
            self._log(f'Removed {exact_removed} exact duplicate rows')
            self._step(f'Removed {exact_removed} exact duplicate row(s)')

        # 4b. Business-key duplicates (numeric ID + date combo)
        id_cols   = [c for c, v in self.report['schema'].items()
                     if v['role'] in ('id',) and c in self.df.columns]
        date_cols = [c for c, v in self.report['schema'].items()
                     if v['role'] == 'date' and c in self.df.columns]

        biz_key = id_cols[:1] + date_cols[:1]
        biz_dups = 0
        if len(biz_key) >= 1:
            biz_dups = int(self.df.duplicated(subset=biz_key, keep='first').sum())
            if biz_dups > 0:
                self.df.drop_duplicates(subset=biz_key, keep='first', inplace=True)
                self.df.reset_index(drop=True, inplace=True)
                self._log(f'Removed {biz_dups} business-key duplicates on {biz_key}')
                self._step(f'Removed {biz_dups} business-key duplicate(s) using key: {biz_key}')

        self.report['business_key_dups'] = biz_dups

    # ══════════════════════════════════════════════════════════════════════════
    # PASS 5 — Date parsing + enrichment
    # ══════════════════════════════════════════════════════════════════════════
    def _pass5_date_enrichment(self):
        self._log_section('PASS 5 — Date Parsing & Enrichment')
        schema     = self.report['schema']
        date_cols  = [c for c, v in schema.items()
                      if v['role'] == 'date' and c in self.df.columns]
        parsed     = []
        derived    = []

        for col in date_cols:
            if not pd.api.types.is_datetime64_any_dtype(self.df[col]):
                converted = pd.to_datetime(self.df[col],
                                           errors='coerce', dayfirst=False)
                ok_rate = converted.notna().sum() / max(len(converted), 1)
                if ok_rate >= 0.5:
                    self.df[col] = converted
                    parsed.append(col)
                    self._log(f'Parsed "{col}" as datetime ({ok_rate:.0%} success)')
                else:
                    self._log(f'Skipped "{col}" — only {ok_rate:.0%} parsed successfully')
                    continue

            # Create derived features (only if useful = has >= 10 unique dates)
            if self.df[col].nunique() >= 10:
                base = col.replace('_date','').replace('date_','').strip('_')
                year_col  = f'{base}_year'
                month_col = f'{base}_month'
                qtr_col   = f'{base}_quarter'

                self.df[year_col]  = self.df[col].dt.year
                self.df[month_col] = self.df[col].dt.month
                self.df[qtr_col]   = self.df[col].dt.quarter
                derived.extend([year_col, month_col, qtr_col])
                self._log(f'Created derived features: {year_col}, {month_col}, {qtr_col}')

        self.report['dates_parsed']  = parsed
        self.report['date_features'] = derived

        if parsed:
            self._step(f'Parsed {len(parsed)} date column(s) and created '
                       f'{len(derived)} derived time features')

    # ══════════════════════════════════════════════════════════════════════════
    # PASS 6 — Outlier capping
    # ══════════════════════════════════════════════════════════════════════════
    def _pass6_outliers(self):
        self._log_section('PASS 6 — Outlier Detection & Capping')
        schema       = self.report['schema']
        capped       = {}

        num_cols = [c for c in self.df.select_dtypes(include='number').columns
                    if schema.get(c, {}).get('role') not in ('id',)
                    and not schema.get(c, {}).get('protect', False)]

        for col in num_cols:
            s = self.df[col].dropna()
            if len(s) < 10 or s.nunique() <= 5:
                continue

            Q1, Q3 = s.quantile(0.25), s.quantile(0.75)
            IQR    = Q3 - Q1
            if IQR == 0:
                continue

            lower  = Q1 - 1.5 * IQR
            upper  = Q3 + 1.5 * IQR
            mask   = (self.df[col] < lower) | (self.df[col] > upper)
            count  = int(mask.sum())

            if count > 0:
                # Z-score double-check
                try:
                    zscores = np.abs(sp_stats.zscore(s))
                    z_outliers = int((zscores > 3).sum())
                except Exception:
                    z_outliers = count

                self.df[col] = self.df[col].clip(lower=lower, upper=upper)
                capped[col]  = {
                    'iqr_count':     count,
                    'zscore_count':  z_outliers,
                    'lower_fence':   round(float(lower), 4),
                    'upper_fence':   round(float(upper), 4),
                    'pct_affected':  round(count / len(self.df) * 100, 2)
                }
                self._log(f'"{col}": capped {count} outliers '
                          f'[{lower:.2f}, {upper:.2f}], z-score violations: {z_outliers}')

        self.report['outliers_capped'] = capped
        if capped:
            total = sum(v['iqr_count'] for v in capped.values())
            self._step(f'Capped {total:,} outlier(s) across {len(capped)} column(s) '
                       f'using IQR Tukey fences')

    # ══════════════════════════════════════════════════════════════════════════
    # PASS 7 — Quality scoring
    # ══════════════════════════════════════════════════════════════════════════
    def _pass7_quality_score(self):
        self._log_section('PASS 7 — Data Quality Score')

        def score_df(df: pd.DataFrame, dup_count: int) -> float:
            n_cells     = df.shape[0] * df.shape[1]
            null_pct    = df.isnull().sum().sum() / max(n_cells, 1)
            dup_pct     = dup_count / max(len(df), 1)

            completeness = (1 - null_pct) * 40          # 40 pts
            uniqueness   = (1 - dup_pct)  * 20          # 20 pts
            consistency  = self._consistency_score() * 30 # 30 pts
            validity     = 10                             # 10 pts baseline

            return min(round(completeness + uniqueness + consistency + validity, 1), 100.0)

        self.report['quality_before'] = score_df(self.original,
                                                  int(self.original.duplicated().sum()))
        self.report['quality_after']  = score_df(self.df,
                                                  int(self.df.duplicated().sum()))
        self._log(f"Quality score: {self.report['quality_before']} → "
                  f"{self.report['quality_after']} / 100")

    def _consistency_score(self) -> float:
        """Ratio of numeric columns with normal-ish distribution (skew < 2)."""
        num_cols = self.df.select_dtypes(include='number').columns
        if len(num_cols) == 0:
            return 0.8
        ok = sum(1 for c in num_cols if abs(self.df[c].skew()) < 2)
        return ok / len(num_cols)

    # ── Helpers ────────────────────────────────────────────────────────────────
    def _log_section(self, title: str):
        self.log.append({'type': 'section', 'text': title})

    def _log(self, msg: str):
        self.log.append({'type': 'detail', 'text': msg})
        logger.debug(msg)

    def _step(self, msg: str):
        self.report['steps'].append(msg)
        self.log.append({'type': 'step', 'text': msg})
