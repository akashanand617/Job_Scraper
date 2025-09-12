#!/usr/bin/env python3
"""
Simple LinkedIn Cookie Refresh
Uses existing login logic and uploads to S3
"""

import os
import boto3
import json
from datetime import datetime, timezone
from src.login import login_and_save_cookies

def main():
    print("🍪 LinkedIn Cookie Refresh")
    print("=" * 30)
    
    # Get credentials from environment
    email = os.getenv('LINKEDIN_EMAIL')
    password = os.getenv('LINKEDIN_PASSWORD')
    bucket = os.getenv('JOBS_BUCKET', 'linkedin-job-scraper-dev-jobs')
    
    if not email or not password:
        print("❌ Error: Set LINKEDIN_EMAIL and LINKEDIN_PASSWORD environment variables")
        return False
    
    try:
        print("🔐 Logging into LinkedIn...")
        login_and_save_cookies(email, password)
        
        print("📦 Uploading cookies to S3...")
        s3_client = boto3.client('s3')
        s3_key = "cookies/li_cookies.pkl"
        
        s3_client.upload_file('li_cookies.pkl', bucket, s3_key)
        print(f"✅ Cookies uploaded to s3://{bucket}/{s3_key}")
        
        # Upload metadata
        metadata = {
            "refreshed_at": datetime.now(timezone.utc).isoformat(),
            "bucket": bucket,
            "key": s3_key,
            "status": "success"
        }
        
        metadata_key = "cookies/li_cookies_metadata.json"
        s3_client.put_object(
            Bucket=bucket,
            Key=metadata_key,
            Body=json.dumps(metadata, indent=2),
            ContentType='application/json'
        )
        
        print("✅ Cookie refresh completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
