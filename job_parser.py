import os
import requests
from dotenv import load_dotenv

load_dotenv()

# --- 1. Get credentials ---
APP_ID = os.getenv("ADZUNA_ID")
APP_KEY = os.getenv("ADZUNA_KEY")

if not APP_ID or not APP_KEY:
    raise ValueError("ADZUNA_ID and ADZUNA_KEY must be set in .env file")

# --- 2. Define search variables ---
what_param = "software engineer"
what_phrase_param = "RAG"
where_param = "Los Angeles, CA"
results_per_page_param = 50
sort_by_param = "date"
full_time_param = 1

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

# --- 3. Fetch jobs ---
url = "https://api.adzuna.com/v1/api/jobs/us/search/1"

try:
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()
except requests.exceptions.RequestException as e:
    print(f"Error fetching jobs: {e}")
    exit(1)

jobs = data.get("results", [])
print(
    f"\n📍 Found {len(jobs)} jobs matching '{what_param} + {what_phrase_param}' in {where_param}"
)
print(f"📊 Total results available: {data.get('total', 0)}\n")

# --- 4. Define location filters ---
REMOTE_KEYWORDS = ["remote", "work from home", "wfh", "home office"]
HYBRID_KEYWORDS = ["hybrid", "flex", "flexible", "onsite/remote", "remote/onsite"]
WEST_COAST_CITIES = [
    "san francisco",
    "sf",
    "santa clara",
    "san jose",
    "oakland",
    "seattle",
    "bellevue",
    "redmond",
    "portland",
    "los angeles",
    "la",
    "santa monica",
    "pasadena",
    "irvine",
    "san diego",
]

# --- 5. Filter and display results ---
print("=" * 80)
print("🔍 FILTERED RESULTS (Remote, Hybrid, or West Coast)")
print("=" * 80)

found_count = 0
for job in jobs:
    location = job.get("location", {}).get("area", [""])[0].lower()
    description = job.get("description", "").lower()
    title = job.get("title", "").lower()
    combined_text = f"{location} {description} {title}"

    is_remote = any(kw in combined_text for kw in REMOTE_KEYWORDS)
    is_hybrid = any(kw in combined_text for kw in HYBRID_KEYWORDS)
    is_west_coast = any(city in location for city in WEST_COAST_CITIES)

    if is_remote or is_hybrid or is_west_coast:
        found_count += 1
        print(f"\n{found_count}. {job.get('title', 'N/A')}")
        print(f"   Company: {job.get('company', {}).get('display_name', 'N/A')}")
        print(f"   Location: {job.get('location', {}).get('area', ['N/A'])[0]}")
        print(
            f"   Salary: {job.get('salary_min', 'N/A')} - {job.get('salary_max', 'N/A')}"
        )

        # Show match type
        match_types = []
        if is_remote:
            match_types.append("🌐 Remote")
        if is_hybrid:
            match_types.append("🔄 Hybrid")
        if is_west_coast:
            match_types.append("🌊 Pacific Time Zone")
        print(f"   Match: {', '.join(match_types)}")

        print(f"   Apply at: {job.get('redirect_url', 'N/A')}")

        desc = job.get("description", "")
        if desc:
            snippet = desc[:400] + "..."
            print(f"   Description: {snippet}")
        print("-" * 70)

print(
    f"\n📊 Summary: Found {found_count} jobs matching location criteria out of {len(jobs)} total."
)
