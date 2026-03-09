#!/bin/bash
# infra/setup-cpu.sh
# Bootstrap script for AWS EC2 CPU-only deployment (t3.medium recommended)
# Run once as root on a fresh Ubuntu 22.04 instance.

set -euo pipefail

echo "=== Zoom Companion Bot EC2 Setup (CPU-only) ==="

# 1. System updates
apt-get update -q
apt-get install -y git curl build-essential

# 2. Docker
curl -fsSL https://get.docker.com | sh
usermod -aG docker ubuntu

# 3. PulseAudio virtual sink (captures Zoom web audio)
apt-get install -y pulseaudio pulseaudio-utils
# Start PulseAudio daemon as ubuntu user
su - ubuntu -c "pulseaudio --start --daemonize=true || true"
# Create virtual sink that Zoom audio routes through
su - ubuntu -c "pactl load-module module-null-sink sink_name=virtual_sink sink_properties=device.description=VirtualSink || true"
su - ubuntu -c "pactl set-default-sink virtual_sink || true"

# 4. Clone and configure
cd /opt
git clone https://github.com/barbaros-yhy/zoom-companionship.git
cd zoom-companionship
chown -R ubuntu:ubuntu /opt/zoom-companionship

# Copy and fill in env file
cp .env.example .env
echo ""
echo "IMPORTANT: Edit /opt/zoom-companionship/.env with your configuration:"
echo "  AWS_REGION=eu-central-1"
echo "  AWS_S3_BUCKET=your-bucket (optional)"
echo ""
echo "AWS credentials will be automatically provided by EC2 instance IAM role."
echo ""

# 5. Start services (CPU-only version)
cd docker
su - ubuntu -c "cd /opt/zoom-companionship/docker && docker compose -f docker-compose.aws-cpu.yml up -d"

echo "=== Setup complete. Bot services starting... ==="
echo "Check status: cd /opt/zoom-companionship/docker && docker compose -f docker-compose.aws-cpu.yml ps"
echo "Check logs:   cd /opt/zoom-companionship/docker && docker compose -f docker-compose.aws-cpu.yml logs -f"
echo ""
echo "Recommended EC2 instance type: t3.medium (2 vCPU, 4 GB RAM)"
echo "Note: CPU transcription is slower than GPU. Consider faster-whisper-tiny for better performance."
