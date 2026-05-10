# ⚡ AI Smart Data Analyzer v2.0
### Production-grade, portfolio-ready full-stack data analytics application

> **Stack:** Python · Flask · Pandas · SQLite · Matplotlib · Seaborn · ReportLab · HTML · CSS · JS

---

## 📁 Project Structure

```
ai_smart_analyzer/
├── app.py                    ← Flask app, all routes, auth, API
├── core/
│   ├── __init__.py
│   ├── cleaner.py            ← 7-pass advanced cleaning engine
│   ├── visualizer.py         ← Power BI-style chart generator
│   ├── insights.py           ← Analyst-style insight engine
│   └── reporter.py           ← Professional PDF report generator
├── templates/
│   ├── auth.html             ← Login / Signup page
│   └── dashboard.html        ← Main dashboard shell
├── static/
│   ├── css/dashboard.css     ← Power BI-style light theme
│   ├── js/dashboard.js       ← Clean state management
│   ├── charts/               ← Generated chart PNGs
│   └── uploads/              ← Uploaded files + PDFs
├── instance/analyzer.db      ← SQLite database (auto-created)
├── sample_data.csv           ← Test dataset (50 rows)
├── requirements.txt
└── README.md
```

---

## 🚀 Quick Start (4 commands)

```bash
cd ai_smart_analyzer
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open **http://127.0.0.1:5000**

---

## 🔧 Cleaning Engine — 7-Pass Pipeline

| Pass | What it does |
|------|-------------|
| 1. Schema Normalization | Column names → snake_case, type classification (id/email/phone/currency/pct/date/numeric/categorical/text) |
| 2. Value Cleaning | Strip currency symbols, convert percentages, remove hidden Unicode, normalize fake-nulls (nan/null/n.a./-) |
| 3. Missing Value Imputation | Numeric: mean if normal, median if skewed · Categorical: mode or "Unknown" · Dates: ffill/bfill |
| 4. Duplicate Resolution | Exact duplicates + business-key duplicates (ID+date combo) |
| 5. Date Enrichment | Parse mixed formats, create year/month/quarter derived features |
| 6. Outlier Capping | IQR Tukey fences + Z-score cross-validation · Winsorized, never deleted |
| 7. Quality Scoring | Composite score /100: Completeness 40% + Uniqueness 20% + Consistency 30% + Validity 10% |

---

## 📊 Chart Types

| Column Type | Chart |
|-------------|-------|
| Multiple numeric | KPI summary strip |
| Numeric (up to 4) | Histogram + KDE + mean/median lines |
| Categorical (up to 4) | Horizontal sorted bar (top 12 + Other) |
| Date × Numeric | Line chart + rolling avg + trend line |
| 2+ Numeric | Correlation heatmap (lower triangle) |
| 2+ Numeric | Box plot (Z-score normalized) |
| Category + Numeric | Grouped bar + donut share chart |

---

## 🤖 Insight Categories

- Executive Overview · Data Quality · Statistical Highlights
- Distribution Analysis (Shapiro normality test)
- Correlation Analysis · Field Analysis · Time Analysis
- Recommendations (ML readiness, modeling suggestions)

---

## 📄 PDF Report Sections

1. Cover page with quality score badge
2. Executive summary with KPI cards
3. Data overview table + descriptive stats
4. Before vs after cleaning comparison table
5. Missing value imputation detail
6. Key findings (all insights, color-coded by severity)
7. Visualizations (up to 8 best charts)
8. Methodology & Technical Appendix

---

## 🔐 Security

- Passwords hashed with PBKDF2-SHA256 (Werkzeug)
- File type and size validation (32 MB limit)
- Identifier/email/phone columns protected from transformation
- Server-side sessions with configurable secret key
- Set `SECRET_KEY` env variable in production

---

## 📝 Resume Bullet Points

- **Built** a full-stack data analytics SaaS application using Flask, Pandas, SQLite, Matplotlib, Seaborn, and ReportLab — deployable locally with 4 commands
- **Engineered** a 7-pass intelligent data cleaning pipeline supporting schema normalization, smart imputation (median/mean by distribution), IQR + Z-score outlier capping, and automated date enrichment
- **Implemented** a composite data quality scoring system (0–100) measuring completeness, uniqueness, consistency, and validity before and after cleaning
- **Designed** a Power BI-style dashboard with light/dark mode, executive KPI strip, data quality comparison view, interactive chart gallery, and analyst-style insight panel
- **Generated** professional multi-page PDF reports with cover page, before/after cleaning tables, descriptive statistics, curated visualizations, and methodology appendix using ReportLab
- **Automated** chart generation for 7 chart types (histogram + KDE, sorted bar, line + trend, correlation heatmap, box plot, grouped bar, donut) using Matplotlib and Seaborn
- **Produced** analysis-ready cleaned CSV exports with ISO date formatting, consistent encoding (UTF-8 BOM), and analyst-standard column naming
- **Protected** sensitive column types (ID, email, phone, URL) from transformation using regex-based role classification

------------------------------
# AI Smart Data Analyzer

## Project Overview
AI Smart Data Analyzer is a full-stack data cleaning, analysis, visualization, and reporting web application built with Flask, Pandas, Matplotlib/Seaborn, and ReportLab. It allows users to upload messy CSV/XLSX files, clean the data automatically, generate insights, create charts, and download a professional PDF report.

## Why I Built This Project
The goal of this project is to transform raw, messy datasets into analysis-ready data with minimal manual effort. It demonstrates practical data cleaning, automated insights, visualization, and reporting in one end-to-end system.

## Features
- Upload CSV, XLSX, and XLS files
- Automatic schema normalization
- Smart missing value handling
- Duplicate row removal
- Text cleanup and standardization
- Date parsing and feature enrichment
- Outlier detection and capping
- Automated charts generation
- AI-style insights
- Professional PDF report generation
- Clean CSV export for Power BI or Excel

## Tech Stack
- Python
- Flask
- Pandas
- NumPy
- Matplotlib
- Seaborn
- ReportLab
- SQLite
- HTML/CSS/JavaScript

## Project Structure
- `app.py`: Flask backend and routes
- `cleaner.py`: Advanced data cleaning engine
- `insights.py`: Generates business-style insights
- `visualizer.py`: Creates charts
- `reporter.py`: Generates PDF reports
- `dashboard.html`: Main dashboard UI
- `auth.html`: Login/signup UI
- `requirements.txt`: Python dependencies

## How It Works
1. User uploads a raw dataset.
2. The backend loads and validates the file.
3. The cleaning engine standardizes and fixes data.
4. The visualizer generates charts from cleaned data.
5. The insights engine creates analytical observations.
6. The reporter builds a PDF report.
7. The cleaned CSV is exported for Power BI or further analysis.

## Data Cleaning Pipeline
1. Column name normalization
2. Missing value imputation
3. Duplicate removal
4. Text normalization
5. Date parsing and derived features
6. Outlier detection and capping
7. Quality scoring

## Dashboard Usage
After uploading a dataset, the dashboard shows:
- dataset overview
- cleaning summary
- quality score
- charts
- AI insights
- downloadable cleaned CSV
- downloadable PDF report

## Power BI Integration
The cleaned CSV can be imported into Power BI to create:
- KPI cards
- category charts
- trend analysis
- quality summary visuals
- anomaly tracking
- business dashboards

## Example Dataset
This project was tested on dirty retail data such as `shopping_mall_dirty_data.csv`, where it:
- removed duplicates
- handled missing values
- cleaned text fields
- parsed dates
- capped outliers
- generated a professional report

## Future Enhancements
- Support for very large datasets using chunking/Dask
- More advanced validation rules
- Interactive Power BI-style frontend
- Role-based user access
- Scheduled report generation
- Database-backed analysis history

## Conclusion
This project is a strong portfolio-level data analytics application that demonstrates cleaning, analysis, visualization, and reporting in a single workflow.