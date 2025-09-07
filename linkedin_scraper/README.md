# LinkedIn Job Scraper

A simple, efficient LinkedIn job scraper with data analysis tools.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the scraper
python src/linkedin_scraper.py

# Search the data
python scripts/simple_search.py
```

## Project Structure

```
linkedin_scraper/
├── linkedin_final.py       # Main pipeline orchestrator
├── src/                    # Core scraper source code
│   ├── linkedin_scraper.py # Main scraper script
│   └── login.py            # LinkedIn login functionality
├── scripts/                # Utility and automation scripts
│   ├── migrate_to_db.py    # Database migration script
│   ├── setup_database.py   # Database setup helper
│   ├── simple_search.py    # Interactive job search tool
│   ├── analyze_posting_patterns.py  # Analyze job posting patterns
│   └── run_pipeline.py     # Pipeline runner
├── data/                   # Data files and outputs
│   ├── linkedin_jobs_simplified.json  # Scraped job data
│   ├── scraping_progress.json   # Resume data for interrupted runs
│   └── li_cookies.pkl      # LinkedIn session cookies
├── database/               # Database-related files
│   └── database_schema.sql # PostgreSQL database schema
├── docs/                   # Documentation
│   ├── DATABASE_SETUP_GUIDE.md # Database setup instructions
│   ├── CRON_SETUP.md      # Automation setup guide
│   └── hybrid_cron_setup.md   # Hybrid scraping strategy guide
├── requirements.txt        # Python dependencies
├── .gitignore             # Git ignore rules
└── README.md              # This file
```

## Files

### Core Files
- `src/linkedin_scraper.py` - Main scraper with optimizations
- `data/linkedin_jobs_simplified.json` - Jobs with shard info included (3,534 jobs)

### Analysis Tools
- `scripts/simple_search.py` - Interactive search tool

### Database Files
- `database/database_schema.sql` - PostgreSQL schema definition
- `scripts/migrate_to_db.py` - Data migration script
- `scripts/setup_database.py` - Database setup script

### Documentation
- `docs/DATABASE_SETUP_GUIDE.md` - Database setup instructions

### Data Files
- `data/li_cookies.pkl` - LinkedIn session cookies

## Features

### Scraper Optimizations
- **Concurrent Job Processing**: 3x faster with ThreadPoolExecutor
- **Adaptive Rate Limiting**: Prevents blocking, optimizes speed
- **Smart Shard Prioritization**: Orders shards by performance
- **Memory-Efficient Deduplication**: Uses sets for O(1) duplicate detection
- **Progress Tracking**: Resume interrupted scrapes

### Simplified Data Structure
Each job now includes all filter information directly:
```json
{
  "job_id": "4287995271",
  "title": "Software Engineer",
  "company_name": "Google", 
  "posted_dt": "2025-08-18T18:59:06+00:00",
  "is_repost": true,
  "url": "https://...",
  "source": "api",
  "shard_key": "4_F_2",
  "exp_level": "4",     // Mid-Senior
  "job_type": "F",      // Full-time  
  "workplace_type": "2", // Remote
  "filters": "mid-senior+full_time+remote"
}
```

## Usage

### Basic Scraping
   ```bash
# Full scrape
python src/linkedin_scraper.py

# Limited scrape
python src/linkedin_scraper.py --max-shards 5

# Resume interrupted scrape
python src/linkedin_scraper.py --resume

# Run full pipeline
python linkedin_final.py --mode daily

# Skip login (use existing cookies)
python linkedin_final.py --mode daily --skip-login

# Skip database migration
python linkedin_final.py --mode daily --skip-migration
```

### Searching Data
   ```bash
# Interactive search
python scripts/simple_search.py

# Quick searches
python -c "
import sys; sys.path.append('scripts')
from simple_search import search_by_company, search_remote_jobs, display_jobs
jobs = search_by_company('Google')
display_jobs(jobs, 3)
"
```

### Database Operations
```bash
# Setup database
python scripts/setup_database.py

# Migrate data to PostgreSQL
python scripts/migrate_to_db.py

# Run sample queries
psql -d linkedin_jobs -f database/database_schema.sql
```

## Data Insights

- **Total Jobs**: 3,534
- **Companies**: 1,221
- **Top Hiring**: Tap Growth Ai (350), Mindrift (250), Telus Digital AI (231)
- **Remote Jobs**: 40% (1,423 jobs)
- **Experience Levels**: Mid-Senior (57%), Entry (19%), Director (8%)
- **Job Types**: Full-time (73%), Part-time (16%), Contract (7%)

## Filter Codes

### Experience Levels
- `1` - Intern
- `2` - Entry Level  
- `3` - Associate
- `4` - Mid-Senior
- `5` - Director
- `6` - Executive

### Job Types  
- `F` - Full-time
- `P` - Part-time
- `C` - Contract
- `I` - Internship
- `T` - Temporary
- `V` - Volunteer
- `O` - Other

### Workplace Types
- `1` - On-site
- `2` - Remote
- `3` - Hybrid

## Simple Queries

With the simplified structure, you can easily:

```python
# Get all remote jobs
remote_jobs = [job for job in jobs if job['workplace_type'] == '2']

# Get mid-senior full-time jobs
mid_senior_fulltime = [job for job in jobs 
                      if job['exp_level'] == '4' and job['job_type'] == 'F']

# Get jobs from specific shard
shard_jobs = [job for job in jobs if job['shard_key'] == '4_F_2']

# Get jobs by company
google_jobs = [job for job in jobs if 'google' in job['company_name'].lower()]
```

## Configuration

Edit `src/linkedin_scraper.py` constants:
```python
CONCURRENT_WORKERS = 5      # Parallel job fetching
MAX_PAGES_PER_SHARD = 40    # Pages per search
BASE_DELAY = 2.0            # Rate limiting delay
```

## Requirements

- Python 3.8+
- Chrome browser
- LinkedIn account (for cookies)

## Troubleshooting

**Scraper stops working**: Update LinkedIn cookies in `li_cookies.pkl`
**Browser issues**: Update Chrome and chromedriver
**Rate limiting**: Increase `BASE_DELAY` in scraper settings

## Next Steps

1. **Build a simple API** for job search
2. **Add more job sites** (Indeed, Glassdoor)
3. **Extract salary information** from job descriptions  
4. **Parse location details** (city, state, country)

The focus is on keeping things simple and maintainable rather than over-engineering. 