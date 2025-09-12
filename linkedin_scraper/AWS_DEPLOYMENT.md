# AWS Lambda Deployment Guide

## Prerequisites

1. **AWS Account** with free tier access
2. **AWS CLI** installed and configured
3. **Node.js** (for Serverless Framework)
4. **Serverless Framework** installed

## Installation Steps

### 1. Install Serverless Framework
```bash
npm install -g serverless
```

### 2. Configure AWS CLI
```bash
aws configure
# Enter your AWS Access Key ID
# Enter your AWS Secret Access Key
# Enter your default region (e.g., us-east-1)
# Enter your default output format (json)
```

### 3. Set Environment Variables
```bash
export LINKEDIN_EMAIL="your-email@example.com"
export LINKEDIN_PASSWORD="your-password"
```

## Deployment Commands

### Deploy to AWS Lambda
```bash
cd linkedin_scraper
serverless deploy
```

### Deploy to specific stage
```bash
serverless deploy --stage prod
```

### Remove deployment
```bash
serverless remove
```

## API Endpoints

After deployment, you'll get a URL like:
`https://abc123.execute-api.us-east-1.amazonaws.com/dev`

### Available Endpoints:
- `GET /` - API info
- `GET /health` - Health check
- `POST /scrape` - Start scraping job
- `GET /scrape/{job_id}` - Check job status
- `GET /jobs` - Get all scraped jobs
- `GET /batch-info` - Batch processing info
- `POST /filter` - Filter jobs
- `GET /filters` - Available filters

## Usage Examples

### Start a scraping job
```bash
curl -X POST https://your-api-url.amazonaws.com/dev/scrape \
  -H "Content-Type: application/json" \
  -d '{"keywords": "AI OR Machine Learning", "batch_number": 1, "batch_size": 18}'
```

### Check job status
```bash
curl -X GET https://your-api-url.amazonaws.com/dev/scrape/{job_id}
```

### Get all jobs
```bash
curl -X GET https://your-api-url.amazonaws.com/dev/jobs
```

## Batch Processing for Lambda

Since Lambda has a 15-minute timeout, use batch processing:

### Batch 1 (Shards 1-18)
```bash
curl -X POST https://your-api-url.amazonaws.com/dev/scrape \
  -H "Content-Type: application/json" \
  -d '{"batch_number": 1, "batch_size": 18}'
```

### Batch 2 (Shards 19-36)
```bash
curl -X POST https://your-api-url.amazonaws.com/dev/scrape \
  -H "Content-Type: application/json" \
  -d '{"batch_number": 2, "batch_size": 18}'
```

Continue for all 7 batches to get all 126 shards.

## Cost Estimation (AWS Free Tier)

- **Lambda**: 1M free requests/month
- **API Gateway**: 1M free API calls/month
- **S3**: 5GB free storage
- **CloudWatch**: 5GB free logs

## Monitoring

- **CloudWatch Logs**: View function logs
- **CloudWatch Metrics**: Monitor performance
- **X-Ray**: Trace requests (optional)

## Troubleshooting

### Common Issues:
1. **Timeout**: Use batch processing
2. **Memory**: Increase memory in serverless.yml
3. **Dependencies**: Check requirements.txt
4. **Environment Variables**: Verify LINKEDIN_EMAIL/PASSWORD

### Logs:
```bash
serverless logs -f api
```

## Security Notes

- Environment variables are encrypted
- S3 bucket is private by default
- IAM roles follow least privilege principle
- CORS is enabled for web access
