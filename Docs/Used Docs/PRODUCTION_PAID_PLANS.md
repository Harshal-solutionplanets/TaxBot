# TaxBot — Production-Grade Paid Plans Guide

> **Goal:** Zero downtime, zero rate limit errors, zero cold starts, and no storage ceiling for a CA firm running TaxBot as a reliable production application.

---

## 🚨 Problems Solved by Going Paid

Before listing the plans, here are the exact errors you will hit on free tiers and what causes them:

| Error You Will See | Root Cause | Component to Upgrade |
| ------------------ | ---------- | -------------------- |
| `429 Too Many Requests` | LLM inference rate limit hit (15 req/min on Gemini free) | LLM API |
| `503 Service Unavailable` / 30-second delay | Backend server sleeping (Render free tier sleeps after 15 min idle) | Backend Hosting |
| `Failed to fetch` / `Backend URL did not respond` | Backend sleeping or crashed, no auto-restart | Backend Hosting |
| `PineconeException: Quota exceeded` | Pinecone free storage (2GB) or read unit quota exceeded | Vector Database |
| `Embedding quota exceeded` | Embedding API daily/minute request limits reached | Embeddings |
| `Space is sleeping` | Hugging Face Spaces free tier paused due to inactivity | Frontend Hosting |
| `Out of memory` / `Model load failed` | GPU VRAM exceeded when running Ollama on a small cloud VM | LLM Hosting (GPU) |
| `SSL certificate error` / `Domain not found` | No custom domain or SSL configured | Domain + CDN |

---

## 💳 Component-by-Component Paid Plans

---

### 1. 🤖 LLM Inference — Fix: `429 Too Many Requests`

**Problem:** Gemini free tier allows only **15 requests/minute and 1,500 requests/day**. In a CA firm environment with even 5 concurrent users, this will be hit immediately.

#### Recommended: Google Gemini API — Pay-As-You-Go

| Plan | RPM Limit | Price | Best For |
| ---- | --------- | ----- | -------- |
| **Free Tier** | 15 req/min | $0 | Dev/Testing only |
| **Pay-As-You-Go** | 2,000 req/min | $0.075 / 1M input tokens | 1–10 users |
| **Pay-As-You-Go (Gemini 1.5 Pro)** | 360 req/min | $1.25 / 1M input tokens | 10–50 users |

**Estimated Monthly Cost for a CA firm (50 queries/day × 30 days × ~2,000 tokens/query):**
```
50 queries/day × 30 days = 1,500 queries/month
1,500 queries × 2,000 tokens = 3,000,000 tokens
3,000,000 tokens × $0.075 / 1M = ~$0.23/month
```
> **Effective cost: ~$0.25/month** for light usage. Even at 500 queries/day, cost stays under **$2.50/month**.

