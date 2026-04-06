# LinkedIn Job Scraper + Resume Tailor

Scrapes job listings from LinkedIn or any company career portal, scores them against your master resume using TF-IDF similarity, and generates tailored resumes for high-relevance jobs using Groq AI.

---

## Folder Structure

```
linkedin-job-scraper/
│
├── config.json              # API tokens and exclusion filters
├── scraper.py               # Scrapes LinkedIn jobs by search filters
├── url_scraper.py           # Fetches jobs from explicit URLs (any portal)
├── score_filter.py          # Scores jobs vs resume, filters by relevance
├── resume_tailor.py         # Generates tailored resumes using Groq AI
├── master_resume.docx       # Your base resume
├── job_urls.txt             # Job URLs for url_scraper.py
├── requirements.txt         # Python dependencies
├── .gitignore
│
└── output/
    └── YYYY-MM-DD/
        ├── linkedin_jobs_HHMMSS.xlsx    # raw scrape output
        ├── url_jobs_HHMMSS.xlsx         # url scraper output
        ├── scored_jobs_HHMMSS.xlsx      # all jobs with scores
        ├── passed_jobs.xlsx             # jobs that passed relevance cutoff
        ├── resume_tailor_report.xlsx    # tailoring report with ATS scores
        └── resumes/
            ├── Google_Data_Engineer.docx
            ├── Meta_Data_Engineer.docx
            └── ...
```

---

## Prerequisites

