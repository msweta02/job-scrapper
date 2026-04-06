import requests
import pandas as pd
import json
import time
from datetime import datetime
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

ACTOR_ID   = "curious_coder~linkedin-jobs-scraper"
TOKEN_FILE = "config.json"
OUTPUT_DIR = Path("output")  # base output folder

# config.json format:
# {
#   "apify_api_token":   "apify_api_xxxxxxxxxxxx",
#   "anthropic_api_key": "sk-ant-xxxxxxxxxxxx",
#   "exclude_titles":    ["Senior", "Staff", "Principal"],
#   "exclude_companies": ["Infosys", "Wipro"]
# }

# ── Load config ───────────────────────────────────────────────────────────────

def load_config(path: str) -> tuple[str, list, list]:
    with open(path, "r") as f:
        cfg = json.load(f)
    token = cfg.get("apify_api_token")
    if not token:
        raise ValueError("'apify_api_token' key not found in config file.")
    exclude_titles    = [t.lower() for t in cfg.get("exclude_titles",    [])]
    exclude_companies = [c.lower() for c in cfg.get("exclude_companies", [])]
    return token, exclude_titles, exclude_companies

# ── Create daily output folders ───────────────────────────────────────────────

def get_daily_dirs() -> tuple[Path, Path]:
    today       = datetime.now().strftime("%Y-%m-%d")
    daily_dir   = OUTPUT_DIR / today
    resumes_dir = daily_dir / "resumes"
    daily_dir.mkdir(parents=True, exist_ok=True)
    resumes_dir.mkdir(parents=True, exist_ok=True)
    print(f"📁 Output folder: {daily_dir.resolve()}")
    return daily_dir, resumes_dir

# ── Run Actor ─────────────────────────────────────────────────────────────────

def run_actor(token: str) -> str:
    linkedin_url = (
        "https://www.linkedin.com/jobs/search/"
        "?keywords=Data+Engineer"
        "&location=United+States"
        "&geoId=103644278"
        "&f_TPR=r86400"
        "&f_EA=true"
        "&sortBy=DD"
    )

    payload = {
        "urls":          [linkedin_url],
        "count":         50,
        "scrapeCompany": False,
    }

    print("▶ Starting Apify Actor run...")
    print(f"  Search URL: {linkedin_url}")
    res = requests.post(
        f"https://api.apify.com/v2/acts/{ACTOR_ID}/runs",
        params={"token": token},
        json=payload,
        timeout=30,
    )
    res.raise_for_status()

    run_id     = res.json()["data"]["id"]
    dataset_id = res.json()["data"]["defaultDatasetId"]
    print(f"  Run ID:     {run_id}")
    print(f"  Dataset ID: {dataset_id}")

    poll_url = f"https://api.apify.com/v2/actor-runs/{run_id}"
    print("⏳ Waiting for run to complete", end="", flush=True)

    while True:
        status_res = requests.get(poll_url, params={"token": token}, timeout=15)

        if status_res.status_code in (502, 503, 504):
            print(f"\n⚠️  Got {status_res.status_code}, retrying in 10s...")
            time.sleep(10)
            continue

        status_res.raise_for_status()
        data   = status_res.json()["data"]
        status = data["status"]

        if status == "SUCCEEDED":
            print(" ✓")
            break
        elif status in ("FAILED", "ABORTED", "TIMED-OUT"):
            log_url = f"https://api.apify.com/v2/actor-runs/{run_id}/log"
            log_res = requests.get(log_url, params={"token": token}, timeout=15)
            print(f"\n❌ Actor run failed with status: {status}")
            print(f"   Exit code : {data.get('exitCode')}")
            print(f"\n--- Actor Log (last 2000 chars) ---")
            print(log_res.text[-2000:] if log_res.ok else "Could not fetch log.")
            raise RuntimeError(f"Actor run ended with status: {status}")
        else:
            print(".", end="", flush=True)
            time.sleep(5)

    return dataset_id

# ── Fetch results ─────────────────────────────────────────────────────────────

def fetch_results(token: str, dataset_id: str) -> list[dict]:
    res = requests.get(
        f"https://api.apify.com/v2/datasets/{dataset_id}/items",
        params={"token": token, "limit": 50},
        timeout=30,
    )
    res.raise_for_status()
    jobs = res.json()
    print(f"✅ Fetched {len(jobs)} jobs.")

    if not jobs:
        print("\n⚠️  No results returned. Common causes:")
        print("   1. LinkedIn URL returns no results in a headless browser")
        print("   2. f_EA=true is too restrictive — try removing it")
        print("   3. f_TPR=r86400 (24hrs) — try r604800 (7 days)")
        print("   4. LinkedIn blocked the request — try again later")

    return jobs

# ── Apply exclusions ──────────────────────────────────────────────────────────

