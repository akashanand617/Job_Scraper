# LinkedIn Cookie Refresh - GitHub Actions Solution

Automated LinkedIn cookie refresh using GitHub Actions. Runs on GitHub's servers - no laptop needed!

## 🚀 Quick Start

### Option 1: GitHub Actions (Recommended)
1. **Create GitHub repository** (private)
2. **Push your code** to GitHub
3. **Add secrets** (LinkedIn credentials, AWS keys)
4. **Done!** Runs automatically every Sunday

See `GITHUB_ACTIONS_SETUP.md` for detailed instructions.

### Option 2: Local Execution
```bash
# Set up environment variables
cp env.example .env
nano .env  # Add your credentials

# Run cookie refresh
python3 refresh_cookies.py
```

## 📋 Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `LINKEDIN_EMAIL` | LinkedIn login email | Yes |
| `LINKEDIN_PASSWORD` | LinkedIn login password | Yes |
| `JOBS_BUCKET` | S3 bucket for storing cookies | No (defaults to linkedin-job-scraper-dev-jobs) |
| `AWS_ACCESS_KEY_ID` | AWS access key | Yes |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key | Yes |
| `AWS_DEFAULT_REGION` | AWS region | No (defaults to us-east-1) |

## 🔄 How it works

1. **Logs into LinkedIn** using your credentials
2. **Saves cookies** locally using existing `src/login.py` logic
3. **Uploads cookies** to S3 at `s3://bucket/cookies/li_cookies.pkl`
4. **Uploads metadata** to track refresh status
5. **Lambda automatically** downloads fresh cookies from S3

## 📊 Monitoring

Check cookie status in S3:
```bash
aws s3 ls s3://linkedin-job-scraper-dev-jobs/cookies/
```

## 🕐 Scheduling

### Option 1: Cron (Linux/Mac)
```bash
# Add to crontab (runs every Sunday at 2 AM)
0 2 * * 0 cd /path/to/linkedin_scraper && docker-compose up cookie-refresh
```

### Option 2: GitHub Actions
```yaml
name: Refresh Cookies
on:
  schedule:
    - cron: '0 2 * * 0'  # Every Sunday at 2 AM
  workflow_dispatch:

jobs:
  refresh:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Refresh cookies
        run: docker-compose up --build cookie-refresh
        env:
          LINKEDIN_EMAIL: ${{ secrets.LINKEDIN_EMAIL }}
          LINKEDIN_PASSWORD: ${{ secrets.LINKEDIN_PASSWORD }}
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
```

## 🛠️ Troubleshooting

### Common Issues
- **Permission denied**: Check AWS credentials and S3 permissions
- **Login failed**: Verify LinkedIn credentials
- **Chrome not found**: Docker build should handle this automatically

### Debug Mode
```bash
# Run with debug output
docker-compose up --build cookie-refresh
```

## 💡 Tips

- **Run weekly**: LinkedIn cookies typically last 7-30 days
- **Monitor S3**: Check that cookies are being uploaded
- **Test locally**: Run `python3 refresh_cookies.py` to test without Docker
- **No redeployment**: Lambda automatically uses fresh cookies from S3
