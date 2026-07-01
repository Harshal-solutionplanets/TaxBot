# TaxBot — Comprehensive Service Cost & Limit Analysis

> **Purpose:** An exhaustive analysis of every third-party service used in TaxBot, the exact failure modes when limits are exceeded, real-world cost calculations at different traffic scales, and the best-plan recommendation for each service tier.

---

## Table of Contents

1. [Pinecone — Vector Database](#1-pinecone--vector-database)
2. [LLM Inference — Google Gemini / Groq / Ollama](#2-llm-inference)
3. [Text Embeddings](#3-text-embeddings)
4. [Backend Hosting — FastAPI / Uvicorn](#4-backend-hosting)
5. [Frontend Hosting — Streamlit / Hugging Face Spaces](#5-frontend-hosting)
6. [Chat Memory Database — SQLite / Supabase](#6-chat-memory-database)
7. [Authentication — Clerk.com](#7-authentication)
8. [Domain & CDN — Cloudflare](#8-domain--cdn)
9. [Consolidated Cost Table by User Scale](#9-consolidated-cost-table-by-user-scale)
10. [Failure Risk Matrix](#10-failure-risk-matrix)

---

## 1. Pinecone — Vector Database

**Role in TaxBot:** Stores 8,790+ dense + sparse vector embeddings of tax document chunks. Every user query triggers a Pinecone hybrid search (reading 20 matching records per query).

---

### Understanding Pinecone Units

| Unit                | Definition                                       | TaxBot Usage Per Query            |
| ------------------- | ------------------------------------------------ | --------------------------------- |
| **Read Unit (RU)**  | Cost of reading 1 vector from an index per query | `top_k × 5` = 100 RUs per query   |
| **Write Unit (WU)** | Cost of writing/upserting 1 vector               | ~8,790 WUs per full ingestion run |
| **Storage**         | GB stored in the index                           | ~12 MB for current 8,790 chunks   |

> **Note:** Pinecone bills Read Units as 5 RUs per vector returned. With `top_k=20`, each query costs **100 RUs**.

---

### Failure Mode: Read Unit Quota Exhausted

**What the user sees:**

```
PineconeApiException: (429) Quota exceeded. Monthly read unit limit reached.
```

The user types a question → the FastAPI backend throws a 500 error → Streamlit shows:
`⚠️ Backend Error: Pinecone quota exceeded.`

**The app is completely non-functional until the next billing cycle.**

---

### Pinecone Plan Analysis (Current Pricing — as of July 2026)

> ⚠️ **Document Correction:** Previous versions of this document listed "Standard Pod p1.x1 = $70" — this was based on Pinecone's deprecated pod-based pricing. The **current Pinecone plan pricing** is as shown on your dashboard screenshot.

| Plan           | Read Units (Monthly)         | Write Units (Monthly)         | Storage                | Monthly Cost              | Best For |
| -------------- | ---------------------------- | ----------------------------- | ---------------------- | ------------------------- | -------- |
| **Starter**    | Up to 1M / mo (free)         | Up to 2M / mo (free)          | Up to 2 GB             | **$0 (Current Plan)**     | POC / dev, < 10,000 queries/month |
| **Builder**    | Up to 2M / mo                | Up to 5M / mo                 | Up to 10 GB            | **$20/month flat**        | Small teams, < 20,000 queries/month |
| **Standard**   | Unlimited ($16 per million)  | Unlimited ($4 per million)    | Unlimited ($0.33/GB/mo)| **$50/month minimum**     | Production, > 20,000 queries/month |
| **Enterprise** | Unlimited ($24 per million)  | Unlimited ($6 per million)    | Unlimited ($0.33/GB/mo)| **$500/month minimum**    | Mission-critical, 99.95% SLA |

### Read Unit Usage Calculator (Using Current Pinecone Plan Pricing)

> Each TaxBot query uses `top_k=20`, which = **100 Read Units** per query on the Pinecone serverless index.

| Daily Queries | Monthly RUs Used | Starter Free? | Builder ($20 flat) | Standard Cost ($50 min + $16/M RUs) |
| ------------- | ---------------- | ------------- | ------------------ | ------------------------------------ |
| 333/day       | 1M RUs           | ✅ FREE (limit) | ✅ Within plan    | $50 + $16 = **$66**                  |
| 666/day       | 2M RUs           | ❌ Exceeded   | ✅ Within plan ($20 flat) | $50 + $32 = **$82**           |
| 1,000/day     | 3M RUs           | ❌ Exceeded   | ❌ Exceeded        | $50 + $48 = **$98**                  |
| 4,000/day     | 12M RUs          | ❌ Exceeded   | ❌ Exceeded        | $50 + $192 = **$242**                |
| 6,000/day     | 18M RUs          | ❌ Exceeded   | ❌ Exceeded        | $50 + $288 = **$338**                |
| 10,000/day    | 30M RUs          | ❌ Exceeded   | ❌ Exceeded        | $50 + $480 = **$530**                |

### ⭐ Best Option (Updated)

- **POC (< 333 queries/day):** Stay on **Starter Free** — you are on this plan now
- **Small usage (333–666 queries/day):** **Builder at $20/month flat** — simple, predictable, no per-unit billing
- **Your Scale (7,500 users, 2K daily, 2–5 queries/day):** At 4,000–10,000 queries/day, **Standard plan at $50/month minimum** applies — cost ranges $242–$530/month for Pinecone alone
  - 💡 **Optimization:** Reduce `top_k` from 20 → 10 in `main.py` to cut Read Units in half (50 RUs/query instead of 100)
- **Enterprise / Mission-Critical:** **Pinecone Enterprise ($500/min)** — 99.95% uptime SLA, private VPC, dedicated support

---

## 2. LLM Inference

**Role in TaxBot:** Receives the retrieved document chunks and the user's question, and generates a grounded, cited answer.

---

### Option A: Google Gemini API (`gemini-1.5-flash`)

| Plan                      | RPM           | RPD           | Tokens/day      | Monthly Cost                      |
| ------------------------- | ------------- | ------------- | --------------- | --------------------------------- |
| **Free**                  | 15 req/min    | 1,500 req/day | 1.5M tokens/day | $0                                |
| **Pay-As-You-Go**         | 2,000 req/min | Unlimited     | Unlimited       | $0.075/1M input + $0.30/1M output |
| **Gemini 1.5 Pro (PAYG)** | 360 req/min   | Unlimited     | Unlimited       | $1.25/1M input + $5.00/1M output  |
| **Vertex AI Enterprise**  | Custom        | Custom        | Custom          | Volume discounts available        |

**Failure Mode (Free Tier):**

```
google.api_core.exceptions.ResourceExhausted: 429 Quota exceeded for quota metric
```

> With just 2 simultaneous CA users each sending a query within the same minute, you will hit the **15 RPM cap** on the free tier. The 16th request in any minute fails.

**Worst Case Calculation (1,000 CAs, 5 queries/day):**

- 1,000 CAs × 5 = 5,000 queries/day
- Average prompt = 6,000 tokens (system prompt + retrieved context + question)
- Average response = 500 tokens
- Input: 5,000 × 6,000 = 30M tokens/month → 30M × $0.075/1M = **$2.25/month**
- Output: 5,000 × 500 = 2.5M tokens/month → 2.5M × $0.30/1M = **$0.75/month**
- **Total: ~$3.00/month** for 1,000 CA users on Gemini Flash PAYG

---

### 📖 Groq LLM Terminology Explained (llama-3.1-8b-instant)

> Based on the Groq pricing page screenshot (current pricing as of July 2026).

#### Input Cost — `$0.05 per 1M tokens` (= 20M tokens per $1)

This is what you **send to the model** — every single character in:
- The system instruction prompt (~300 tokens in TaxBot)
- The 20 retrieved document chunks from Pinecone (~4,000 tokens in TaxBot)
- The user's actual question (~30 tokens)

**Per-query input token count for TaxBot: ~4,330 tokens**

#### Output Cost — `$0.077 per 1M tokens` (~13M tokens per $1)

This is what the model **writes back** — the generated answer text.

**Per-query output token count for TaxBot: ~400–600 tokens** (set `max_output_tokens=1024`)

#### Context Window — `131,072 tokens (128K)`

The maximum combined length of **input + output** the model can process at once. Think of it as the model's "working memory" per request.
- **128K context window means:** The model could read approximately **300 pages of PDF text in a single request**
- **For TaxBot:** Our 4,330-token input is only 3.3% of the context window — very comfortable
- **Advantage over GPT-4:** Older models had 4K–8K context windows; 128K means we could increase `top_k` significantly without hitting limits

#### Max Output Tokens — `131,072`

The maximum length of the **response** the model can generate. We cap TaxBot responses at 1,024 tokens in `main.py` (about 750 words), which is well within this limit.

#### Quantization — `TruePoint Numerics`

Quantization reduces the mathematical precision of model weights (e.g., from 32-bit floating point to 8-bit integers). This makes the model:
- **Faster** (Groq achieves 200–300 tokens/second vs. ~30 tokens/second on standard GPU)
- **Cheaper** to run (smaller memory footprint)
- **Minimally less accurate** (Groq's proprietary TruePoint Numerics is designed to preserve quality in areas that matter)

> For a legal Q&A tool like TaxBot, the accuracy trade-off from quantization is **negligible** — the grounding from Pinecone retrieved documents matters far more than raw model precision.

---

### 💰 Groq Cost Recalculation for Your Actual Scale

**Your scenario: 7,500 total users, ~2,000 daily active, 2–5 queries/day cap**

| Input per TaxBot query | Tokens |
| ---------------------- | ------ |
| System instruction prompt | ~300 |
| 20 retrieved Pinecone chunks (avg. 200 tokens each) | ~4,000 |
| User question | ~30 |
| **Total Input per query** | **~4,330 tokens** |
| **Answer output per query** | **~500 tokens** |

| Query Cap | Daily Queries | Monthly Queries | Input Cost | Output Cost | **Total Groq/month** |
| --------- | ------------- | --------------- | ---------- | ----------- | -------------------- |
| **2/day** | 4,000 | 120,000 | 120K × 4,330 × $0.05/1M = **$26.0** | 120K × 500 × $0.077/1M = **$4.6** | **~$31/month** |
| **3/day** | 6,000 | 180,000 | **$39.0** | **$6.9** | **~$46/month** |
| **5/day** | 10,000 | 300,000 | **$64.9** | **$11.6** | **~$77/month** |

> ⚠️ **Correction from previous document:** The earlier estimate of "$3.00/month" for Groq LLM was calculated with incorrect token assumptions. The accurate figure for your specific scale is **$31–$77/month** depending on your per-user query cap.

---

### ⭐ Best Option for LLM

| Scale                     | Recommendation                        | Reason                                                                           |
| ------------------------- | ------------------------------------- | -------------------------------------------------------------------------------- |
| POC / < 15 RPM            | Gemini Free                           | Zero cost                                                                        |
| 1–50 users                | **Gemini Flash PAYG**                 | < $1/month, zero rate limits, enable billing                                     |
| 50–1,000 users            | **Groq API (llama-3.1-8b-instant)**   | Free tier: 6K tokens/min; PAYG: $0.05/1M input tokens; 200+ tokens/sec speed    |
| 1,000+ users simultaneous | **Groq PAYG + Gemini Flash fallback** | Dual-provider setup routes to whichever API is available; zero downtime          |
| Air-gapped / private data | **Modal.com + Ollama**                | Your own GPU, per-second billing, $30 free credits/month                         |

---

## 3. Text Embeddings

**Role in TaxBot:** Converts the user's question into a 768-dimensional vector for Pinecone semantic search. Called once per user query at inference time.

---

| Provider           | Model                            | Limit (Free)           | Cost (Paid)        | Failure Mode                  |
| ------------------ | -------------------------------- | ---------------------- | ------------------ | ----------------------------- |
| **Ollama (local)** | nomic-embed-text                 | Unlimited              | $0                 | None (local GPU)              |
| **Google Gemini**  | text-embedding-004               | Same as LLM free tier  | $0.00025/1M tokens | 429 Rate limit                |
| **OpenAI**         | text-embedding-3-small           | None (always paid)     | $0.020/1M tokens   | No free tier                  |
| **Cohere**         | embed-english-v3                 | 1,000 API calls/month  | $0.10/1M tokens    | Quota exceeded after 1K calls |
| **Voyage AI**      | voyage-law-2 (legal-specialized) | 200M tokens/month free | $0.12/1M tokens    | Best accuracy for legal text  |

**Worst Case Cost (Embeddings at 1,000 queries/day):**

- 1,000 queries/day × 30 days = 30,000 embeddings/month
- Average query length = 30 tokens
- 30,000 × 30 = 900,000 tokens/month
- On Google PAYG: 900,000 / 1,000,000 × $0.00025 = **$0.000225/month** (essentially free)

### ⭐ Best Option

- **Local deployment:** Stick with **Ollama + nomic-embed-text** — zero cost, zero network latency, GPU-accelerated
- **Cloud deployment (no GPU server):** **Google text-embedding-004** — cost is negligible; bundled with Gemini API key

---

## 4. Backend Hosting

**Role in TaxBot:** Serves the FastAPI REST API (`/api/query`, `/api/sessions`, etc.), loads the BM25 model into RAM, and handles all request routing.

---

### Failure Modes by Plan

| Failure                             | Cause                                                                | User Experience                                               |
| ----------------------------------- | -------------------------------------------------------------------- | ------------------------------------------------------------- |
| **Cold Start (30–40 second delay)** | Render Free tier sleeps after 15 min idle                            | App appears frozen; user waits 30+ seconds for first response |
| **Out of Memory (OOM) crash**       | Render Free/Starter RAM exceeded by BM25 model + concurrent requests | `502 Bad Gateway`; app stops responding entirely              |
| **CPU throttling**                  | Shared CPU overloaded by concurrent requests                         | Queries time out after 30 seconds                             |
| **Request queue overflow**          | Too many concurrent requests on underpowered plan                    | `503 Service Unavailable`                                     |

**BM25 Model RAM Requirement:**

- Our `bm25_model.json` trained on 8,790 chunks ≈ **~50–80 MB RAM** when loaded
- Render Free/Starter (512 MB) can handle this comfortably for 1–10 concurrent users
- At 50+ concurrent users, RAM and CPU becomes a bottleneck on smaller plans

### Render.com Plan Analysis

| Plan         | RAM    | CPU     | Sleep          | Monthly Cost | Max Concurrent Users |
| ------------ | ------ | ------- | -------------- | ------------ | -------------------- |
| **Free**     | 512 MB | Shared  | ✅ After 15min | $0           | 1–3 (slow)           |
| **Starter**  | 512 MB | 0.1 CPU | ❌ Always on   | **$7**       | 5–10                 |
| **Standard** | 2 GB   | 1 CPU   | ❌ Always on   | **$25**      | 20–50                |
| **Pro**      | 4 GB   | 2 CPU   | ❌ Always on   | **$85**      | 50–150               |
| **Pro Plus** | 8 GB   | 4 CPU   | ❌ Always on   | **$175**     | 150–500              |

### Alternative: Railway.app

| Plan      | RAM    | CPU     | Sleep            | Monthly Cost |
| --------- | ------ | ------- | ---------------- | ------------ |
| **Free**  | 512 MB | Shared  | ✅ 500 hrs/month | $0           |
| **Hobby** | 8 GB   | 8 vCPU  | ❌ Always on     | **$5**       |
| **Pro**   | 32 GB  | 32 vCPU | ❌ Always on     | Usage-based  |

> **Railway Hobby at $5/month** beats Render Starter ($7) with 16x more RAM and 80x more CPU for 40% lower cost.

### ⭐ Best Option

| Scale           | Recommendation                                           | Monthly Cost |
| --------------- | -------------------------------------------------------- | ------------ |
| POC             | Render Free (accepts cold starts)                        | $0           |
| 1–50 users      | **Railway Hobby**                                        | **$5**       |
| 50–200 users    | **Render Standard**                                      | $25          |
| 200–1,000 users | **Render Pro**                                           | $85          |
| 1,000+ users    | **AWS ECS / Google Cloud Run** (auto-scaling containers) | $50–200      |

---

## 5. Frontend Hosting

**Role in TaxBot:** Serves the Streamlit Python web interface to end-users via browser.

---

### Failure Modes by Platform

| Platform                  | Failure Mode                          | User Experience                          |
| ------------------------- | ------------------------------------- | ---------------------------------------- |
| Streamlit Community Cloud | **App goes dormant** after inactivity | White screen with "Waking up..." spinner |
| Hugging Face Spaces Free  | **Space pauses** during low traffic   | Loading delay; eventually wakes up       |
| Render Free               | **Sleeps** after 15 min idle          | Same as backend cold start               |

**Critical Limitation — Streamlit Concurrency:**
Streamlit runs each user session as a separate Python thread within the same process. At **50+ simultaneous active users**, the Streamlit process becomes CPU-bound, causing slow UI responses and possible crashes. For 1,000 CAs, this is a serious concern.

### Platform Plan Analysis

| Platform                         | Always-On      | Custom Domain | RAM         | Monthly Cost | Max Stable Users    |
| -------------------------------- | -------------- | ------------- | ----------- | ------------ | ------------------- |
| **Streamlit Community Cloud**    | ✅             | ❌            | ~1 GB       | $0           | ~20–30 simultaneous |
| **Hugging Face Spaces Free**     | ⚠️ (may pause) | ✅ (CNAME)    | 16 GB       | $0           | ~30–50 simultaneous |
| **Hugging Face Spaces Pro**      | ✅             | ✅            | 16 GB       | **$9**       | ~50 simultaneous    |
| **Render.com Standard**          | ✅             | ✅            | 2 GB        | **$25**      | ~20–30 simultaneous |
| **Hugging Face Spaces + T4 GPU** | ✅             | ✅            | 16 GB + GPU | **$60**      | ~50+ simultaneous   |

> **Architectural Note:** For 1,000 CAs using the app simultaneously, Streamlit is not the right tool. A **Next.js / React frontend on Vercel** can serve unlimited concurrent users (serverless rendering) at $0/month and scales infinitely.

### ⭐ Best Option

| Scale                 | Recommendation                         | Monthly Cost |
| --------------------- | -------------------------------------- | ------------ |
| POC / demo            | Hugging Face Spaces Free               | $0           |
| < 50 simultaneous     | **Hugging Face Spaces Pro**            | **$9**       |
| 50–1,000 simultaneous | **Convert to Next.js → Vercel (free)** | $0           |
| Enterprise / private  | **AWS CloudFront + S3 + Next.js**      | $5–20        |

---

## 6. Chat Memory Database

**Role in TaxBot:** Stores conversation sessions and messages (SQLite locally, Supabase in cloud).

---

### Failure Modes

| Failure                         | Cause                                        | User Experience                                              |
| ------------------------------- | -------------------------------------------- | ------------------------------------------------------------ |
| **SQLite file lock**            | Two processes trying to write simultaneously | Chat messages fail to save; no visible error                 |
| **Supabase row limit exceeded** | Free tier: 500MB database                    | New messages cannot be written; query history stops saving   |
| **Supabase connection limit**   | Free tier: 60 concurrent connections         | `too many clients already` error; chat history fails to load |
| **Disk full (local SQLite)**    | Local machine runs out of disk               | Database write fails; sessions cannot be created             |

**Storage Estimate:**

- Average message: ~500 bytes
- 1,000 users × 20 messages/day × 30 days = 600,000 messages/month
- 600,000 × 500 bytes = **~300 MB/month**
- Supabase Free (500 MB total) is exhausted in **less than 2 months** at this scale

### Supabase Plan Analysis

| Plan           | Database Size | Connections     | Bandwidth | Monthly Cost |
| -------------- | ------------- | --------------- | --------- | ------------ |
| **Free**       | 500 MB        | 60 connections  | 5 GB      | $0           |
| **Pro**        | 8 GB          | 200 connections | 50 GB     | **$25**      |
| **Team**       | 16 GB         | 400 connections | 200 GB    | **$599**     |
| **Enterprise** | Custom        | Unlimited       | Custom    | Custom quote |

### ⭐ Best Option

| Scale                  | Recommendation                              | Monthly Cost             |
| ---------------------- | ------------------------------------------- | ------------------------ |
| POC (local)            | **SQLite** (current)                        | $0                       |
| < 500K messages/month  | **Supabase Free**                           | $0                       |
| 500K–5M messages/month | **Supabase Pro**                            | **$25**                  |
| 5M+ messages/month     | **Supabase Team or self-hosted PostgreSQL** | $599+ or $20 self-hosted |

---

## 7. Authentication

**Role in TaxBot (Future):** Manages user accounts, sessions, sign-in/sign-out flow for 1,000+ CAs.

---

### Failure Modes

| Failure                      | Cause                                | User Experience                                            |
| ---------------------------- | ------------------------------------ | ---------------------------------------------------------- |
| **MAU Limit Exceeded**       | Clerk free tier: 10,000 MAU          | Sign-in returns "Service unavailable"; users cannot log in |
| **JWT Signing Key Rotation** | Key changed without updating backend | All existing tokens invalidated; users logged out suddenly |
| **OAuth Callback Failed**    | Google OAuth redirect misconfigured  | Sign-in loop; user never reaches the app                   |

### Clerk.com Plan Analysis

| Plan           | Monthly Active Users (MAU)           | Monthly Cost                            |
| -------------- | ------------------------------------ | --------------------------------------- |
| **Free**       | 10,000 MAU                           | $0                                      |
| **Pro**        | Unlimited                            | **$25/month** + $0.02 per MAU above 10K |
| **Enterprise** | Unlimited + SSO + custom domain auth | Custom quote                            |

> For 1,000 CAs: **Clerk Free easily handles this** (10K MAU free limit >> 1,000 users).

### ⭐ Best Option

- **1,000 CAs:** Stay on **Clerk Free** — well within 10K MAU limit
- **10,000+ CAs:** Upgrade to **Clerk Pro** at $25/month + $0.02/additional MAU

---

## 8. Domain & CDN

**Role in TaxBot:** Routes `taxbot.solutionplanets.com` to your hosting provider; provides SSL, DDoS protection, and global caching.

---

### Failure Modes

| Failure                         | Cause                         | User Experience                                             |
| ------------------------------- | ----------------------------- | ----------------------------------------------------------- |
| **Domain expired**              | Annual renewal missed         | DNS stops resolving; app unreachable for all users          |
| **DDoS attack (no protection)** | Bot traffic overwhelms server | App goes offline; all real CA users blocked                 |
| **SSL certificate expired**     | Renewal failed                | Browser shows "Not Secure" warning; users refuse to proceed |

### Cloudflare Plan Analysis

| Plan         | DDoS Protection  | WAF (Firewall) | Rate Limiting | Monthly Cost |
| ------------ | ---------------- | -------------- | ------------- | ------------ |
| **Free**     | Basic (L3/L4)    | ❌             | ❌            | $0           |
| **Pro**      | Advanced (L3–L7) | ✅ (5 rules)   | ✅            | **$20**      |
| **Business** | Enterprise-grade | ✅ (unlimited) | ✅ Advanced   | **$200**     |

### ⭐ Best Option

- **POC/MVP:** Cloudflare Free (SSL + basic DDoS) + domain from Namecheap ($10/year) → **$10/year total**
- **Production (1,000 CAs):** Cloudflare **Pro at $20/month** — protects against targeted attacks on your legal/financial service

---

## 9. Consolidated Cost Table by User Scale

### Scenario A: POC / Internal Demo (< 50 queries/day)

| Service                     | Plan                            | Monthly Cost |
| --------------------------- | ------------------------------- | ------------ |
| Pinecone                    | Serverless Free                 | $0           |
| LLM (Ollama llama 3.1 [8B]) | Free Tier                       | $0           |
| Embeddings                  | Ollama nomic-embed-text (local) | $0           |
| Backend                     | Render Free                     | $0           |
| Frontend                    | HF Spaces Free                  | $0           |
| Chat DB                     | SQLite (local)                  | $0           |
| Auth                        | None (local user)               | $0           |
| Domain                      | None                            | $0           |
| **Total**                   |                                 | **$0/month** |

---

### Scenario B: Small CA Firm (1–50 users, 200 queries/day)

| Service            | Plan                        | Monthly Cost      |
| ------------------ | --------------------------- | ----------------- |
| Pinecone           | Serverless Paid             | ~$0.02            |
| LLM (Gemini Flash) | Pay-As-You-Go               | ~$0.15            |
| Embeddings         | Google (bundled)            | ~$0.00            |
| Backend            | Railway Hobby               | $5.00             |
| Frontend           | HF Spaces Pro               | $9.00             |
| Chat DB            | Supabase Free               | $0                |
| Auth               | Clerk Free                  | $0                |
| Domain + SSL       | Namecheap + Cloudflare Free | $0.84 (amortized) |
| **Total**          |                             | **~$15/month**    |

---

### Scenario C: Growing Firm (50–500 CAs, 2,000 queries/day)

| Service                 | Plan             | Monthly Cost                   |
| ----------------------- | ---------------- | ------------------------------ |
| Pinecone                | Serverless Paid  | ~$0.18                         |
| LLM (Gemini Flash PAYG) | Pay-As-You-Go    | ~$1.50                         |
| Embeddings              | Google (bundled) | ~$0.00                         |
| Backend                 | Render Standard  | $25.00                         |
| Frontend                | HF Spaces Pro    | $9.00                          |
| Chat DB                 | Supabase Pro     | $25.00                         |
| Auth                    | Clerk Free       | $0                             |
| Domain + Cloudflare Pro | Pro plan         | $20.84                         |
| **Total**               |                  | **~$81/month (~₹6,800/month)** |

---

### Scenario D: Your Actual Scale — 7,500 Users, 2,000 Daily Active, 3 Queries/Day Cap

> This scenario is calibrated specifically to your stated user base.
> - **Total registered users:** 7,500 CAs
> - **Daily active (30% concurrency):** ~2,000 users/day
> - **Query cap enforced:** 3 queries/user/day (middle of your 2–5 range)
> - **Daily queries:** 2,000 × 3 = **6,000 queries/day**
> - **Monthly queries:** 6,000 × 30 = **180,000 queries/month**

| Service                 | Plan                           | Calculation Detail                                       | Monthly Cost |
| ----------------------- | ------------------------------ | -------------------------------------------------------- | ------------ |
| **Pinecone**            | Standard ($50 min + $16/M RUs) | 18M RUs/mo × $16 = $288 + $50 minimum                   | **$338.00**  |
| **Pinecone (optimized)**| Standard — reduce top_k to 10  | 9M RUs/mo × $16 = $144 + $50 minimum                    | **$194.00** ✂️ |
| **LLM (Groq PAYG)**     | llama-3.1-8b-instant           | 180K queries × 4,330 tokens × $0.05/1M (input)          | **$39.00**   |
| *(LLM output)*          | —                              | 180K queries × 500 tokens × $0.077/1M (output)          | **$6.93**    |
| **Embeddings**          | Google text-embedding-004      | 180K queries × 30 tokens = negligible                   | ~$0.00       |
| **Backend**             | Render Pro (4 GB RAM)          | Always-on, handles 50–150 concurrent                    | $85.00       |
| **Frontend**            | Next.js on Vercel (Free tier)  | Scales to unlimited concurrent users                    | $0.00        |
| **Chat DB**             | Supabase Pro                   | 180K queries × 2 msgs = 360K msgs/mo → well within 8 GB | $25.00       |
| **Auth**                | Clerk Free (< 10K MAU)         | 7,500 users < 10,000 MAU free limit                     | $0.00        |
| **Domain + CDN**        | Namecheap + Cloudflare Pro     | Domain $10/yr + Cloudflare $20/mo                       | $20.84       |
| **Total (standard)**    |                                | Pinecone Standard + full stack                          | **~$475/month (~₹39,500/month)** |
| **Total (optimized)**   |                                | With top_k=10 optimization on Pinecone                  | **~$331/month (~₹27,600/month)** |

> 💡 **Key Insight:** Pinecone is the dominant cost driver at this scale. The single most impactful optimization is **reducing `top_k` from 20 → 10** in `main.py`, which cuts Pinecone costs by ~43% with minimal impact on answer quality.

---

### Scenario D2: Enterprise (10,000 queries/day, 5 query/day cap)

---

### Scenario E: Absolute Worst Case (1,000 CAs all active simultaneously, 100K queries/day)

| Service                      | Plan                   | Monthly Cost                         |
| ---------------------------- | ---------------------- | ------------------------------------ |
| Pinecone                     | Enterprise pod (p2.x4) | ~$560.00                             |
| LLM (Gemini 1.5 Pro PAYG)    | High volume            | ~$90.00                              |
| Embeddings                   | Google PAYG            | ~$0.10                               |
| Backend                      | AWS ECS (4 containers) | ~$200.00                             |
| Frontend                     | Next.js on Vercel Pro  | $20.00                               |
| Chat DB                      | Supabase Team          | $599.00                              |
| Auth                         | Clerk Pro              | ~$45.00                              |
| Domain + Cloudflare Business | Business plan          | $200.00                              |
| **Total**                    |                        | **~$1,714/month (~₹1,43,000/month)** |

> **Reality check:** 1,000 CAs simultaneously sending 100 queries each every day is an extremely heavy load for a legal Q&A app. Real-world CA firm usage will likely be 10–50 concurrent peak users, not 1,000.

---

## 10. Failure Risk Matrix

| Risk                        | Service             | Probability                   | Impact                  | Mitigation                       |
| --------------------------- | ------------------- | ----------------------------- | ----------------------- | -------------------------------- |
| **Read unit quota hit**     | Pinecone            | Medium (at 34+ queries/day)   | 🔴 App broken           | Upgrade to Serverless Paid / Pod |
| **LLM rate limit (15 RPM)** | Gemini Free         | High (2+ concurrent users)    | 🔴 All queries fail     | Enable Pay-As-You-Go billing     |
| **Backend cold start**      | Render Free         | High (after 15min idle)       | 🟡 30-sec delay         | Upgrade to Starter ($7)          |
| **Backend OOM crash**       | Render Free/Starter | Medium (50+ concurrent)       | 🔴 App goes down        | Upgrade to Standard ($25)        |
| **Chat DB full**            | Supabase Free       | Medium (2 months at 1K users) | 🟡 History stops saving | Upgrade to Supabase Pro          |
| **Frontend sleeping**       | HF Spaces Free      | Low                           | 🟡 Loading delay        | Upgrade to HF Pro ($9)           |
| **DDoS attack**             | Any                 | Low                           | 🔴 All users blocked    | Cloudflare Pro ($20)             |
| **Domain expired**          | Namecheap           | Very Low                      | 🔴 App unreachable      | Enable auto-renew                |
| **SSL expired**             | Cloudflare          | Very Low                      | 🟡 Browser warning      | Cloudflare manages auto-renewal  |
| **Pinecone storage full**   | Pinecone            | Very Low (12MB / 2GB)         | 🔴 Ingestion fails      | Upgrade to Serverless Paid       |
| **Auth MAU exceeded**       | Clerk Free          | Very Low (< 10K free)         | 🔴 Sign-in fails        | Upgrade to Clerk Pro ($25)       |

---

## Final Recommendation Summary

> **Minimum paid services to guarantee zero downtime for a CA firm:**

1. ✅ **Backend:** Railway Hobby — **$5/month** (eliminates cold starts, 8GB RAM)
2. ✅ **LLM:** Gemini PAYG — **~$0.25–3/month** (eliminates rate limit errors)
3. ✅ **Frontend:** Hugging Face Spaces Pro — **$9/month** (always-on UI)
4. ✅ **Domain:** Namecheap — **~$1/month** amortized (professional URL)
5. ✅ **CDN/SSL:** Cloudflare Free — **$0** (automatic SSL + basic DDoS)
6. ✅ **Pinecone:** Serverless Paid — **~$0.02–0.30/month** (only billed when free tier exceeded)
7. ✅ **Chat DB:** Supabase Free — **$0** (sufficient for < 200K messages/month)

**Combined guaranteed zero-downtime cost: ~$15–20/month (~₹1,250–1,700/month)**

---

_Document last updated: July 1, 2026_
