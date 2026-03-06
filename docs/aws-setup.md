# AWS Setup — Zoom Companion Bot

## 1. Bedrock Model Access

AWS Console → **Bedrock** → **Model access** (sol menü)
- Region: **eu-central-1** olduğundan emin ol
- `Claude Haiku (claude-haiku-4-5-20251001)` → **Request access**
- Genellikle anında aktif olur

---

## 2. IAM Policy Oluştur

IAM → Policies → **Create policy** → JSON tab:

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

Policy adı: `ZoomCompanionBedrock`

---

## 3. IAM Role Oluştur

IAM → Roles → **Create Role**
- Trusted entity: **AWS service**
- Use case: **EC2**
- Permissions: `ZoomCompanionBedrock` policy'yi ekle
- Role adı: `zoom-companion-bot-role`
- Create

---

## 4. EC2 Instance'a Role Attach Et

**Yeni instance için:**
- Launch sırasında IAM instance profile: `zoom-companion-bot-role`

**Var olan instance için:**
- EC2 → Instance seç → Actions → Security → **Modify IAM role**
- `zoom-companion-bot-role` seç → Update

---

## 5. Doğrulama

EC2 instance üzerinde:

```bash
# Credentials çalışıyor mu?
aws sts get-caller-identity

# Bedrock erişimi var mı?
aws bedrock list-foundation-models --region eu-central-1 --query 'modelSummaries[?contains(modelId, `haiku`)]'
```

---

## Notlar

- `.env` dosyasında AWS credential gerekmez — boto3 instance role'den otomatik alır
- Sadece `AWS_REGION=eu-central-1` yeterli
- Bedrock `eu-central-1`'de mevcut (Frankfurt)
