# GitHub Actions Setup for LinkedIn Cookie Refresh

This guide will help you set up automated LinkedIn cookie refresh using GitHub Actions.

## 🚀 Quick Setup

### Step 1: Create GitHub Repository
1. Go to [GitHub.com](https://github.com) and create a new repository
2. Name it something like `linkedin-job-scraper` or `linkedin-cookie-refresh`
3. Make it **private** (to keep your credentials secure)

### Step 2: Push Your Code
```bash
# Initialize git (if not already done)
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit with GitHub Actions workflow"

# Add your GitHub repository as remote
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git

# Push to GitHub
git push -u origin main
```

### Step 3: Add Secrets to GitHub
Go to your repository → Settings → Secrets and variables → Actions

Add these secrets:

| Secret Name | Value | Description |
|-------------|-------|-------------|
| `LINKEDIN_EMAIL` | your-email@example.com | Your LinkedIn email |
| `LINKEDIN_PASSWORD` | your-password | Your LinkedIn password |
| `AWS_ACCESS_KEY_ID` | your-aws-access-key | Your AWS access key |
| `AWS_SECRET_ACCESS_KEY` | your-aws-secret-key | Your AWS secret key |

### Step 4: Test the Workflow
1. Go to your repository → Actions tab
2. Click on "Refresh LinkedIn Cookies" workflow
3. Click "Run workflow" to test it manually
4. Watch it run and check the logs

## ⏰ Schedule

The workflow runs:
- **Automatically**: Every Sunday at 9 AM UTC
- **Manually**: Click "Run workflow" anytime

## 🔧 Customization

### Change Schedule
Edit `.github/workflows/refresh-cookies.yml`:
```yaml
schedule:
  - cron: '0 9 * * 0'  # Sunday 9 AM UTC
  # - cron: '0 14 * * 0'  # Sunday 2 PM UTC
  # - cron: '0 9 * * 1'   # Monday 9 AM UTC
```

### Change Timezone
The workflow runs in UTC. To convert to your timezone:
- **EST**: UTC-5 (9 AM UTC = 4 AM EST)
- **PST**: UTC-8 (9 AM UTC = 1 AM PST)
- **CET**: UTC+1 (9 AM UTC = 10 AM CET)

## 📊 Monitoring

### Check Status
1. Go to your repository → Actions tab
2. See the latest run status
3. Click on a run to see detailed logs

### Success Indicators
- ✅ Green checkmark = Success
- ❌ Red X = Failed
- 🟡 Yellow circle = Running

## 🛠️ Troubleshooting

### Common Issues

**1. Chrome Installation Failed**
- The workflow will retry automatically
- Check the logs for specific error messages

**2. LinkedIn Login Failed**
- Verify your credentials in GitHub Secrets
- Check if LinkedIn requires 2FA (may need app password)

**3. AWS Upload Failed**
- Verify AWS credentials in GitHub Secrets
- Check S3 bucket permissions

### Manual Refresh
If the automated refresh fails:
1. Go to Actions tab
2. Click "Run workflow"
3. Select "Run workflow" to trigger manually

## 🔒 Security

### Repository Settings
- Keep your repository **private**
- Never commit credentials to code
- Use GitHub Secrets for all sensitive data

### Credentials
- Use app-specific passwords if you have 2FA enabled
- Rotate credentials regularly
- Monitor for any unauthorized access

## 📈 Benefits

✅ **Completely Free** - No cost for GitHub Actions
✅ **Always Available** - Runs on GitHub's servers
✅ **No Laptop Needed** - Works even when your computer is off
✅ **Automatic** - Runs every week without intervention
✅ **Reliable** - GitHub's infrastructure is highly available
✅ **Secure** - Credentials stored in GitHub Secrets

## 🎯 Next Steps

1. Set up the repository and secrets
2. Test the workflow manually
3. Monitor the first few automatic runs
4. Adjust schedule if needed
5. Enjoy automated cookie refresh!

## 📞 Support

If you encounter issues:
1. Check the Actions logs for error messages
2. Verify all secrets are set correctly
3. Test the script locally first
4. Check LinkedIn and AWS credentials
