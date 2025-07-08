# Deployment Guide for Binance Tracker V2

## Deploying to Render.com (Recommended - Free)

### Prerequisites
1. GitHub account
2. Render.com account (free)

### Step 1: Prepare Your Repository

1. Create a new GitHub repository
2. Push your code:
```bash
cd /home/bernard-gitau-ndegwa/gradual_grow/binance_tracker_v2
git init
git add .
git commit -m "Initial commit - Binance Tracker V2 with scoring system"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/binance-tracker-v2.git
git push -u origin main
```

### Step 2: Deploy on Render

1. Go to [Render.com](https://render.com) and sign up/login
2. Click "New +" → "Web Service"
3. Connect your GitHub account
4. Select your `binance-tracker-v2` repository
5. Fill in the details:
   - **Name**: binance-tracker-v2
   - **Environment**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn web.app:app`
6. Click "Create Web Service"

### Step 3: Wait for Deployment

- First deployment takes 5-10 minutes
- Your app will be available at: `https://binance-tracker-v2.onrender.com`

## Important Notes

### Free Tier Limitations
- **Spins down after 15 minutes of inactivity**
- Takes ~30 seconds to wake up on first request
- 750 hours/month free (enough for 24/7 if single app)
- SQLite database resets on each deployment

### Production Considerations

#### Database Persistence
Current SQLite implementation will lose data on redeploy. For production:

1. **Option A**: Use Render's PostgreSQL (free tier available)
2. **Option B**: Use external database service
3. **Option C**: Implement data export/backup features

#### Performance Optimization
```python
# Add to config.py for production
CACHE_TTL = 300  # 5 minutes cache
UPDATE_INTERVAL = 60  # Update every minute
CLEANUP_INTERVAL = 3600  # Clean old data hourly
```

#### Monitoring
- Render provides basic metrics in dashboard
- Add health check endpoint:

```python
@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})
```

## Alternative Free Hosting Options

### 1. Railway.app
```bash
# Install Railway CLI
npm install -g @railway/cli

# Deploy
railway login
railway init
railway up
```

### 2. Fly.io
```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Deploy
fly launch
fly deploy
```

### 3. Heroku (Free tier discontinued, but student pack available)

## Environment Variables

For production, set these in Render dashboard:

```
FLASK_ENV=production
LOG_LEVEL=INFO
```

## Security Considerations

1. **No API Keys Required** - Uses public Binance API
2. **Read-Only** - No trading functionality
3. **Rate Limiting** - Built-in to respect Binance limits

## Monitoring Your Deployment

1. **Render Dashboard**: Shows logs, metrics, deploys
2. **Application Logs**: Available in Render dashboard
3. **Uptime Monitoring**: Use free service like UptimeRobot

## Updating Your App

```bash
git add .
git commit -m "Update description"
git push origin main
```

Render will automatically redeploy (if autoDeploy is enabled).

## Troubleshooting

### App Won't Start
- Check logs in Render dashboard
- Verify all dependencies in requirements.txt
- Ensure gunicorn is installed

### Slow Performance
- First request after sleep takes ~30s (normal)
- Consider implementing caching
- Reduce API call frequency

### Database Issues
- SQLite file may be deleted on redeploy
- Consider PostgreSQL for persistence

## Cost Optimization

To stay within free tier:
1. Single web service only
2. Don't add background workers
3. Use external free database if needed
4. Monitor usage in Render dashboard

## Support

- Render Docs: https://render.com/docs
- Check application logs for errors
- GitHub issues for app-specific problems