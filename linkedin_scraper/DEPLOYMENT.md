# LinkedIn Scraper API - Render Deployment Guide

## 🚀 Quick Deploy to Render

### 1. Push to GitHub
```bash
git init
git add .
git commit -m "Initial commit: LinkedIn Scraper API"
git branch -M main
git remote add origin https://github.com/yourusername/linkedin-scraper-api.git
git push -u origin main
```

### 2. Deploy to Render
1. Go to [render.com](https://render.com)
2. Sign up/Login with GitHub
3. Click "New +" → "Web Service"
4. Connect your GitHub repository
5. Configure:
   - **Name**: `linkedin-scraper-api`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python simple_api.py`
   - **Plan**: Free

### 3. Environment Variables (Optional)
Add these in Render dashboard if needed:
- `PYTHON_VERSION`: `3.11.0`

## 📡 API Endpoints

Once deployed, your API will be available at:
`https://your-app-name.onrender.com`

### Available Endpoints:
- `GET /` - API info and endpoints
- `GET /health` - Health check
- `POST /scrape` - Start scraping job
- `GET /scrape/{job_id}` - Check job status
- `GET /jobs` - List all jobs
- `GET /latest` - Get latest scraped jobs
- `POST /filter` - Filter jobs by criteria
- `GET /filters` - Get available filter options
- `GET /docs` - Interactive API documentation

## 🔧 Local Development

### Setup:
```bash
pip install -r requirements.txt
python simple_api.py
```

### Test:
```bash
curl http://localhost:8000/health
```

## 📊 Usage Examples

### Start Scraping:
```bash
curl -X POST "https://your-app.onrender.com/scrape" \
  -H "Content-Type: application/json" \
  -d '{"max_shards": 5, "mode": "daily"}'
```

### Filter Jobs:
```bash
curl -X POST "https://your-app.onrender.com/filter" \
  -H "Content-Type: application/json" \
  -d '{"job_type": "internship", "limit": 10}'
```

### Get Latest Jobs:
```bash
curl "https://your-app.onrender.com/latest"
```

## ⚠️ Important Notes

- **Personal Use Only**: This API is for personal job searching
- **Rate Limiting**: Built-in protection against abuse
- **Free Tier**: 750 hours/month on Render free tier
- **Auto-sleep**: App sleeps after 15 minutes of inactivity
- **Cold Start**: 10-30 second delay when waking up

## 🛠️ Troubleshooting

### Common Issues:
1. **Cold Start Delay**: Normal for free tier, wait 10-30 seconds
2. **Build Failures**: Check Python version compatibility
3. **Import Errors**: Ensure all dependencies in requirements.txt
4. **Memory Issues**: Free tier has 512MB limit

### Logs:
Check Render dashboard → Your service → Logs for debugging

## 🔄 Updates

To update your deployed API:
```bash
git add .
git commit -m "Update API"
git push origin main
```
Render will automatically redeploy.
