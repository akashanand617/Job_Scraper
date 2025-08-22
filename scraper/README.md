# LinkedIn Job Scraper

A robust, automated LinkedIn job scraper that extracts AI/ML job listings using advanced search parameters and human-like browsing behavior.

## 🚀 Features

- **Intelligent Sharding**: Breaks down searches into 126 combinations (6 experience levels × 7 job types × 3 workplace types)
- **Human-like Behavior**: Simulates real user interactions (scrolling, hovering, random delays)
- **Cookie Management**: Persistent login sessions with automatic cookie refresh
- **Environment Variables**: Secure credential storage for automation
- **Comprehensive Data**: Extracts job ID, title, company, URL, posting date, and repost detection
- **Repost Detection**: Automatically identifies and marks reposted jobs
- **Blacklist Filtering**: Automatically filters out job aggregators and staffing agencies
- **Robust Error Handling**: Graceful handling of network issues and rate limiting

## 📁 Project Structure

```
scraper/
├── linkedin_scraper.py      # Main scraper script
├── login.py                 # Standalone login utility
├── requirements.txt         # Python dependencies
├── .env                     # Environment variables (create this)
├── .gitignore              # Git ignore rules
├── li_cookies.pkl          # Saved LinkedIn cookies
├── scraped_jobs.json       # Extracted job data (generated)
├── scraped_shards.json     # Search shard metadata (generated)
├── job_shard_mappings.json # Job-to-shard relationships (generated)
└── web_scraper.ipynb       # Original Jupyter notebook
```

## 🛠️ Installation