**How to upgrade:** Go to [aistudio.google.com](https://aistudio.google.com) → Enable billing → No plan change needed; pay-as-you-go activates automatically.

---

#### Alternative: Groq API — Pay-As-You-Go (Ultra-Fast)

| Plan | Speed | Price | Limit |
| ---- | ----- | ----- | ----- |
| **Free** | 200+ tok/sec | $0 | 6,000 tokens/min |
| **Pay-As-You-Go** | 200+ tok/sec | $0.06 / 1M tokens (llama-3.1-8b) | No limit |

> **Effective cost: ~$0.18/month** for 50 queries/day. Groq is both faster AND cheaper than Gemini.

**How to upgrade:** [console.groq.com](https://console.groq.com) → Add credit card → Pay only for actual usage.

---

### 2. 📊 Vector Database — Fix: `PineconeException: Quota exceeded`

**Problem:** Pinecone Serverless free tier provides **2GB storage** and limited monthly **read/write units**. With 8,790 chunks at ~1KB each, you are using ~9MB today. But as more documents are ingested (new tax circulars, judgments, etc.) and query volume grows, you will hit both storage and query limits.

#### Recommended: Pinecone Serverless — Pay-As-You-Go

| Tier | Storage | Read Units | Write Units | Monthly Cost |
| ---- | ------- | ---------- | ----------- | ------------ |
| **Free** | 2 GB | 100K/month | 100K/month | $0 |
| **Serverless (Paid)** | Unlimited | $0.10/1M units | $0.10/1M units | ~$2–10/month |
| **Standard Pod (p1.x1)** | 1GB/pod (dedicated) | Unlimited | Unlimited | $70/month |

**Estimated Monthly Cost (50 queries/day, 8,790 chunks, top_k=20 per query):**
```
50 queries/day × 30 days = 1,500 queries
1,500 queries × 20 reads = 30,000 read units/month
30,000 / 1,000,000 × $0.10 = $0.003/month
```
> **Effective cost: < $1.00/month** for light-to-medium usage. You stay well within free tier unless you have thousands of queries/month.

**Storage risk trigger:** Pinecone storage limit is hit only if you ingest **2,000+ additional pages** of tax documents. Current 8,790 chunks ≈ 9MB — well within free limits.

**How to upgrade:** [app.pinecone.io](https://app.pinecone.io) → Settings → Billing → Add payment method. You are only charged beyond the free tier.

---

### 3. 🖥️ Backend Hosting — Fix: `Failed to fetch` / Cold Start Delays

**Problem:** Render.com free web services **sleep after 15 minutes of inactivity**. The first query after sleep takes **20–40 seconds** to respond, which looks like a crash to users.

#### Option A: Render.com — Starter Plan (Recommended)

| Plan | Sleep | RAM | CPU | Monthly Cost |
| ---- | ----- | --- | --- | ------------ |
| **Free** | ✅ Sleeps after 15min | 512 MB | Shared | $0 |
| **Starter** | ❌ Always-on | 512 MB | 0.1 CPU | **$7/month** |
| **Standard** | ❌ Always-on | 2 GB | 1 CPU | **$25/month** |

> **Recommendation: Starter at $7/month** is sufficient for a CA firm with light-to-medium usage. Upgrades to Standard only if you have 20+ concurrent users.

**How to upgrade:** [dashboard.render.com](https://dashboard.render.com) → Your Service → Settings → Instance Type → Starter → Save.

---

#### Option B: Railway.app — Hobby Plan

| Plan | Sleep | Resources | Monthly Cost |
| ---- | ----- | --------- | ------------ |
| **Free** | ✅ Limited hours | 512 MB | $0 (500 hours/month) |
| **Hobby** | ❌ Always-on | 8 GB RAM, 8 vCPU | **$5/month** |
| **Pro** | ❌ Always-on | Custom | Usage-based |

> **Recommendation: Hobby at $5/month** — cheaper than Render Starter, more RAM, always-on.

---

### 4. 🌐 Frontend Hosting — Fix: `Space is sleeping` / Slow UI

**Problem:** Hugging Face Spaces free tier may pause your Streamlit app during low activity periods, causing a loading delay.

#### Option A: Hugging Face Spaces — Pro Plan (Best)

| Plan | Sleep | Hardware | Monthly Cost |
| ---- | ----- | -------- | ------------ |
| **Free** | ⚠️ May pause | 2 vCPU, 16 GB RAM | $0 |
| **Pro** | ❌ Always-on | 2 vCPU, 16 GB RAM | **$9/month** |
| **Pro + GPU** | ❌ Always-on | T4 GPU | **$60/month** |

> **Recommendation: Pro at $9/month** removes all sleep limits and gives priority access.

---

#### Option B: Streamlit Community Cloud — Teams Plan

| Plan | Apps | Custom Domain | Monthly Cost |
| ---- | ---- | ------------- | ------------ |
| **Free** | 3 public apps | ❌ | $0 |
| **Teams** | Unlimited private apps | ✅ | **$25/user/month** |

> This is expensive for a small firm. **Hugging Face Pro at $9/month is far better value.**

---

### 5. 🔗 Custom Domain + SSL — Fix: Professional URL

**Problem:** Without a custom domain, your app URL will be `harshal-sp.hf.space/taxbot` or `taxbot.onrender.com`. Not professional for a CA firm delivering client services.

| Service | What It Does | Cost |
| ------- | ------------ | ---- |
| **Domain Registration** (GoDaddy / Namecheap) | Buy `taxbot.solutionplanets.com` or `taxbot.in` | **$8–15/year** (~₹700–1,300/year) |
| **Cloudflare** (DNS + SSL + CDN) | Route domain to your app; free SSL certificate | **$0/month** |
| **Cloudflare Pro** (Optional) | Advanced DDoS, WAF security rules | **$20/month** |

> **Minimum needed:** Buy a domain ($10/year) + use Cloudflare Free (DNS proxy + SSL). Total: **$10/year (~₹900/year)**.

---

### 6. 🤖 Self-Hosted LLM on Cloud GPU — Fix: No Third-Party API Limits

If you want to eliminate all third-party API dependencies (Gemini, Groq) and run **your own Ollama + Llama 3.1** in the cloud permanently:

#### Option A: RunPod.io — Secure Cloud GPU

| GPU | VRAM | Speed | Monthly Cost (24/7) |
| --- | ---- | ----- | ------------------- |
| RTX 3090 | 24 GB | Fast | **~$22–28/month** |
| RTX 4090 | 24 GB | Very Fast | **~$42–55/month** |
| A100 | 80 GB | Blazing | **~$120–150/month** |

> **Recommendation: RTX 3090 at ~$25/month** — same GPU class as your 4060, runs Llama 3.1 8B with room for embedding model simultaneously.

#### Option B: Modal.com — Serverless GPU (Pay Per Request)

| Resource | Price | Free Credits |
| -------- | ----- | ------------ |
| A10G GPU | $0.000583/GPU-second | **$30/month free** |
| T4 GPU | $0.000164/GPU-second | Included in free credits |

> **At 50 queries/day × ~5 sec inference = 7,500 GPU-seconds/month = $4.37/month**. Falls within free credits for light usage. Scales to paid seamlessly.

---

## 📦 Production Stack Bundles

### Bundle A: Light Usage (1–5 CAs, < 100 queries/day)

| Component | Service | Monthly Cost |
| --------- | ------- | ------------ |
| LLM + Embeddings | Gemini Pay-As-You-Go | ~$0.50 |
| Vector DB | Pinecone Serverless (likely stays free) | $0 |
| Backend | Render.com Starter | $7.00 |
| Frontend | Hugging Face Spaces Pro | $9.00 |
| Domain | Namecheap + Cloudflare Free | $1.25 (amortized) |
| **Total** | | **~$18/month (~₹1,500/month)** |

---

### Bundle B: Medium Usage (5–20 CAs, 100–500 queries/day)

| Component | Service | Monthly Cost |
| --------- | ------- | ------------ |
| LLM + Embeddings | Gemini Pay-As-You-Go | ~$2–5 |
| Vector DB | Pinecone Serverless | ~$1–3 |
| Backend | Railway.app Hobby | $5.00 |
| Frontend | Hugging Face Spaces Pro | $9.00 |
| Domain | Namecheap + Cloudflare Free | $1.25 (amortized) |
| **Total** | | **~$20–25/month (~₹1,700–2,100/month)** |

---

### Bundle C: Heavy Usage / Enterprise (20+ CAs, 500+ queries/day)

| Component | Service | Monthly Cost |
| --------- | ------- | ------------ |
| LLM + Embeddings | Groq Pay-As-You-Go OR dedicated GPU | ~$5–25 |
| Vector DB | Pinecone Standard Pod (p1.x1) | $70.00 |
| Backend | Render.com Standard | $25.00 |
| Frontend | Hugging Face Spaces Pro | $9.00 |
| Domain + Security | Cloudflare Pro + Custom Domain | $21.25 |
| **Total** | | **~$130–150/month (~₹11,000–12,500/month)** |

---

## 📋 Upgrade Priority Order

If budget is tight, upgrade services in this order based on user impact:

```
1. Backend Hosting (Render Starter $7/month)
   ↳ HIGHEST IMPACT: Eliminates cold starts. Users never see "Backend URL failed to respond."

2. LLM API (Gemini Pay-As-You-Go)
   ↳ Eliminates 429 rate limit errors. Cost is negligible (~$0.25–2/month).

3. Frontend Hosting (Hugging Face Spaces Pro $9/month)
   ↳ Eliminates frontend sleep. Always-on UI.

4. Custom Domain ($10/year via Namecheap + Cloudflare Free)
   ↳ Professional URL for client-facing deployment.

5. Pinecone Serverless (Auto-paid when free tier exceeded)
   ↳ Only needed when document corpus > 2GB or query volume > 100K/month.

6. Dedicated GPU Cloud (RunPod ~$25/month)
   ↳ Only if you want to eliminate all third-party LLM APIs entirely.
```

---

## 🔐 Security Checklist for Production

Before going live with paid plans, ensure:

- [ ] `.env` file is **never committed** to GitHub (already in `.gitignore` ✅)
- [ ] All API keys (Gemini, Pinecone, Groq) stored as **environment secrets** in hosting platform
- [ ] Pinecone index is set to **private** (not publicly queryable)
- [ ] FastAPI backend has **CORS restricted** to only your frontend domain
- [ ] Custom domain has **HTTPS/SSL enforced** via Cloudflare (free)
- [ ] Rate limiting added to FastAPI `/api/query` endpoint to prevent abuse

---

_Document last updated: June 30, 2026_
