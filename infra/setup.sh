#!/bin/bash
# infra/setup.sh
# Bootstrap script for EC2 g4dn.xlarge (Ubuntu 22.04 + NVIDIA GPU)
# Run once as root on a fresh instance.

set -euo pipefail

echo "=== Zoom Companion Bot EC2 Setup ==="

# 1. System updates
apt-get update -q
apt-get install -y git curl build-essential

# 2. NVIDIA drivers (required for Speaches GPU)
apt-get install -y nvidia-driver-525
echo "Reboot may be required after NVIDIA driver install."

# 3. Docker
curl -fsSL https://get.docker.com | sh
usermod -aG docker ubuntu

# 4. NVIDIA Container Toolkit (allows Docker to use GPU)
distribution=$(. /etc/os-release; echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | apt-key add -
curl -s -L "https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list" \
  | tee /etc/apt/sources.list.d/nvidia-docker.list
apt-get update -q
apt-get install -y nvidia-container-toolkit
systemctl restart docker

# 5. PulseAudio virtual sink (captures Zoom web audio)
apt-get install -y pulseaudio pulseaudio-utils
# Start PulseAudio daemon
pulseaudio --start --daemonize=true || true
# Create virtual sink that Zoom audio routes through
pactl load-module module-null-sink sink_name=virtual_sink \
  sink_properties=device.description=VirtualSink || true
pactl set-default-sink virtual_sink || true

# 6. Clone and configure
cd /opt
git clone https://github.com/barbaros-yhy/zoom-companionship.git
cd zoom-companionship

# Copy and fill in env file
cp .env.example .env
echo ""
echo "IMPORTANT: Edit /opt/zoom-companionship/.env with your API keys before starting."
echo "  ANTHROPIC_API_KEY=sk-ant-..."
echo "  AWS_S3_BUCKET=your-bucket"
echo ""

# 7. Start services
cd docker
docker compose up -d

echo "=== Setup complete. Bot services starting... ==="
echo "Check status: docker compose ps"
echo "Check logs:   docker compose logs -f"