1. **Clone and navigate to the scraper directory:**
   ```bash
   cd scraper
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables:**
   ```bash
   # Create .env file
   echo "LINKEDIN_EMAIL=your_email@example.com" > .env
   echo "LINKEDIN_PASSWORD=your_password" >> .env
   ```

## 🔧 Configuration

### Search Parameters

The scraper searches for AI/ML jobs with these default parameters:

```python
BASE = {
    "keywords": '"AI" OR "Generative AI" OR "LLM" OR "Large Language Model" OR '
                '"Prompt Engineering" OR "Foundation Model" OR "Transformer" OR '
                '"RAG" OR "Reinforcement Learning With Human Feedback" OR "RLHF"',
    "location": "United States",
    "geoId": "103644278",      # US
    "f_TPR": "r604800",        # Past week
}
```

### Search Facets

The scraper creates 126 search combinations:

- **Experience Levels (6)**: Intern, Entry, Associate, Mid-Senior, Director, Executive
- **Job Types (7)**: Internship, Full-time, Contract, Temporary, Part-time, Volunteer, Other
- **Workplace Types (3)**: Remote, On-site, Hybrid

### Blacklisted Companies

Automatically filters out:
- Job aggregators (Indeed, ZipRecruiter, etc.)
- Staffing agencies (Robert Half, Aerotek, etc.)
- Recruiting platforms (Glassdoor, Monster, etc.)

## 🚀 Usage

### First Time Setup

1. **Login and save cookies:**
   ```bash
   python login.py
   ```
   - Uses credentials from `.env` file
   - Handles 2FA if required
   - Saves cookies to `li_cookies.pkl`

### Run the Scraper

```bash
python linkedin_scraper.py
```

**What happens:**
1. Loads saved cookies or prompts for login
2. Iterates through all 126 search combinations
3. Extracts job data with human-like behavior
4. Saves results to JSON files
5. Handles interruptions gracefully

### Output Files

- **`scraped_jobs.json`**: Individual job records
- **`scraped_shards.json`**: Search shard metadata
- **`job_shard_mappings.json`**: Job-to-shard relationships

## 🔍 Technical Details

### Core Functions

#### Authentication
- `login_and_save_cookies()`: Handles LinkedIn login and cookie storage
- `make_driver_with_cookies()`: Creates browser with saved session

#### Data Extraction
- `parse_cards_from_ul_html()`: Parses job cards from HTML
- `page_has_no_results()`: Detects empty search results
- `build_url()`: Constructs LinkedIn search URLs

#### Human-like Behavior
- `back_and_forth()`: Simulates natural scrolling
- `hover_on_job()`: Random job card hovering
- `human_scroll()`: Gradual page scrolling

#### Data Management
- `register_shard()`: Creates search shard records
- `add_job_links()`: Links jobs to search shards
- `save_results()`: Exports data to JSON files

### Search Sharding

The scraper uses a sophisticated sharding system:

```python
# 126 total combinations
EXP_CODES = ["1", "2", "3", "4", "5", "6"]           # Experience
JT_CODES  = ["I", "F", "C", "T", "P", "V", "O"]      # Job Type  
WT_CODES  = ["2", "1", "3"]                          # Workplace
```

Each combination gets a unique hash ID for tracking and deduplication.

### Data Structure

**Job Record:**
```json
{
  "job_id": "4281201823",
  "title": "AI Engineering Intern",
  "posted_dt": "2025-01-20T00:00:00+00:00",
  "company_name": "Tech Corp",
  "url": "https://linkedin.com/jobs/view/4281201823"
}
```

**Shard Record:**
```json
{
  "rank": 0,
  "params": {"f_E": "1", "f_JT": "I", "f_WT": "2"},
  "meta": {
    "experience_lbl": "intern",
    "job_type_lbl": "internship", 
    "workplace_lbl": "remote"
  }
}
```

## 🔒 Security & Privacy

- **Environment Variables**: Credentials stored in `.env` (not in code)
- **Cookie Management**: Secure cookie storage and validation
- **Rate Limiting**: Human-like delays prevent detection
- **Error Handling**: Graceful failure without data loss

## 🛡️ Anti-Detection Features

- **Undetected ChromeDriver**: Bypasses bot detection
- **Random User Agents**: Rotates browser fingerprints
- **Human-like Delays**: 5-8 second random intervals
- **Natural Scrolling**: Gradual, realistic page navigation
- **Random Interactions**: Hovering and back-and-forth scrolling

## 📊 Performance

- **Concurrent Processing**: Processes multiple search facets
- **Incremental Saving**: Saves progress on interruption
- **Deduplication**: Prevents duplicate job entries
- **Memory Efficient**: Streams data without loading everything

## 🚨 Troubleshooting

### Common Issues

1. **"Cookies expired"**
   - Run `python login.py` to refresh cookies
   - Check if 2FA is required

2. **"No job cards found"**
   - LinkedIn may have changed selectors
   - Check if search parameters are too restrictive

3. **Browser crashes**
   - Ensure Chrome is up to date
   - Check system memory availability

### Debug Mode

Add debug prints to see what's happening:
```python
# In linkedin_scraper.py, add:
print(f"Current URL: {driver.current_url}")
print(f"Page source length: {len(driver.page_source)}")
```

## 🔄 Automation

### Weekly Runs

Set up a cron job for automated scraping:
```bash
# Edit crontab
crontab -e

# Add weekly run (Sundays at 2 AM)
0 2 * * 0 cd /path/to/scraper && python linkedin_scraper.py
```

### Environment Variables

For automation, set these in your system:
```bash
export LINKEDIN_EMAIL="your_email@example.com"
export LINKEDIN_PASSWORD="your_password"
```

## 📈 Data Analysis

The scraper outputs structured data perfect for analysis:

- **Trend Analysis**: Track job posting patterns over time
- **Company Analysis**: Identify top AI/ML employers
- **Geographic Analysis**: Remote vs on-site job distribution
- **Skill Analysis**: Extract required skills from job titles

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is for educational and research purposes. Please respect LinkedIn's Terms of Service and use responsibly.

## ⚠️ Disclaimer

This tool is for educational purposes only. Users are responsible for complying with LinkedIn's Terms of Service and applicable laws. The authors are not responsible for any misuse of this software. 