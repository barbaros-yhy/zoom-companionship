# 🚀 AWS EC2 Production Deployment - Komple Rehber

> **Zoom Companion Bot** için sıfırdan production deployment rehberi

**Süre:** ~45 dakika
**Seviye:** Başlangıç (AWS deneyimi gerekmez)
**Maliyet:** ~$0.70/saat (EC2 g4dn.xlarge)

---

## 📋 İçindekiler

1. [Ön Hazırlık](#1-ön-hazırlık)
2. [AWS Bedrock Model Access](#2-aws-bedrock-model-access)
3. [IAM Role Oluşturma](#3-iam-role-oluşturma)
4. [S3 Bucket Oluşturma](#4-s3-bucket-oluşturma-opsiyonel)
5. [EC2 Instance Oluşturma](#5-ec2-instance-oluşturma)
6. [SSH Bağlantısı](#6-ssh-bağlantısı)
7. [Sistem Kurulumu](#7-sistem-kurulumu)
8. [Environment Configuration](#8-environment-configuration)
9. [Servisleri Başlatma](#9-servisleri-başlatma)
10. [Deployment Testi](#10-deployment-testi)
11. [Monitoring & Logs](#11-monitoring--logs)
12. [Troubleshooting](#12-troubleshooting)
13. [Maliyet Optimizasyonu](#13-maliyet-optimizasyonu)

---

## 🎯 1. Ön Hazırlık

### 1.1 Gereksinimler

- [ ] AWS Account (ücretsiz kayıt: https://aws.amazon.com)
- [ ] Kredi kartı (AWS hesap doğrulama için)
- [ ] SSH client (Mac/Linux: Terminal, Windows: PuTTY veya Windows Terminal)
- [ ] Tarayıcı (Chrome/Firefox önerilir)

### 1.2 Beklenen Maliyetler

| Kaynak | Maliyet |
|--------|---------|
| EC2 g4dn.xlarge (eu-central-1) | ~$0.526/saat |
| EBS Storage (50 GB) | ~$5/ay |
| AWS Bedrock (Claude Haiku) | ~$0.01/meeting |
| S3 Storage (opsiyonel) | ~$0.023/GB/ay |
| **Toplam (24/7 çalışırsa)** | **~$385/ay** |

💡 **Maliyet Optimizasyonu:** Sadece gerektiğinde instance'ı çalıştırarak aylık $50-100'e düşürülebilir.

---

## 🤖 2. AWS Bedrock Model Access

Bot, toplantı sonunda AI summary oluşturmak için AWS Bedrock kullanıyor.

### 2.1 AWS Console'a Giriş

1. https://console.aws.amazon.com adresine git
2. Email/şifre ile giriş yap
3. Sağ üst köşeden **Region** kontrol et

### 2.2 Region Seçimi

**ÖNEMLI:** Bedrock sadece belirli regionlarda mevcut!

- Sağ üst köşede **region adına** tıkla (örn: "US East (N. Virginia)")
- **Europe (Frankfurt) eu-central-1** seç ✅

### 2.3 Bedrock Servisine Git

1. Üst arama çubuğuna **"bedrock"** yaz
2. **Amazon Bedrock** servisine tıkla
3. Sol menüden **Model access** tıkla

Ya da direkt link:
https://eu-central-1.console.aws.amazon.com/bedrock/home?region=eu-central-1#/modelaccess

### 2.4 Model Access İsteği

1. **Manage model access** turuncu buton (sağ üstte) → tıkla
2. Modeller listesinde **Anthropic** bölümünü bul
3. **Claude Haiku** yanındaki checkbox'ı işaretle:
   ```
   ☑ Claude 3.5 Haiku (anthropic.claude-3-5-haiku-20241022-v1:0)
   ```
4. Sağ alt köşede **Request model access** tıkla
5. **Submit** tıkla (kullanım koşullarını kabul et)

### 2.5 Onay Bekle

- **Access status:** `Access granted` yeşil tick görmeli ✅
- Genellikle **anında** onaylanır
- Bazen 5-10 dakika sürebilir

**Doğrulama:**
```
Model                          Status
Claude 3.5 Haiku              Access granted ✅
```

✅ **Tamamlandı!** Bedrock hazır.

---

## 🔐 3. IAM Role Oluşturma

EC2 instance'ın Bedrock'a erişebilmesi için IAM role gerekiyor.

### 3.1 IAM Servisine Git

1. Üst arama çubuğuna **"iam"** yaz
2. **IAM** servisine tıkla

Ya da direkt link:
https://console.aws.amazon.com/iam

### 3.2 IAM Policy Oluştur

#### Adım A: Policies Sayfasına Git

1. Sol menüden **Policies** tıkla
2. **Create policy** mavi buton (sağ üstte) → tıkla

#### Adım B: JSON Editor

1. **JSON** sekmesine tıkla (varsayılan "Visual" sekmesi)
2. Mevcut JSON'u sil
3. Aşağıdaki JSON'u yapıştır:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "bedrock:InvokeModel",
      "Resource": "arn:aws:bedrock:eu-central-1::foundation-model/anthropic.claude-3-5-haiku-20241022-v1:0"
    }
  ]
}
```

4. **Next** tıkla

#### Adım C: Policy Detayları

1. **Policy name:** `ZoomCompanionBedrock`
2. **Description (opsiyonel):** `Allows Zoom Companion Bot to invoke Claude Haiku via Bedrock`
3. **Tags (opsiyonel):** Boş bırak
4. **Create policy** tıkla

✅ **Policy oluşturuldu:** `ZoomCompanionBedrock`

### 3.3 IAM Role Oluştur

#### Adım A: Roles Sayfasına Git

1. Sol menüden **Roles** tıkla
2. **Create role** mavi buton (sağ üstte) → tıkla

#### Adım B: Trusted Entity Seç

1. **Trusted entity type:** `AWS service` seçili olmalı ✅
2. **Use case:** Dropdown'dan **EC2** seç
3. **Next** tıkla

#### Adım C: Permissions Ekle

1. Arama kutusuna `ZoomCompanionBedrock` yaz
2. Az önce oluşturduğun policy'yi bul
3. Yanındaki **checkbox'ı işaretle** ✅
4. **Next** tıkla

#### Adım D: Role Detayları

1. **Role name:** `zoom-companion-bot-role`
2. **Description (opsiyonel):** `IAM role for Zoom Companion Bot EC2 instance`
3. **Step 1 - Select trusted entities** doğru mu kontrol et:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Principal": {
           "Service": "ec2.amazonaws.com"
         },
         "Action": "sts:AssumeRole"
       }
     ]
   }
   ```
4. **Create role** tıkla

✅ **Role oluşturuldu:** `zoom-companion-bot-role`

### 3.4 Doğrulama

**Roles** sayfasında:
1. `zoom-companion-bot-role` arama kutusuna yaz
2. Role'ü bul ve **tıkla**
3. **Permissions** sekmesinde `ZoomCompanionBedrock` policy'yi görmelisin ✅
4. **Trust relationships** sekmesinde `ec2.amazonaws.com` görmelisin ✅

---

## 💾 4. S3 Bucket Oluşturma (Opsiyonel)

Transcript'leri S3'e backup etmek istersen (opsiyonel):

### 4.1 S3 Servisine Git

1. Üst arama çubuğuna **"s3"** yaz
2. **S3** servisine tıkla

Ya da direkt link:
https://s3.console.aws.amazon.com/s3

### 4.2 Bucket Oluştur

1. **Create bucket** turuncu buton → tıkla

**General configuration:**
- **Bucket name:** `zoom-companion-transcripts-[rastgele-sayı]`
  - Örnek: `zoom-companion-transcripts-20240306`
  - ⚠️ Bucket adı **globally unique** olmalı!
- **AWS Region:** `Europe (Frankfurt) eu-central-1`

**Object Ownership:**
- Varsayılan bırak (ACLs disabled)

**Block Public Access:**
- ✅ **Block all public access** işaretli bırak (güvenlik)

**Bucket Versioning:**
- İsteğe bağlı (Disabled bırakabilirsin)

**Tags (opsiyonel):**
- Boş bırak

**Default encryption:**
- Varsayılan bırak (SSE-S3)

2. **Create bucket** tıkla

✅ **Bucket oluşturuldu!**

### 4.3 Bucket ARN'ini Kopyala

1. Bucket'a tıkla
2. **Properties** sekmesinde
3. **Amazon Resource Name (ARN)** kopyala:
   ```
   arn:aws:s3:::zoom-companion-transcripts-20240306
   ```

💡 **Not:** Daha sonra `.env` dosyasında kullanacağız.

---

## 🖥️ 5. EC2 Instance Oluşturma

Şimdi GPU'lu server oluşturacağız.

### 5.1 EC2 Servisine Git

1. Üst arama çubuğuna **"ec2"** yaz
2. **EC2** servisine tıkla

Ya da direkt link:
https://eu-central-1.console.aws.amazon.com/ec2

### 5.2 Launch Instance

1. Sol menüden **Instances** tıkla
2. **Launch instances** turuncu buton (sağ üstte) → tıkla

### 5.3 Name and Tags

**Name:** `zoom-companion-bot`

💡 Tags opsiyonel (boş bırakabilirsin)

### 5.4 Application and OS Images (AMI)

1. **Quick Start** sekmesi seçili olmalı ✅
2. **Ubuntu** logo'suna tıkla (turuncu logo)
3. Dropdown'dan seç:
   ```
   Ubuntu Server 22.04 LTS (HVM), SSD Volume Type
   64-bit (x86)
   ami-xxxxxxxxxx
   ```

⚠️ **ÖNEMLI:** "**22.04**" ve "**LTS**" olduğundan emin ol!

### 5.5 Instance Type

1. **Instance type** dropdown'a tıkla
2. Arama kutusuna `g4dn.xlarge` yaz
3. **g4dn.xlarge** seç ✅

**Detaylar:**
```
Family: g4dn (GPU instances)
vCPUs: 4
Memory: 16 GiB
Instance Storage: 1 x 125 NVMe SSD
Network Performance: Up to 25 Gigabit
GPU: 1x NVIDIA T4 Tensor Core (16 GB)
Price: ~$0.526/hour (eu-central-1)
```

### 5.6 Key Pair (Login)

#### Yeni Key Oluştur:

1. **Key pair name** dropdown → **Create new key pair** (yeşil link) tıkla

**Pop-up açılacak:**
- **Key pair name:** `zoom-companion-key`
- **Key pair type:** `RSA` ✅
- **Private key file format:**
  - Mac/Linux: `.pem` ✅
  - Windows (PuTTY): `.ppk`

2. **Create key pair** tıkla

📥 **`zoom-companion-key.pem` indirilecek** → Güvenli yere kaydet!

⚠️ **UYARI:** Bu dosyayı kaybedersen instance'a SSH yapamazsın!

#### Var Olan Key Kullan:

Eğer daha önce key oluşturduysam dropdown'dan seç.

### 5.7 Network Settings

#### 5.7.1 VPC ve Subnet

- **VPC:** `Default VPC` (otomatik seçili)
- **Subnet:** `No preference` (otomatik seçili)
- **Auto-assign public IP:** `Enable` ✅

#### 5.7.2 Firewall (Security Groups)

1. **Create security group** seçili olsun ✅

**Security group name:** `zoom-companion-sg`

**Description:** `Security group for Zoom Companion Bot`

#### 5.7.3 Inbound Security Group Rules

Varsayılan SSH kuralı var:
```
Type: SSH
Protocol: TCP
Port: 22
Source: 0.0.0.0/0 (veya My IP)
```

**4 kural daha ekle** → Her kural için **Add security group rule** tıkla:

---

**Kural 1 - Speaches API:**
```
Type: Custom TCP
Protocol: TCP
Port range: 8000
Source type: Anywhere IPv4
Source: 0.0.0.0/0
Description: Speaches STT API
```

**Kural 2 - API Server:**
```
Type: Custom TCP
Protocol: TCP
Port range: 3001
Source type: Anywhere IPv4
Source: 0.0.0.0/0
Description: API Server
```

**Kural 3 - Dashboard (Opsiyonel):**
```
Type: Custom TCP
Protocol: TCP
Port range: 3000
Source type: Anywhere IPv4
Source: 0.0.0.0/0
Description: Next.js Dashboard
```

**Kural 4 - WebSocket:**
```
Type: Custom TCP
Protocol: TCP
Port range: 8765
Source type: Anywhere IPv4
Source: 0.0.0.0/0
Description: Bot WebSocket
```

---

✅ **Toplam 5 kural olmalı:** 22, 8000, 3001, 3000, 8765

💡 **Güvenlik İyileştirmesi:** Production'da `0.0.0.0/0` yerine spesifik IP aralıkları kullan.

### 5.8 Configure Storage

**Root volume (Volume 1):**
- **Size (GiB):** `50` (varsayılan 8 GB → **değiştir!**)
- **Volume type:** `gp3` (General Purpose SSD)
- **IOPS:** 3000 (varsayılan)
- **Throughput:** 125 MB/s (varsayılan)
- **Delete on termination:** ✅ İşaretli (instance silinince disk de silinir)
- **Encrypted:** İsteğe bağlı (ücretsiz, ama performans -%5)

💡 **Neden 50 GB?**
- Ubuntu: ~5 GB
- Docker images: ~5 GB
- Whisper models: ~3 GB (small) - ~10 GB (large)
- Logs & transcripts: ~20 GB
- **Toplam: ~40 GB** → 50 GB güvenli

### 5.9 Advanced Details

**ÇOK ÖNEMLİ:** Bu kısmı atlamadan yap!

1. **Advanced details** başlığını bul (sayfa sonunda)
2. **Expand** (genişlet) et

Aşağı kaydır → **IAM instance profile** bul:

**IAM instance profile:** Dropdown'dan **`zoom-companion-bot-role`** seç ✅

⚠️ **Görmüyorsan?** [Adım 3.3](#33-iam-role-oluştur)'e geri dön, role'ü oluştur.

**Diğer ayarlar:** Varsayılan bırak (değiştirme)

### 5.10 Summary ve Launch

Sağ tarafta **Summary** panelini kontrol et:

```
Number of instances: 1
Software image (AMI): Ubuntu Server 22.04 LTS (HVM)
Instance type: g4dn.xlarge
Key pair name: zoom-companion-key
Network: Default VPC
Storage: 50 GiB gp3
IAM role: zoom-companion-bot-role ✅
Security groups: zoom-companion-sg (SSH, 8000, 3001, 3000, 8765)
```

✅ Her şey doğruysa → **Launch instance** turuncu buton tıkla

### 5.11 Success!

```
✅ Successfully initiated launch of instance i-0123456789abcdef0
```

**View all instances** tıkla

---

## ⏳ 5.12 Instance Başlamasını Bekle

**Instances** sayfasında:

1. **zoom-companion-bot** instance'ını bul
2. **Instance state** sütununa bak:
   - `Pending` (sarı) → Bekle ⏳
   - `Running` (yeşil) → Devam et ✅

3. **Status check** sütununa bak:
   - `Initializing` (gri) → Bekle ⏳
   - `2/2 checks passed` (yeşil) → Devam et ✅

**Bekleme süresi:** ~3-5 dakika

### 5.13 Public IP'yi Kopyala

Instance **Running** olunca:

1. Instance'a **tıkla** (checkbox değil, ismin üzerine)
2. Alt panelde **Details** sekmesi açılır
3. **Public IPv4 address** bul ve kopyala:
   ```
   3.123.45.67
   ```

📋 Bu IP'yi not al → SSH için gerekecek

---

## 🔐 6. SSH Bağlantısı

### 6.1 Mac / Linux

#### Terminal Aç

```bash
# Applications → Utilities → Terminal
# veya Spotlight: Cmd+Space → "terminal" yaz
```

#### Key Dosyasını Bul

```bash
cd ~/Downloads
ls -la zoom-companion-key.pem
```

Dosya görünmüyorsa tarayıcı indirme klasörünü kontrol et.

#### İzinleri Düzelt

```bash
chmod 400 zoom-companion-key.pem
```

Bu komut key dosyasını sadece sen okuyabilir hale getirir (güvenlik).

#### SSH Bağlan

```bash
ssh -i zoom-companion-key.pem ubuntu@3.123.45.67
```

⚠️ **3.123.45.67** yerine **kendi Public IP'ni** yaz!

**İlk bağlantıda soracak:**
```
The authenticity of host '3.123.45.67 (3.123.45.67)' can't be established.
ECDSA key fingerprint is SHA256:xxxxxxxxxxxxxxxxxxx.
Are you sure you want to continue connecting (yes/no/[fingerprint])?
```

**`yes` yaz** → Enter

✅ **Başarılı giriş:**
```
Welcome to Ubuntu 22.04.3 LTS (GNU/Linux 5.15.0-1046-aws x86_64)

ubuntu@ip-172-31-12-34:~$
```

### 6.2 Windows (PowerShell / CMD)

#### PowerShell / CMD Aç

```
Win+R → "powershell" → Enter
```

#### Key Dosyasını Bul

```powershell
cd C:\Users\KullaniciAdin\Downloads
dir zoom-companion-key.pem
```

#### SSH Bağlan

```powershell
ssh -i zoom-companion-key.pem ubuntu@3.123.45.67
```

**Not:** Windows 10/11 native SSH desteği var.

### 6.3 Windows (PuTTY)

#### PuTTY İndir (eğer yoksa)

https://www.putty.org → Download → putty-64bit-installer.msi

#### PuTTYgen ile Key Dönüştür

1. **PuTTYgen** aç (Start Menu → PuTTY → PuTTYgen)
2. **Conversions** → **Import key**
3. `zoom-companion-key.pem` seç
4. **Save private key** → `zoom-companion-key.ppk` kaydet

#### PuTTY ile Bağlan

1. **PuTTY** aç
2. **Host Name:** `ubuntu@3.123.45.67`
3. **Port:** `22`
4. **Connection type:** `SSH`
5. Sol menü: **Connection → SSH → Auth → Credentials**
6. **Private key file:** `zoom-companion-key.ppk` seç
7. **Open** tıkla
8. **Accept** (ilk bağlantı uyarısı)

### 6.4 SSH Bağlantı Sorunları

#### "Permission denied (publickey)"

```bash
# Key dosya izinleri yanlış
chmod 400 zoom-companion-key.pem

# Doğru kullanıcı adı: ubuntu
ssh -i zoom-companion-key.pem ubuntu@IP
# ❌ ssh -i zoom-companion-key.pem ec2-user@IP
# ❌ ssh -i zoom-companion-key.pem root@IP
```

#### "Connection timed out"

- Security group'ta port 22 (SSH) açık mı kontrol et
- Public IP doğru mu?
- Instance **Running** durumda mı?

#### "Host key verification failed"

```bash
# ~/.ssh/known_hosts dosyasını temizle
ssh-keygen -R 3.123.45.67
# Tekrar dene
ssh -i zoom-companion-key.pem ubuntu@3.123.45.67
```

---

## ⚙️ 7. Sistem Kurulumu

SSH bağlantısı başarılı olduktan sonra:

### 7.1 Sistem Bilgilerini Kontrol Et

```bash
# Ubuntu versiyonu
lsb_release -a
# Ubuntu 22.04.3 LTS

# CPU
lscpu | grep "Model name"
# Intel(R) Xeon(R) Platinum 8259CL

# RAM
free -h
# 15Gi total

# Disk
df -h /
# 48G available
```

### 7.2 Root Kullanıcısına Geç

```bash
sudo su
```

Prompt değişecek:
```bash
root@ip-172-31-12-34:/home/ubuntu#
```

### 7.3 Setup Script İndir

```bash
curl -fsSL https://raw.githubusercontent.com/barbaros-yhy/zoom-companionship/main/infra/setup.sh -o setup.sh
```

İndirilen dosyayı kontrol et:
```bash
cat setup.sh | head -20
```

Görmelisin:
```bash
#!/bin/bash
# infra/setup.sh
# Bootstrap script for EC2 g4dn.xlarge (Ubuntu 22.04 + NVIDIA GPU)
...
```

### 7.4 Executable Yap

```bash
chmod +x setup.sh
```

### 7.5 Setup Script Çalıştır

```bash
./setup.sh
```

**Script ne yapıyor?**
```
=== Zoom Companion Bot EC2 Setup ===

[1/7] System updates...
[2/7] Installing NVIDIA drivers...
[3/7] Installing Docker...
[4/7] Installing NVIDIA Container Toolkit...
[5/7] Installing PulseAudio...
[6/7] Cloning repository...
[7/7] Starting services...

=== Setup complete. Bot services starting... ===
```

**Süre:** ~10-15 dakika

### 7.6 Reboot Gerekebilir

NVIDIA driver kurulumundan sonra:
```
Reboot may be required after NVIDIA driver install.
```

Reboot yap:
```bash
sudo reboot
```

**SSH bağlantısı kopacak** → 2 dakika bekle → Tekrar bağlan:
```bash
ssh -i zoom-companion-key.pem ubuntu@3.123.45.67
```

### 7.7 GPU Kontrolü

```bash
nvidia-smi
```

**Beklenen output:**
```
+-----------------------------------------------------------------------------+
| NVIDIA-SMI 525.147.05   Driver Version: 525.147.05   CUDA Version: 12.0   |
|-------------------------------+----------------------+----------------------+
| GPU  Name        Persistence-M| Bus-Id        Disp.A | Volatile Uncorr. ECC |
| Fan  Temp  Perf  Pwr:Usage/Cap|         Memory-Usage | GPU-Util  Compute M. |
|                               |                      |               MIG M. |
|===============================+======================+======================|
|   0  Tesla T4            Off  | 00000000:00:1E.0 Off |                    0 |
| N/A   37C    P0    26W /  70W |      0MiB / 15360MiB |      0%      Default |
|                               |                      |                  N/A |
+-------------------------------+----------------------+----------------------+
```

✅ **Tesla T4 görünüyorsa başarılı!**

❌ **"command not found" hatası?** → Reboot yapmadın, `sudo reboot` yap

---

## 🔧 8. Environment Configuration

### 8.1 .env Dosyasını Düzenle

```bash
cd /opt/zoom-companionship
nano .env
```

### 8.2 .env İçeriği

Aşağıdaki gibi doldur:

```bash
# AWS Configuration
AWS_REGION=eu-central-1
AWS_S3_BUCKET=zoom-companion-transcripts-20240306  # Adım 4'te oluşturduğun bucket

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

# Dashboard (Opsiyonel)
NEXT_PUBLIC_BOT_WS_URL=ws://3.123.45.67:8765  # Kendi Public IP'ni yaz
NEXT_PUBLIC_API_URL=http://3.123.45.67:3001
```

⚠️ **DEĞİŞTİR:**
- `AWS_S3_BUCKET`: Kendi bucket adın
- `NEXT_PUBLIC_BOT_WS_URL`: Kendi Public IP'n
- `NEXT_PUBLIC_API_URL`: Kendi Public IP'n

### 8.3 Kaydet ve Çık

**Ctrl+X** → **Y** → **Enter**

### 8.4 Doğrula

```bash
cat .env | grep -v "^#"
```

Boş satırlar olmadan tüm değişkenler görünmeli.

---

## 🚀 9. Servisleri Başlatma

### 9.1 Docker Grubuna Ekle

```bash
sudo usermod -aG docker ubuntu
newgrp docker
```

Bu komut ubuntu kullanıcısını docker grubuna ekler (sudo gerektirmez).

### 9.2 Docker Klasörüne Git

```bash
cd /opt/zoom-companionship/docker
```

### 9.3 Servisleri Başlat

```bash
docker compose up -d
```

**İlk başlatma çıktısı:**
```
[+] Running 10/10
 ✔ speaches 9 layers pulled
 ✔ api 1 layers pulled
 ✔ bot Built
[+] Running 4/4
 ✔ Network docker_default          Created
 ✔ Volume docker_speaches-models   Created
 ✔ Volume docker_bot-data          Created
 ✔ Container docker-speaches-1     Started
 ✔ Container docker-api-1          Started
```

**Süre:** İlk kez ~5-10 dakika (Whisper model indiriliyor)

### 9.4 Model İndirme İlerlemesi

```bash
docker compose logs -f speaches | grep -i "download\|preload"
```

**Çıktı:**
```
speaches-1 | INFO: Preloading 1 models on startup
speaches-1 | INFO: Downloading model: Systran/faster-whisper-large-v3-turbo
speaches-1 | Fetching 5 files:   0%|          | 0/5 [00:00<?, ?it/s]
speaches-1 | Fetching 5 files:  20%|██        | 1/5 [00:10<00:40, 10.0s/it]
speaches-1 | Fetching 5 files: 100%|██████████| 5/5 [03:45<00:00, 45.0s/it]
speaches-1 | INFO: Successfully downloaded model
```

**Ctrl+C** ile çık

### 9.5 Servis Durumlarını Kontrol Et

```bash
docker compose ps
```

**Beklenen output:**
```
NAME                STATUS              PORTS
docker-api-1        Up (healthy)        0.0.0.0:3001->3001/tcp
docker-speaches-1   Up (healthy)        0.0.0.0:8000->8000/tcp
```

✅ Tüm servisler **Up** ve **(healthy)** olmalı

❌ **Exited** veya **unhealthy** görüyorsan → [Troubleshooting](#12-troubleshooting) bölümüne git

---

## ✅ 10. Deployment Testi

### 10.1 Speaches Health Check

```bash
curl http://localhost:8000/health
```

**Beklenen:**
```json
{"message":"OK"}
```

### 10.2 API Health Check

```bash
curl http://localhost:3001/meetings
```

**Beklenen:**
```json
[]
```

### 10.3 GPU Kullanımı

```bash
nvidia-smi
```

Speaches çalışıyorsa **GPU Memory-Usage** artmış olmalı:
```
|   0  Tesla T4            Off  | 00000000:00:1E.0 Off |                    0 |
| N/A   42C    P0    28W /  70W |   3456MiB / 15360MiB |      12%     Default |
```

### 10.4 Bedrock Erişimi

```bash
aws sts get-caller-identity
```

**Beklenen:**
```json
{
    "UserId": "AROAXXXXXXXXXX:i-0123456789abcdef0",
    "Account": "123456789012",
    "Arn": "arn:aws:sts::123456789012:assumed-role/zoom-companion-bot-role/i-0123456789abcdef0"
}
```

✅ IAM role çalışıyor!

### 10.5 Test Meeting Oluştur

```bash
curl -X POST http://localhost:3001/meetings \
  -H "Content-Type: application/json" \
  -d '{
    "meeting_url": "https://zoom.us/j/123456789",
    "title": "Production Test Meeting"
  }'
```

**Response:**
```json
{"meeting_id":"abc12345"}
```

✅ **Deployment başarılı! Sistem production'da çalışıyor!** 🎉

---

**Tam deployment dökümanı oluşturuldu. Commit edip push edelim mi?**