def apply_exclusions(
    jobs: list[dict],
    exclude_titles: list[str],
    exclude_companies: list[str],
) -> list[dict]:

    before   = len(jobs)
    filtered = []

    for j in jobs:
        title   = (j.get("title")       or j.get("jobTitle")    or "").lower()
        company = (j.get("companyName") or j.get("company")     or "").lower()

        if any(ex in title for ex in exclude_titles):
            print(f"  ✗ Excluded title:   '{j.get('title')}' @ {j.get('companyName')}")
            continue

        if any(ex in company for ex in exclude_companies):
            print(f"  ✗ Excluded company: '{j.get('companyName')}'")
            continue

        filtered.append(j)

    after = len(filtered)
    print(f"🔍 Exclusions applied: {before - after} removed → {after} jobs remaining.")
    return filtered

# ── Deduplicate by company + title + url ─────────────────────────────────────

def deduplicate_jobs(jobs: list[dict]) -> list[dict]:
    seen    = {}   # key → index in merged list
    merged  = []

    for j in jobs:
        company  = (j.get("companyName") or j.get("company") or "").strip()
        title    = (j.get("title")       or j.get("jobTitle") or "").strip()
        url      = (j.get("applyUrl")    or j.get("url")      or "").strip()
        location = (j.get("location")    or "").strip()

        # Key: company + title + url (url handles same job, diff location pages)
        # If url is empty fall back to company + title only
        key = (company.lower(), title.lower(), url.lower() if url else "")

        if key in seen:
            idx = seen[key]
            existing_loc = merged[idx].get("location") or ""
            if location and location not in existing_loc:
                merged[idx]["location"] = existing_loc + "\n" + location
        else:
            seen[key] = len(merged)
            merged.append(dict(j))   # copy so we don't mutate original

    removed = len(jobs) - len(merged)
    print(f"🔗 Deduplicated: {removed} duplicate(s) merged → {len(merged)} unique jobs.")
    return merged



def save_to_excel(jobs: list[dict], daily_dir: Path) -> Path:
    if not jobs:
        print("⚠️  No jobs to save.")
        return None

    rows = []
    for j in jobs:
        rows.append({
            "Company":                j.get("companyName")        or j.get("company"),
            "Job Title":              j.get("title")              or j.get("jobTitle"),
            "Location":               j.get("location"),
            "Posted Date":            j.get("postedAt")           or j.get("publishedAt"),
            "Applicants":             j.get("applicantsCount"),
            "Employment Type":        j.get("employmentType"),
            "Seniority Level":        j.get("seniorityLevel"),
            "Workplace Type":         j.get("workplaceTypes/0"),
            "Salary":                 j.get("salary"),
            "Job Poster Name":        j.get("jobPosterName"),
            "Job Poster Title":       j.get("jobPosterTitle"),
            "Job Poster Profile URL": j.get("jobPosterProfileUrl"),
            "Job Description":        j.get("description"),
            "Job LinkedIn URL":                j.get("inputUrl")           or j.get("url"),
            "Job URL":                j.get("applyUrl")           or j.get("url"),
        })

    df = pd.DataFrame(rows)
    df.sort_values(by="Company", ascending=True, inplace=True, na_position="last")

    timestamp = datetime.now().strftime("%H%M%S")
    out_path  = daily_dir / f"linkedin_jobs_{timestamp}.xlsx"

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Jobs")
        ws = writer.sheets["Jobs"]

        # Wrap text in Location column (col C = index 3)
        from openpyxl.styles import Alignment
        loc_col = None
        for cell in ws[1]:
            if cell.value == "Location":
                loc_col = cell.column_letter
                break
        if loc_col:
            for cell in ws[loc_col]:
                cell.alignment = Alignment(wrap_text=True, vertical="top")

        # Auto-fit column widths
        for col in ws.columns:
            max_len = max(
                max((len(line) for line in str(cell.value).split("\n")), default=0)
                if cell.value else 0
                for cell in col
            )
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 80)

    print(f"💾 Saved to: {out_path.resolve()}")
    return out_path

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    token, exclude_titles, exclude_companies = load_config(TOKEN_FILE)

    print(f"🚫 Excluding titles:    {exclude_titles    or 'none'}")
    print(f"🚫 Excluding companies: {exclude_companies or 'none'}")

    daily_dir, resumes_dir = get_daily_dirs()

    dataset_id = run_actor(token)
    jobs       = fetch_results(token, dataset_id)
    jobs       = apply_exclusions(jobs, exclude_titles, exclude_companies)
    jobs       = deduplicate_jobs(jobs)
    excel_path = save_to_excel(jobs, daily_dir)

    # ── Optionally run resume tailor ─────────────────────────────────────────
    if excel_path and jobs:
        from resume_tailor import tailor_resumes
        tailor_resumes(excel_path, resumes_dir)

if __name__ == "__main__":
    main()