# USDT Tracker

A Flask-based portfolio tracker for USDT trading with live price feeds, P/L calculator, and multi-currency support.

## Quick Start (Local)

```bash
# SQLite (no external dependencies)
python app.py
# Visit http://127.0.0.1:5000 | Login: admin / pass123

# MySQL
set DB_TYPE=mysql
set MYSQL_HOST=localhost
set MYSQL_USER=root
set MYSQL_PASSWORD=your_password
set MYSQL_DB=usdt_tracker
python app.py
```

## Public Deployment

Choose your deployment method:

| Platform | Difficulty | HTTPS | Monthly Cost |
|----------|-----------|-------|-------------|
| Railway | Easy | Automatic | Free-$5 |
| Render | Easy | Automatic | Free-$7 |
| DigitalOcean + Docker | Medium | Manual (Let's Encrypt) | $5 |
| AWS EC2 + Docker | Medium | Manual (Let's Encrypt) | $3.50 |
| Self-hosted VPS | Hard | Manual | $5 |

See [DEPLOY.md](./DEPLOY.md) for detailed instructions for each platform.

### Railway (Easiest)
```bash
# 1. Push to GitHub
git init && git add -A && git commit -m "Initial commit"
git remote add origin https://github.com/yourname/usdt-tracker.git
git push -u origin main

# 2. Go to railway.app -> New Project -> Import from GitHub
# 3. Add MySQL plugin
# 4. Set SECRET_KEY environment variable
# 5. Deploy
```

### VPS with Docker
```bash
# On your server (Ubuntu 22.04+)
curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh
git clone https://github.com/yourname/usdt-tracker.git
cd usdt-tracker
docker-compose -f docker-compose.prod.yml up -d
```

## Files

| File | Purpose |
|------|---------|
| `app.py` | Main Flask application |
| `config.py` | Config with environment variable support |
| `Dockerfile` | Container image definition |
| `docker-compose.yml` | Local development (port 5000) |
| `docker-compose.prod.yml` | Production (nginx + MySQL + app) |
| `nginx/nginx.conf` | Production nginx config with HTTPS |
| `schema.sql` | MySQL database initialization script |
| `Procfile` | For PaaS platforms (gunicorn) |
| `Procfile.windows` | For Windows (waitress) |
| `DEPLOY.md` | Detailed deployment instructions |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | `dev-secret-key-change-in-production` | Flask session secret (**change in production**) |
| `DB_TYPE` | `sqlite` | Database: `sqlite` or `mysql` |
| `MYSQL_HOST` | `localhost` | MySQL host |
| `MYSQL_USER` | `root` | MySQL user |
| `MYSQL_PASSWORD` | | MySQL password |
| `MYSQL_DB` | `usdt_tracker` | MySQL database name |
| `COIN_API_URL` | `https://api.coingecko.com/api/v3` | CoinGecko API URL |
| `FLASK_DEBUG` | `False` | Enable Flask debug mode |
| `PORT` | `5000` | Server port |
| `HOST` | `0.0.0.0` | Server bind host |

## Default Login

- Username: `admin`
- Password: `pass123`

**Important**: Change these credentials in production via the profile page.
