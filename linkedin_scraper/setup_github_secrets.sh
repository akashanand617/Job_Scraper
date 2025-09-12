#!/bin/bash

# Script to set GitHub secrets from .env file
# Make sure to fill in your real credentials in .env first!

echo "🔐 Setting up GitHub secrets from .env file..."
echo ""

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found"
    echo "Please create .env file with your credentials first"
    exit 1
fi

# Load environment variables from .env
export $(cat .env | grep -v '^#' | xargs)

# Check if credentials are set
if [ -z "$LINKEDIN_EMAIL" ] || [ "$LINKEDIN_EMAIL" = "your-email@example.com" ]; then
    echo "❌ Error: Please set your real LinkedIn email in .env file"
    echo "Edit .env and replace 'your-email@example.com' with your actual email"
    exit 1
fi

if [ -z "$LINKEDIN_PASSWORD" ] || [ "$LINKEDIN_PASSWORD" = "your-password" ]; then
    echo "❌ Error: Please set your real LinkedIn password in .env file"
    echo "Edit .env and replace 'your-password' with your actual password"
    exit 1
fi

echo "✅ Found credentials in .env file"
echo "📧 Email: $LINKEDIN_EMAIL"
echo "🪣 Bucket: ${JOBS_BUCKET:-linkedin-job-scraper-dev-jobs}"
echo ""

# Set GitHub secrets
echo "🔧 Setting GitHub secrets..."

echo "Setting LINKEDIN_EMAIL..."
gh secret set LINKEDIN_EMAIL --body "$LINKEDIN_EMAIL"

echo "Setting LINKEDIN_PASSWORD..."
gh secret set LINKEDIN_PASSWORD --body "$LINKEDIN_PASSWORD"

echo "Setting AWS_ACCESS_KEY_ID..."
gh secret set AWS_ACCESS_KEY_ID --body "$AWS_ACCESS_KEY_ID"

echo "Setting AWS_SECRET_ACCESS_KEY..."
gh secret set AWS_SECRET_ACCESS_KEY --body "$AWS_SECRET_ACCESS_KEY"

echo ""
echo "✅ All secrets set successfully!"
echo ""
echo "🎯 Next steps:"
echo "1. Go to your repository: https://github.com/akashanand617/Job_Scraper"
echo "2. Click on 'Actions' tab"
echo "3. Click on 'Refresh LinkedIn Cookies' workflow"
echo "4. Click 'Run workflow' to test it"
echo ""
echo "📅 The workflow will run automatically every Sunday at 9 AM UTC"
