import os
import requests
from dotenv import load_dotenv

load_dotenv()

# --- 1. Get credentials from .env ---
APP_ID = os.getenv("ADZUNA_ID")
APP_KEY = os.getenv("ADZUNA_KEY")

if not APP_ID or not APP_KEY:
    raise ValueError("ADZUNA_ID and ADZUNA_KEY must be set in .env file")

# --- 2. Define search variables (modify these) ---
what_param = "software engineer"  # Job title/keywords (broad)
what_phrase_param = "RAG"  # Exact phrase to match
where_param = "Los Angeles, CA"  # Location
results_per_page_param = 20  # Results per page (max 50)
sort_by_param = "date"  # Sort by: date, salary, relevance
full_time_param = 1  # 1 = full-time only, 0 = any

# --- 3. Build params dictionary ---
params = {
    "app_id": APP_ID,
    "app_key": APP_KEY,
    "what": what_param,
    "what_phrase": what_phrase_param,
    "where": where_param,
    "results_per_page": results_per_page_param,
    "sort_by": sort_by_param,
    "full_time": full_time_param,
}

# --- 4. Make the API request ---
url = "https://api.adzuna.com/v1/api/jobs/us/search/1"

try:
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()
except requests.exceptions.RequestException as e:
    print(f"Error fetching jobs: {e}")
    exit(1)

# --- 5. Display results ---
print(
    f"\n📍 Found {data.get('count', 0)} jobs matching '{what_param} + {what_phrase_param}' in {where_param}"
)
print(f"📊 Total results available: {data.get('total', 0)}\n")

jobs = data.get("results", [])
if not jobs:
    print("No jobs found. Try broadening your search terms.")
else:
    print("-" * 70)
for i, job in enumerate(jobs, 1):
    print(f"{i}. {job.get('title', 'N/A')}")
    print(f"   Company: {job.get('company', {}).get('display_name', 'N/A')}")
    print(f"   Location: {job.get('location', {}).get('area', ['N/A'])[0]}")
    print(f"   Salary: {job.get('salary_min', 'N/A')} - {job.get('salary_max', 'N/A')}")
    print(f"   Apply at: {job.get('redirect_url', 'N/A')}")

    desc = job.get("description", "")
    if desc:
        snippet = desc[:1000] + "..."
        print(f"   Description: {snippet}")
    print("-" * 70)

# --- 6. Summary ---
print("\n📋 Summary for RAG analysis:")
print(f"   - Total jobs fetched: {len(jobs)}")
companies = set(job.get("company", {}).get("display_name", "") for job in jobs)
print(f"   - Unique companies: {len(companies)}")
titles = [job.get("title", "") for job in jobs]
print(f"   - Job titles: {', '.join(titles[:5])}{'...' if len(titles) > 5 else ''}")
