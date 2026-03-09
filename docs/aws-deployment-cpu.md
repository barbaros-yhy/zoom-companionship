# 🚀 AWS EC2 CPU-Only Deployment Rehberi

> **Zoom Companion Bot** için GPU gerektirmeyen, uygun maliyetli AWS deployment

**Süre:** ~30 dakika
**Seviye:** Başlangıç (AWS deneyimi gerekmez)
**Maliyet:** ~$0.05/saat (EC2 t3.medium) = ~$36/ay (7/24 çalışırsa)

---

## 📋 İçindekiler

1. [Ön Hazırlık](#1-ön-hazırlık)
2. [AWS Bedrock Model Access](#2-aws-bedrock-model-access)
3. [IAM Role Oluşturma](#3-iam-role-oluşturma)
4. [EC2 Instance Oluşturma](#4-ec2-instance-oluşturma)
5. [SSH Bağlantısı](#5-ssh-bağlantısı)
6. [Sistem Kurulumu](#6-sistem-kurulumu)
7. [Environment Configuration](#7-environment-configuration)
8. [Servisleri Başlatma](#8-servisleri-başlatma)
9. [Deployment Testi](#9-deployment-testi)
10. [Troubleshooting](#10-troubleshooting)

---

## 🎯 1. Ön Hazırlık

### 1.1 Gereksinimler

- [ ] AWS Account (ücretsiz kayıt: https://aws.amazon.com)
- [ ] Kredi kartı (AWS hesap doğrulama için)
- [ ] SSH client (Mac/Linux: Terminal, Windows: PowerShell)

### 1.2 Beklenen Maliyetler

| Kaynak | Maliyet |
|--------|---------|
| EC2 t3.medium (eu-central-1) | ~$0.048/saat |
| EBS Storage (30 GB) | ~$3/ay |
| AWS Bedrock (Claude Haiku) | ~$0.01/meeting |
| **Toplam (24/7 çalışırsa)** | **~$38/ay** |

💡 **Not:** CPU-only transkripsiyon GPU'ya göre 3-5x daha yavaş ama çok daha ucuz. Kısa meetingler (<30dk) için yeterli.

---

## 🤖 2. AWS Bedrock Model Access

Bot, toplantı sonunda AI summary oluşturmak için AWS Bedrock kullanıyor.

### 2.1 AWS Console'a Giriş

1. https://console.aws.amazon.com adresine git
2. Email/şifre ile giriş yap
3. Sağ üst köşeden **Region** → **Europe (Frankfurt) eu-central-1** seç ✅

### 2.2 Bedrock Model Access

1. Üst arama çubuğuna **"bedrock"** yaz → **Amazon Bedrock** seç
2. Sol menüden **Model access** tıkla
3. **Manage model access** (sağ üst) → **Claude Haiku** checkbox işaretle
4. **Request model access** → **Submit**

**Doğrulama:**
- Access status: `Access granted` yeşil tick ✅
- Genellikle anında onaylanır

---

## 🔐 3. IAM Role Oluşturma

EC2 instance'ın Bedrock'a erişebilmesi için IAM role gerekiyor.

### 3.1 IAM Policy Oluştur

1. AWS Console → **IAM** → **Policies** → **Create policy**
2. **JSON** sekmesi → Aşağıdaki JSON'u yapıştır:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "bedrock:InvokeModel",
      "Resource": "arn:aws:bedrock:eu-central-1::foundation-model/anthropic.claude-haiku-4-5-20251001-v1:0"
    }
  ]
}
```

3. **Next** → Policy name: `ZoomCompanionBedrock` → **Create policy**

### 3.2 IAM Role Oluştur

1. **IAM** → **Roles** → **Create role**
2. **Trusted entity type:** `AWS service`
3. **Use case:** `EC2` → **Next**
4. **Permissions:** `ZoomCompanionBedrock` seç → **Next**
5. **Role name:** `zoom-companion-bot-role` → **Create role**

✅ Role oluşturuldu!

---

## 🖥️ 4. EC2 Instance Oluşturma

### 4.1 Launch Instance

1. AWS Console → **EC2** → **Launch instances**

### 4.2 Instance Konfigürasyonu

**Name:** `zoom-companion-bot-cpu`

**Application and OS Images (AMI):**
- **Ubuntu Server 22.04 LTS (HVM), SSD Volume Type** ✅

**Instance Type:**
- **t3.medium** (2 vCPU, 4 GB RAM, ~$0.048/saat) ✅
- Alternatif: **t3.large** (4 vCPU, 8 GB RAM) daha hızlı ama 2x pahalı

**Key Pair:**
- **Create new key pair:**
  - Name: `zoom-companion-key`
  - Type: `RSA`
  - Format: `.pem` (Mac/Linux) veya `.ppk` (Windows/PuTTY)
- 📥 **Key dosyasını güvenli yere kaydet!**

**Network Settings:**
- **Create security group:**
  - Name: `zoom-companion-sg`
  - **Inbound rules:**
    - SSH (22) - My IP veya 0.0.0.0/0
    - Custom TCP (8000) - 0.0.0.0/0 (Speaches API)
    - Custom TCP (3001) - 0.0.0.0/0 (API Server)
    - Custom TCP (8765) - 0.0.0.0/0 (WebSocket)

**Configure Storage:**
- **Size:** `30 GiB` (varsayılan 8 GB → değiştir!)
- **Type:** `gp3` (General Purpose SSD)

**Advanced Details:**
- **IAM instance profile:** `zoom-companion-bot-role` ✅ (ÇOK ÖNEMLİ!)

### 4.3 Launch

**Launch instance** → **View all instances** → Instance **Running** olana kadar bekle (~2 dakika)

### 4.4 Public IP'yi Kopyala

1. Instance'a tıkla
2. **Public IPv4 address** kopyala (örn: `3.123.45.67`)

---

## 🔐 5. SSH Bağlantısı

### 5.1 Mac / Linux

```bash
cd ~/Downloads
chmod 400 zoom-companion-key.pem
ssh -i zoom-companion-key.pem ubuntu@3.123.45.67
```

⚠️ **3.123.45.67** yerine **kendi Public IP'ni** yaz!

**İlk bağlantıda:** `yes` yaz → Enter

### 5.2 Windows (PowerShell)

```powershell
cd C:\Users\KullaniciAdin\Downloads
ssh -i zoom-companion-key.pem ubuntu@3.123.45.67
```

✅ **Başarılı giriş:**
```
Welcome to Ubuntu 22.04 LTS
ubuntu@ip-172-31-12-34:~$
```

---

## ⚙️ 6. Sistem Kurulumu

### 6.1 Root Kullanıcısına Geç

```bash
sudo su
```

### 6.2 Setup Script İndir

```bash
curl -fsSL https://raw.githubusercontent.com/barbaros-yhy/zoom-companionship/main/infra/setup-cpu.sh -o setup.sh
chmod +x setup.sh
```

### 6.3 Setup Script Çalıştır

```bash
./setup.sh
```

**Script ne yapıyor?**
```
=== Zoom Companion Bot EC2 Setup (CPU-only) ===

[1/5] System updates...
[2/5] Installing Docker...
[3/5] Installing PulseAudio...
[4/5] Cloning repository...
[5/5] Starting services...

=== Setup complete. Bot services starting... ===
```

**Süre:** ~5-8 dakika (GPU kurulumu yok)

✅ Setup tamamlandı!

---

## 🔧 7. Environment Configuration

### 7.1 .env Dosyasını Düzenle

```bash
cd /opt/zoom-companionship
nano .env
```

### 7.2 .env İçeriği

```bash
# AWS Configuration
AWS_REGION=eu-central-1

# Speaches STT
SPEACHES_URL=http://speaches:8000

# Bot Configuration
BOT_WS_PORT=8765
BOT_NAME=Companion
DB_PATH=/data/meetings.db
TRANSCRIPT_DIR=/data/transcripts

# API Server
API_URL=http://localhost:3001
PORT=3001

# Dashboard (Opsiyonel - daha sonra eklenebilir)
NEXT_PUBLIC_BOT_WS_URL=ws://3.123.45.67:8765  # Kendi Public IP'ni yaz
NEXT_PUBLIC_API_URL=http://3.123.45.67:3001
```

⚠️ **DEĞİŞTİR:**
- `NEXT_PUBLIC_BOT_WS_URL`: Kendi Public IP'n
- `NEXT_PUBLIC_API_URL`: Kendi Public IP'n

**Kaydet:** Ctrl+X → Y → Enter

---

## 🚀 8. Servisleri Başlatma

### 8.1 Docker Klasörüne Git

```bash
cd /opt/zoom-companionship/docker
```

### 8.2 Servisleri Başlat (CPU Versiyonu)

```bash
docker compose -f docker-compose.aws-cpu.yml up -d
```

**İlk başlatma:**
```
[+] Running 10/10
 ✔ speaches Pulled (CPU image)
 ✔ api Started
 ✔ bot Started
 ✔ Volume speaches-models Created
 ✔ Volume bot-data Created
```

**Süre:** İlk kez ~3-5 dakika (Whisper small model indiriliyor)

### 8.3 Model İndirme İlerlemesi

```bash
docker compose -f docker-compose.aws-cpu.yml logs -f speaches
```

**Çıktı:**
```
speaches-1 | INFO: Preloading model: Systran/faster-whisper-small
speaches-1 | Fetching 5 files: 100%|██████████| 5/5 [01:30<00:00]
speaches-1 | INFO: Model loaded successfully
```

**Ctrl+C** ile çık

### 8.4 Servis Durumlarını Kontrol Et

```bash
docker compose -f docker-compose.aws-cpu.yml ps
```

**Beklenen:**
```
NAME                STATUS              PORTS
docker-api-1        Up (healthy)        0.0.0.0:3001->3001/tcp
docker-bot-1        Up                  0.0.0.0:8765->8765/tcp
docker-speaches-1   Up (healthy)        0.0.0.0:8000->8000/tcp
```

✅ Tüm servisler **Up** olmalı

---

## ✅ 9. Deployment Testi

### 9.1 Speaches Health Check

```bash
curl http://localhost:8000/health
```

**Beklenen:**
```json
{"message":"OK"}
```

### 9.2 API Health Check

```bash
curl http://localhost:3001/meetings
```

**Beklenen:**
```json
[]
```

### 9.3 Bedrock Erişimi

```bash
aws sts get-caller-identity
```

**Beklenen:**
```json
{
    "UserId": "AROAXXXXXXXXXX:i-0123456789abcdef0",
    "Account": "123456789012",
    "Arn": "arn:aws:sts::123456789012:assumed-role/zoom-companion-bot-role/i-..."
}
```

✅ IAM role çalışıyor!

### 9.4 Test Meeting Oluştur

```bash
curl -X POST http://localhost:3001/meetings \
  -H "Content-Type: application/json" \
  -d '{
    "meeting_url": "https://zoom.us/j/123456789",
    "title": "CPU Test Meeting"
  }'
```

**Response:**
```json
{"meeting_id":"abc12345"}
```

### 9.5 External Access Test (Kendi bilgisayarından)

Tarayıcıdan aç:
```
http://3.123.45.67:3001/meetings
```

Boş array `[]` görmelisin.

✅ **Deployment başarılı! CPU-only sistem production'da çalışıyor!** 🎉

---

## 🐛 10. Troubleshooting

### Servisler başlamıyor

```bash
# Logları kontrol et
cd /opt/zoom-companionship/docker
docker compose -f docker-compose.aws-cpu.yml logs

# Servisleri yeniden başlat
docker compose -f docker-compose.aws-cpu.yml down
docker compose -f docker-compose.aws-cpu.yml up -d
```

### PulseAudio hatası

```bash
# PulseAudio'yu yeniden başlat
pulseaudio --kill
pulseaudio --start
pactl load-module module-null-sink sink_name=virtual_sink
pactl set-default-sink virtual_sink
```

### Bedrock "AccessDenied" hatası

1. IAM role doğru mu? `aws sts get-caller-identity` kontrol et
2. Bedrock model access granted mı? AWS Console → Bedrock → Model access
3. Region doğru mu? `eu-central-1` olmalı

### CPU transkripsiyon çok yavaş

```bash
# Daha küçük model kullan (daha hızlı ama daha az doğru)
nano /opt/zoom-companionship/docker/docker-compose.aws-cpu.yml
```

`faster-whisper-small` → `faster-whisper-tiny` değiştir:
```yaml
- DEFAULT_MODEL=Systran/faster-whisper-tiny
- WHISPER__MODEL=Systran/faster-whisper-tiny
- PRELOAD_MODELS=["Systran/faster-whisper-tiny"]
```

```bash
# Servisleri yeniden başlat
docker compose -f docker-compose.aws-cpu.yml down
docker compose -f docker-compose.aws-cpu.yml up -d
```

---

## 📊 Performans Karşılaştırması

| Model | Instance | Transkripsiyon Hızı | Doğruluk | Maliyet |
|-------|----------|---------------------|----------|---------|
| large-v3-turbo + GPU | g4dn.xlarge | **1x** (real-time) | Mükemmel | $385/ay |
| small + CPU | t3.medium | 3-5x yavaş | İyi | $38/ay |
| tiny + CPU | t3.medium | 2-3x yavaş | Orta | $38/ay |

💡 **Öneri:** Kısa meetingler (<30dk) için `small + t3.medium` yeterli.

---

## 🔒 Güvenlik İyileştirmeleri

Production kullanımı için:

1. **Security Group:**
   - SSH: `0.0.0.0/0` → `MyIP` değiştir
   - API/WebSocket: Sadece ihtiyaç duyulan IP aralıkları

2. **Elastic IP:** Public IP değişmesin (instance restart'ta)
   ```bash
   # AWS Console → EC2 → Elastic IPs → Allocate → Associate
   ```

3. **HTTPS:** API için SSL sertifikası (Let's Encrypt + Nginx)

4. **Monitoring:** CloudWatch alarms (CPU, disk, hata logları)

---

## 🎉 Başarılı Deployment!

Sistem çalışıyor. Şimdi:

1. **Bot'u test et:** Gerçek Zoom meeting'e katıl
2. **Dashboard ekle:** Next.js uygulamasını deploy et
3. **Monitoring kur:** CloudWatch ile metrikler izle
4. **Backup yap:** Transcripts için S3 entegrasyonu ekle

**Sorular?** GitHub Issues: https://github.com/barbaros-yhy/zoom-companionship/issues
