# LinkedIn Job Scraper

A powerful, optimized LinkedIn job scraper that uses API-first approach with intelligent DOM fallback for maximum job coverage.

## 🚀 Features

- **API-First Approach**: Uses LinkedIn's internal APIs for fast, reliable data extraction
- **Smart DOM Fallback**: Intelligent fallback to DOM parsing when API fails
- **Shard-Based Scraping**: Processes all combinations of experience levels, job types, and workplace types
- **Early Empty Page Detection**: Quickly identifies pages with no jobs to avoid timeouts
- **Strategic Rate Limiting**: Intelligent delays to prevent blocking
- **Complete Data Extraction**: Job titles, company names, posting dates, repost detection, direct apply URLs
- **Shard Analytics**: Tracks which combinations yield the most jobs
- **Blacklist Filtering**: Automatically filters out job aggregators and staffing agencies

## 📁 File Structure

```
scraper/
├── linkedin_scraper.py      # Main optimized scraper
├── login.py                 # LinkedIn login and cookie management
├── requirements.txt         # Python dependencies
├── README.md               # This file
├── .gitignore              # Git ignore rules
├── li_cookies.pkl          # Saved LinkedIn cookies (generated)
├── linkedin_jobs.json      # Scraped job data (generated)
├── shard_results.json      # Shard performance analytics (generated)
└── shard_mappings.json     # Job-to-shard mapping data (generated)
```

## 🛠️ Setup

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Login to LinkedIn**:
   ```bash
   python login.py
   ```
   This will open a browser window for you to log in to LinkedIn and save your session cookies.

## 🎯 Usage

### Basic Usage
```bash
python linkedin_scraper.py
```

### Configuration
Edit the `main()` function in `linkedin_scraper.py` to customize:

- **Keywords**: Modify the `keywords` variable for different job searches
- **Shard Limit**: Change `max_shards=5` to control how many shard combinations to process
- **Experience Levels**: Modify `EXP_CODES` for different experience requirements
- **Job Types**: Modify `JT_CODES` for different job types
- **Workplace Types**: Modify `WT_CODES` for different workplace arrangements

## 📊 Output Files

### `linkedin_jobs.json`
Contains all scraped job data with fields:
- `job_id`: LinkedIn job ID
- `title`: Job title
- `company_name`: Company name (extracted from URL path)
- `posted_dt`: ISO formatted posting date
- `is_repost`: Boolean indicating if job is a repost
- `url`: Direct apply URL (prefers company apply URL when available)
- `source`: Data source ('api' or 'dom')

### `shard_results.json`
Shard performance analytics showing:
- Job count per shard combination
- Experience level, job type, and workplace type labels
- Success rates for different combinations

### `shard_mappings.json`
Maps each job to the shard(s) it was found in, useful for:
- Understanding which combinations are most productive
- Filtering jobs by specific criteria
- Optimizing future scraping runs

## 🔧 Technical Details

### Shard Combinations
The scraper processes all combinations of:
- **Experience Levels**: Intern, Entry, Associate, Mid-Senior, Director, Executive
- **Job Types**: Internship, Full-time, Contract, Temporary, Part-time, Volunteer, Other
- **Workplace Types**: Remote, On-site, Hybrid

### API Endpoints Used
- `voyagerJobsDashJobCards`: Get job IDs and basic info
- `jobs/jobPostings/{job_id}`: Get detailed job information

### Optimization Features
- **Early Empty Page Detection**: Uses WebDriverWait to quickly identify pages with no jobs
- **Strategic Rate Limiting**: Longer breaks every 5 shards to prevent blocking
- **Optimized Browser Options**: Disabled images, JavaScript, and other features for faster loading
- **Smart Error Handling**: Graceful fallback from API to DOM parsing

## 📈 Performance

### Typical Results
- **205+ unique jobs** from 5 shards (intern level)
- **100% API success rate** for most shards
- **0% false positives** for repost detection
- **Complete company names** extracted from URL paths
- **Direct apply URLs** when available

### Most Productive Shards
Based on testing:
1. **Intern + Full-time + On-site**: ~100 jobs
2. **Intern + Internship + On-site**: ~83 jobs
3. **Intern + Internship + Hybrid**: ~11 jobs

## 🔒 Privacy & Ethics

- Uses your own LinkedIn account session
- Respects LinkedIn's rate limits
- Only scrapes publicly available job data
- Includes strategic delays to avoid overwhelming servers
- Filters out job aggregators to focus on direct company postings

## 🚨 Important Notes

- **Login Required**: You must be logged into LinkedIn for the scraper to work
- **Rate Limiting**: The scraper includes built-in delays to prevent blocking
- **Session Management**: Cookies are saved locally and reused across runs
- **Data Quality**: API data is preferred over DOM data for accuracy

## 🐛 Troubleshooting

### Common Issues
1. **"No saved cookies found"**: Run `python login.py` first
2. **API timeouts**: Normal for some shards, DOM fallback will activate
3. **Browser crashes**: Rare with optimized settings, scraper will continue
4. **Empty results**: Some shard combinations may have no jobs

### Debug Mode
The scraper includes detailed logging to help identify issues:
- API success/failure messages
- DOM fallback activation
- Job counts per shard
- Rate limiting information

## 📝 License

This project is for educational and personal use. Please respect LinkedIn's terms of service and use responsibly. 