- Python 3.10+
- [Apify account](https://apify.com) — free plan, no credit card needed
- [Groq account](https://console.groq.com) — free API key

---

## Step 1 — Clone or Download the Project

```bash
cd your-projects-folder
```

---

## Step 2 — Create a Virtual Environment

```bash
# Create
python -m venv venv

# Activate (Mac/Linux)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate
```

You should see `(venv)` in your terminal prompt.

---

## Step 3 — Install Dependencies

```bash
pip install -r requirements.txt
```

To verify:
```bash
pip list
```

---

## Step 4 — Get Your API Keys

### Apify API Token
1. Sign up at [apify.com](https://apify.com) (free, no credit card)
2. Go to **Settings → Integrations**
3. Copy your **Personal API Token**

### Groq API Key
1. Sign up at [console.groq.com](https://console.groq.com) (free)
2. Go to **API Keys → Create Key**
3. Copy the key — starts with `gsk_...`

---

## Step 5 — Configure `config.json`

Create `config.json` in the project root:

```json
{
  "apify_api_token":  "apify_api_xxxxxxxxxxxx",
  "groq_api_key":     "gsk_xxxxxxxxxxxx",
  "exclude_titles":   ["Senior", "Staff", "Principal", "Manager", "Director"],
  "exclude_companies":["Infosys", "Wipro", "Tata Consultancy", "Cognizant"]
}
```

- `exclude_titles` — job titles containing these words are filtered out (partial, case-insensitive)
- `exclude_companies` — companies containing these names are filtered out
- Leave as `[]` for no exclusions

> ⚠️ Never commit `config.json` to GitHub — it contains your secret keys.

---

## Step 6 — Add Your Master Resume

Place your base resume in the project root:
```
master_resume.docx
```

---

## How It Works

```
scraper.py / url_scraper.py
        ↓
  Jobs Excel file
        ↓
  score_filter.py
  Score each job vs master resume (TF-IDF)
  Filter jobs with Relevance Score >= 80
        ↓
  passed_jobs.xlsx
        ↓
  resume_tailor.py
  Generate tailored resume for each job (Groq AI)
        ↓
  resumes/*.docx  +  resume_tailor_report.xlsx
```

---

## Running the App

### Option A — Full Pipeline via LinkedIn Search

Scrapes LinkedIn for Data Engineer jobs in the US, scores them, and tailors resumes:

```bash
python scraper.py
```

Filters applied by default:
- Keywords: Data Engineer
- Location: United States
- Posted: Last 24 hours
- Applicants: ≤ 50 (Early Applicant)
- Max results: 50

---

### Option B — Scrape Specific Job URLs

Use this when you have specific job URLs from LinkedIn, Greenhouse, Lever, Workday, or any company career page.

**1. Add URLs to `job_urls.txt`:**
```
# Lines starting with # are comments — ignored
https://boards.greenhouse.io/stripe/jobs/1234567
https://jobs.lever.co/airbnb/abc-def-123
https://careers.google.com/jobs/results/123456/
https://www.linkedin.com/jobs/view/1234567890/
```

**2. Run:**
```bash
python url_scraper.py
```

Supported portals:
- **Greenhouse** — uses free Greenhouse API (best quality)
- **Lever** — uses free Lever API (best quality)
- **LinkedIn, Workday, iCIMS, Jobvite, Indeed, and others** — HTML scraping

---

### Option C — Score Filter Only

Run scoring on an existing Excel file without re-scraping:

```bash
# Auto-detect most recent Excel
python score_filter.py

# On a specific file
python score_filter.py output/2026-04-04/linkedin_jobs_142301.xlsx
```

Console output:
```
✅ PASS   84/100  Amazon — Data Engineer
✅ PASS   81/100  Databricks — Data Engineer
❌ SKIP   63/100  A1 Solution Pvt ltd — Data Engineer
──────────────────────────────────────────
  ✅ Passed  (>=80): 12 jobs
  ❌ Skipped (< 80): 32 jobs
```

Change the cutoff threshold in `score_filter.py`:
```python
RELEVANCE_CUTOFF = 80   # change to 70, 75, 85 etc.
```

---

### Option D — Resume Tailor Only

Run resume tailoring on an existing Excel without re-scraping or re-scoring:

```bash
# On passed_jobs.xlsx (recommended — already filtered)
python resume_tailor.py output/2026-04-04/passed_jobs.xlsx

# Auto-detect most recent Excel
python resume_tailor.py
```

---

## Scoring

### Relevance Score
Calculated using **TF-IDF cosine similarity** between the job description and master resume. This is a real algorithm — not an AI guess.

```
Score = keyword overlap between JD and resume × 100
```

- **≥ 80** → Resume tailored
- **< 80** → Skipped

### ATS Score
Estimated by Groq AI after the tailored resume is created — reflects how well the new resume matches the JD keywords.

---

## Output Files

| File | Description |
|---|---|
| `linkedin_jobs_*.xlsx` | Raw scraped jobs from LinkedIn |
| `url_jobs_*.xlsx` | Jobs fetched from explicit URLs |
| `scored_jobs_*.xlsx` | All jobs with relevance scores (green=pass, red=skip) |
| `passed_jobs.xlsx` | Only jobs that passed the threshold — input for resume tailor |
| `resume_tailor_report.xlsx` | Report with ATS scores, keywords, gaps per job |
| `resumes/*.docx` | Individual tailored resume per job |

---

## What Each Tailored Resume Contains

| Section | Description |
|---|---|
| **Summary** | ATS-friendly summary tailored to the specific role |
| **Experience** | All 3 roles rewritten with STAR-method bullets, JD keywords prioritized |
| **Technical Skills** | Reordered — most JD-relevant skills listed first |
| **Education** | Both degrees exactly as in master resume |
| **Certifications** | All certifications from master resume |

---

## Deactivate Virtual Environment

```bash
deactivate
```

---

## .gitignore

```
venv/
config.json
output/
__pycache__/
*.pyc
```

---

## Troubleshooting

| Issue | Fix |
|---|---|
| `404 Not Found` on Apify | Actor ID must use `~` not `/`: `curious_coder~linkedin-jobs-scraper` |
| `502 Bad Gateway` | Apify server hiccup — wait and retry |
| `0 jobs returned` | Open the LinkedIn URL in incognito and verify jobs appear |
| `groq_api_key not found` | Check `config.json` has the correct key name |
| `Rate limited` by Groq | Script auto-retries — wait for it; or increase `time.sleep(20)` in `resume_tailor.py` |
| `JSON parse error` | Groq response was cut off — reduce JD length or increase `time.sleep` |
| Resume tailor skips a job | Job has no description in the Excel — normal, it logs a warning |
| Score always low | JD may be missing from Excel — check `Job Description` column is populated |
| No jobs pass threshold | Lower `RELEVANCE_CUTOFF` in `score_filter.py` (try 70) |
