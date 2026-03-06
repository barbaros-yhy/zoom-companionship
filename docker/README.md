# Docker Setup

## Speaches (STT Server)

Speaches runs faster-whisper large-v3-turbo for real-time transcription.

**Requirements:** NVIDIA GPU + nvidia-container-toolkit on the host.

**Start:**
```bash
docker compose up speaches -d
```

**Check logs:**
```bash
docker compose logs -f speaches
```

**Test transcription:**
```bash
curl -X POST http://localhost:8000/v1/audio/transcriptions \
  -F "file=@test.wav" \
  -F "model=Systran/faster-whisper-large-v3-turbo"
```

**Without GPU (CPU-only for dev):**
Change image to `ghcr.io/speaches-ai/speaches:latest` and remove the `deploy.resources` block.
