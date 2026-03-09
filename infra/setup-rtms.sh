#!/bin/bash
# infra/setup-rtms.sh
# EC2 setup script for RTMS bot (CPU-only, t3.small)

set -e

echo "=== Zoom RTMS Bot Setup ==="

# Update system
apt-get update
apt-get upgrade -y

# Install Docker
apt-get install -y apt-transport-https ca-certificates curl software-properties-common
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add -
add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Start Docker
systemctl start docker
systemctl enable docker

# Clone repository
cd /opt
if [ -d "zoom-companionship" ]; then
    cd zoom-companionship
    git pull
else
    git clone https://github.com/YOUR_USERNAME/zoom-companionship.git
    cd zoom-companionship
fi

# Create .env file (restricted permissions)
cat > .env << EOF
ZM_RTMS_CLIENT=${ZM_RTMS_CLIENT}
ZM_RTMS_SECRET=${ZM_RTMS_SECRET}
AWS_REGION=eu-central-1
EOF
chmod 600 .env

# Build and start services
cd docker
docker compose -f docker-compose.aws-cpu.yml up -d

echo "=== Setup Complete ==="
echo "Services:"
echo "  - Bot webhook: http://localhost:8080/webhook"
echo "  - Bot WebSocket: ws://localhost:8765"
echo "  - API: http://localhost:3001"
echo ""
echo "Check logs:"
echo "  docker compose -f docker-compose.aws-cpu.yml logs -f"
