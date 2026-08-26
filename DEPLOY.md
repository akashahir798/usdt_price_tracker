# Quick Public Deployment Guide

## Option 1: PaaS - Railway (Free tier available, HTTPS automatic)

```bash
# 1. Push to GitHub
git init
git add -A
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/yourusername/usdt-tracker.git
git push -u origin main

# 2. Go to https://railway.app -> New Project -> Deploy from GitHub
# 3. Add MySQL plugin (Railway > New > Plugin > MySQL)
# 4. Set environment variables:
#    SECRET_KEY=<openssl rand -hex 32>
#    FLASK_DEBUG=False
# 5. Done - app gets HTTPS automatically
```

## Option 2: PaaS - Render (Free tier available)

```bash
# 1. Push to GitHub (same as above)
# 2. Go to https://render.com -> New Web Service -> Connect GitHub
# 3. Select your repo
# 4. Set build command: docker build -t usdt-tracker .
# 5. Set start command: docker run -p 5000:5000 usdt-tracker
# 6. Add MySQL via Render PostgreSQL plugin or external MySQL
# 7. HTTPS automatic via Let's Encrypt
```

## Option 3: VPS with Docker (DigitalOcean, AWS EC2)

```bash
# 1. Get a VPS (Ubuntu 22.04, $5/mo recommended)
# 2. SSH in and install Docker:
curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh

# 3. Clone your repo:
git clone https://github.com/yourusername/usdt-tracker.git
cd usdt-tracker

# 4. Set production env vars:
set -a
source .env.production
set +a

# 5. Run with Docker Compose:
docker-compose -f docker-compose.yml up -d

# 6. Set up SSL with Let's Encrypt:
docker run -it --rm --entrypoint="" nginx:alpine sh
# (or use the nginx reverse proxy setup)
```

## Option 4: VPS with nginx + HTTPS (Manual, full control)

```bash
# 1. Get a VPS and domain name
# 2. Install nginx, Python 3.11+, certbot:
sudo apt update
sudo apt install nginx python3-pip python3-venv certbot python3-certbot-nginx -y

# 3. Deploy app:
git clone https://github.com/yourusername/usdt-tracker.git
cd usdt-tracker
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install gunicorn

# 4. Set env vars:
export DB_TYPE=mysql
export MYSQL_HOST=your-db-host
export MYSQL_USER=your-user
export MYSQL_PASSWORD=your-password
export MYSQL_DB=usdt_tracker
export SECRET_KEY=$(openssl rand -hex 32)

# 5. Create systemd service:
sudo tee /etc/systemd/system/usdt-tracker.service > /dev/null << 'EOF'
[Unit]
Description=USDT Tracker App
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/home/ubuntu/usdt-tracker
Environment=DB_TYPE=mysql
Environment=MYSQL_HOST=your-db-host
Environment=MYSQL_USER=your-user
Environment=MYSQL_PASSWORD=your-password
Environment=MYSQL_DB=usdt_tracker
Environment=SECRET_KEY=your-generated-secret
ExecStart=/home/ubuntu/usdt-tracker/venv/bin/gunicorn -w 4 -b 127.0.0.1:8000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl start usdt-tracker
sudo systemctl enable usdt-tracker

# 6. Configure nginx:
sudo tee /etc/nginx/sites-available/usdt-tracker > /dev/null << 'EOF'
server {
    listen 80;
    server_name your-domain.com;
    location / {
        return 301 https://$host$request_uri;
    }
}
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    location /static/ {
        alias /home/ubuntu/usdt-tracker/static/;
        expires 30d;
    }
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/usdt-tracker /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx

# 7. Get SSL certificate:
sudo certbot --nginx -d your-domain.com
```

## After Deployment

1. Visit `https://your-domain.com`
2. Login: `admin` / `pass123`
3. Change your password via Profile page
4. Add transactions
5. Set your preferred currency in the navbar dropdown
