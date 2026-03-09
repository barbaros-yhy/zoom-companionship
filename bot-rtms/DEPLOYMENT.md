# RTMS Bot Deployment Guide

## Prerequisites

1. **Zoom Marketplace App:**
   - Go to https://marketplace.zoom.us/develop/create
   - Create Account-level OAuth app
   - Enable RTMS feature
   - Copy Client ID and Client Secret

2. **AWS Account:**
   - IAM role with Bedrock access for EC2 instance

3. **Domain Name:**
   - Point to EC2 instance IP
   - SSL certificate (Let's Encrypt)

## Local Development

```bash
cd bot-rtms
npm install
cp .env.example .env
# Edit .env with your credentials
npm run dev
```

## Production Deployment

### Step 1: Launch EC2 Instance

- Instance type: t3.small
- OS: Ubuntu 22.04
- Storage: 30GB gp3
- Security groups: 22 (SSH), 80 (HTTP), 443 (HTTPS), 8080 (Webhook), 8765 (WebSocket), 3001 (API)

### Step 2: Attach IAM Role

Create role with this policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel"
      ],
      "Resource": "arn:aws:bedrock:*:*:model/anthropic.claude-haiku-*"
    }
  ]
}
```

### Step 3: Run Setup Script

```bash
# SSH into EC2
ssh -i key.pem ubuntu@<ec2-ip>

# Set environment variables
export ZM_RTMS_CLIENT=your_client_id
export ZM_RTMS_SECRET=your_client_secret

# Download and run setup
curl -O https://raw.githubusercontent.com/YOUR_USERNAME/zoom-companionship/main/infra/setup-rtms.sh
chmod +x setup-rtms.sh
sudo -E ./setup-rtms.sh
```

### Step 4: Configure Nginx + SSL

```bash
sudo apt install nginx certbot python3-certbot-nginx

# Create nginx config
sudo nano /etc/nginx/sites-available/zoom-bot
```

Add this config:
```nginx
server {
    server_name your-domain.com;

    location /webhook {
        proxy_pass http://localhost:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/zoom-bot /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Get SSL certificate
sudo certbot --nginx -d your-domain.com
```

### Step 5: Configure Zoom Webhook

1. Go to your Zoom App settings
2. Add webhook URL: `https://your-domain.com/webhook`
3. Subscribe to event: `meeting.rtms_started`
4. Zoom will send validation challenge (bot handles automatically)

## Monitoring

```bash
# Check logs
cd /opt/zoom-companionship/docker
docker compose -f docker-compose.aws-cpu.yml logs -f

# Check status
docker compose -f docker-compose.aws-cpu.yml ps

# Restart services
docker compose -f docker-compose.aws-cpu.yml restart
```

## Troubleshooting

**Webhook validation fails:**
- Check nginx logs: `sudo tail -f /var/log/nginx/error.log`
- Verify SSL certificate is valid
- Check bot logs for validation challenge handling

**No transcripts appearing:**
- Verify RTMS client is joining: check bot logs
- Verify webhook is being triggered: check Zoom app logs
- Test WebSocket: `wscat -c ws://localhost:8765`

**Summary generation fails:**
- Check IAM role has Bedrock permissions
- Verify AWS_REGION is correct
- Check bot logs for Bedrock API errors
