#!/bin/bash
# Audio Debug Script - EC2'de bot çalışırken çalıştır

echo "=== ZOOM AUDIO DEBUG DIAGNOSTICS ==="
echo ""

# 1. PulseAudio Virtual Sink Durumu
echo "1. PulseAudio Virtual Sink:"
pactl list sinks short | grep virtual || echo "  ❌ virtual_sink bulunamadı!"
echo ""

# 2. Chromium Sink-Inputs (Browser Audio Streams)
echo "2. Chromium Audio Streams:"
pactl list sink-inputs short
echo ""
echo "  Detaylı Stream Bilgisi:"
pactl list sink-inputs | grep -A 30 -i "chromium\|chrome" | grep -E "Sink:|Volume:|Mute:|State:"
echo ""

# 3. PulseAudio Capture Test (5 saniye)
echo "3. PulseAudio Capture Test (5 saniye)..."
timeout 5 parec --device=virtual_sink.monitor \
  --format=s16le --rate=16000 --channels=1 \
  /tmp/test_capture.raw 2>/dev/null

CAPTURE_SIZE=$(stat -f%z /tmp/test_capture.raw 2>/dev/null || stat -c%s /tmp/test_capture.raw 2>/dev/null)
echo "  Capture file size: $CAPTURE_SIZE bytes"

if [ "$CAPTURE_SIZE" -eq 0 ]; then
    echo "  ❌ PROBLEM: PulseAudio capture tamamen boş!"
elif [ "$CAPTURE_SIZE" -lt 10000 ]; then
    echo "  ⚠️  WARNING: Capture çok az veri aldı (silence olabilir)"
else
    echo "  ✅ PulseAudio capture çalışıyor"
fi
echo ""

# 4. Browser Process Check
echo "4. Browser Processes:"
ps aux | grep -E "chromium|chrome" | grep -v grep | head -5
echo ""

# 5. Display Environment
echo "5. Display Environment:"
echo "  DISPLAY=$DISPLAY"
echo "  PULSE_SERVER=$PULSE_SERVER"
echo "  PULSE_SINK=$PULSE_SINK"
echo ""

# 6. Sonuç Özeti
echo "=== SUMMARY ==="
if [ "$CAPTURE_SIZE" -eq 0 ]; then
    echo "🔴 CRITICAL: PulseAudio capture BAŞARISIZ"
    echo "   → Çözüm: PulseAudio config veya stream routing problemi"
elif pactl list sink-inputs short | grep -qi chromium; then
    echo "🟡 WARNING: Browser stream var ama capture zayıf"
    echo "   → Çözüm: Volume/Mute check veya WebRTC routing problemi"
else
    echo "🔴 CRITICAL: Browser hiç audio stream üretmiyor"
    echo "   → Çözüm: Autoplay policy, headless throttling veya AudioContext suspended"
fi
