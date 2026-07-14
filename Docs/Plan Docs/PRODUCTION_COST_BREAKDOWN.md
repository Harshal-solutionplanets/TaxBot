# 💰 TaxBot — Comprehensive Production Cost Breakdown

> **Scope**: Every paid subscription and service required to run TaxBot in production.
> **Target Scale**: 6,000–7,000 registered users · ~3,500 concurrent active users · 3 queries/day limit.
> **LLM Strategy**: Full Gemini Setup (Gemini 2.5 Flash for chat + Gemini Embedding-2 for vectors).

---

## 📊 Usage Assumptions

| Parameter                          | Value                          |
|:-----------------------------------|:-------------------------------|
| Total registered users             | 7,000                          |
| Active users per day               | **3,500** (concurrent users)   |
| Queries per user per day           | 3 (hard limit)                 |
| **Total queries per day**          | **10,500**                     |
| **Total queries per month (30d)**  | **315,000**                    |
| Follow-up suggestion calls/query   | 1 (AI-generated)               |
| Embedding calls per query          | 1 (query-time only)            |
| **Total LLM calls per month**     | **630,000** (query + suggestion)|
| **Total embedding calls per month**| **315,000**                    |

### Token Estimates per Query

| Component                  | Tokens        |
|:---------------------------|:--------------|
| User question (input)      | ~50 tokens    |
| RAG context chunks (input) | ~2,000 tokens |
| System prompt (input)      | ~200 tokens   |
| **Total input per LLM call** | **~2,250 tokens** |
| **Output per LLM call**   | **~500 tokens** |
| Follow-up input            | ~500 tokens   |
| Follow-up output           | ~100 tokens   |
| Embedding input per query  | ~50 tokens    |

---

## 🧩 Complete Service Map

TaxBot requires **5 external services** to operate in production:

| #  | Service              | Purpose                                   | Provider       |
|:--:|:---------------------|:------------------------------------------|:---------------|
| 1  | **LLM Chat API**     | Answer user tax queries (streaming)       | Google Gemini  |
| 2  | **Embedding API**    | Convert user queries to vectors at runtime| Google Gemini  |
| 3  | **Vector Database**  | Store & retrieve document embeddings      | Pinecone       |
| 4  | **Relational Database** | Users, sessions, messages, rate limits | Supabase       |
| 5  | **App Hosting**      | Deploy backend (FastAPI) + frontend (Next.js) | Cloud Provider |

---

## 1️⃣ Google Gemini API — LLM & Embeddings

> **Account**: `taxbot0807@gmail.com` on [Google AI Studio](https://aistudio.google.com/)
> **Billing**: Pay-as-you-go (credit/debit card linked)

### 1A. Chat LLM — Gemini 2.5 Flash

| Metric       | Rate                    |
|:-------------|:------------------------|
| Input price  | **$0.30 / 1M tokens**  |
| Output price | **$2.50 / 1M tokens**  |

**Main Query Cost (315K queries/month):**

| Component           | Calculation                          | Monthly Cost  |
|:--------------------|:-------------------------------------|:-------------:|
| Input tokens        | 315,000 × 2,250 = **708.75M tokens**  | —           |
| Input cost          | 708.75 × $0.30                        | **$212.63**  |
| Output tokens       | 315,000 × 500 = **157.5M tokens**     | —           |
| Output cost         | 157.5 × $2.50                          | **$393.75**  |
| **Subtotal (Query)**| —                                      | **$606.38**  |

**Follow-up Suggestion Cost (315K calls/month):**

| Component           | Calculation                          | Monthly Cost  |
|:--------------------|:-------------------------------------|:-------------:|
| Input tokens        | 315,000 × 500 = **157.5M tokens**     | —           |
| Input cost          | 157.5 × $0.30                          | **$47.25**   |
| Output tokens       | 315,000 × 100 = **31.5M tokens**      | —           |
| Output cost         | 31.5 × $2.50                           | **$78.75**   |
| **Subtotal (Suggestions)** | —                               | **$126.00**  |

> [!TIP]
> **Context Caching Optimization**: The system prompt (~200 tokens) is identical for every request. By caching it, Google charges only ~10% of the input rate for cached tokens. This can save approximately **$19–$21/month** on the system prompt alone. If frequently retrieved document chunks are also cached, savings could reach **$70–$140/month**.

| Component               | Monthly Cost   |
|:-------------------------|:--------------:|
| Main query LLM           | $606.38       |
| Follow-up suggestions    | $126.00       |
| **Gemini Chat Total**    | **$732.38**   |
| *With context caching*   | *~$590–$660*  |

---

### 1B. Embeddings — Gemini Embedding-2

| Metric       | Rate                    |
|:-------------|:------------------------|
| Price        | **$0.20 / 1M tokens**  |

**Query-Time Embedding Cost:**

| Component           | Calculation                        | Monthly Cost |
|:--------------------|:-----------------------------------|:------------:|
| Queries per month   | 315,000                             | —           |
| Tokens per query    | ~50 tokens                           | —           |
| Total tokens        | 315,000 × 50 = **15.75M tokens**    | —           |
| Cost                | 15.75 × $0.20                         | **$3.15**   |

**One-Time Ingestion Embedding Cost (initial setup):**

| Component           | Calculation                        | Cost (One-Time) |
|:--------------------|:-----------------------------------|:----------------:|
| Total document chunks | ~9,200 chunks                     | —               |
| Tokens per chunk    | ~75 tokens (avg)                     | —               |
| Total tokens        | 9,200 × 75 = **690,000 tokens**     | —               |
| Cost                | 0.69 × $0.20                         | **$0.14**       |

| Component                  | Monthly Cost  |
|:---------------------------|:-------------:|
| Query-time embeddings       | $3.15        |
| Ingestion (one-time)        | $0.14        |
| **Embedding Total/month**  | **$3.15**    |

---

### 📦 Gemini API — Combined Monthly Total

| Component               | Monthly Cost     |
|:-------------------------|:----------------:|
| Chat LLM (2.5 Flash)     | $732.38         |
| Embeddings (Embedding-2) | $3.15           |
| **Gemini Total**         | **$735.53**     |
| *With context caching*   | *~$595–$665*    |

---

## 2️⃣ Pinecone — Vector Database

> **Account**: `taxbot0807@gmail.com` on [Pinecone Console](https://console.pinecone.io/)
> **Index**: `taxbot-hybrid-index` (768 dimensions, dotproduct metric, serverless)

### Plan Options

| Plan        | Base Fee    | Includes                                     | Overage Rates            |
|:------------|:------------|:---------------------------------------------|:-------------------------|
| **Starter** | $0/month    | 2GB storage, 1M RU, 2M WU                   | N/A (hard limits)        |
| **Builder** | $20/month   | Higher limits, no overages (hard block)      | N/A (hard limits)        |
| **Standard**| $50/month   | Pay-as-you-go after minimum                  | $16/M RU, $4/M WU, $0.33/GB |

### Usage Estimate

| Metric                    | Calculation                                | Value        |
|:--------------------------|:-------------------------------------------|:-------------|
| Stored vectors            | ~9,200 chunks × 768 dims                   | ~0.03 GB     |
| Queries per month         | 315,000 (1 query = 1 Pinecone read)        | 315,000 RU   |
| Writes per month          | ~0 (only during re-ingestion)               | Negligible   |

**The Starter (Free) plan is sufficient** — TaxBot uses only ~315K of the 1M read unit limit and well under 2GB storage.

| Plan Recommended          | Monthly Cost |
|:--------------------------|:------------:|
| **Starter (Free)**        | **$0**       |
| Builder (if need headroom)| $20          |
| Standard (full production)| $50          |

> [!IMPORTANT]
> **Recommendation**: Start on the **Starter plan (Free)**. It covers 1M read units/month — TaxBot only needs ~315K. Upgrade to Standard ($50/month) only if you need SLA guarantees or your user base exceeds ~10,000 active users/day.

---

## 3️⃣ Supabase — Relational Database

> **Account**: `taxbot0807@gmail.com` on [Supabase Console](https://supabase.com/)
> **Project**: `taxbot-prod`
> **Tables**: `taxbot_users`, `taxbot_sessions`, `taxbot_messages`, `taxbot_query_usage`

### Plan Options

| Plan     | Monthly Cost | DB Storage | MAU Limit  | Backups        | Key Feature          |
|:---------|:-------------|:-----------|:-----------|:---------------|:---------------------|
| **Free** | $0           | 500 MB     | 50,000     | None           | Pauses after 7d idle |
| **Pro**  | $25          | 8 GB       | 100,000    | 7-day          | Always-on, no pause  |
| **Team** | $599         | 8 GB       | 100,000    | 14-day         | SOC2, SSO, SLA       |

### Storage Estimate

| Data Type           | Estimate per Month                               | Size        |
|:--------------------|:-------------------------------------------------|:------------|
| User records        | 7,000 rows × ~0.5 KB                             | ~3.5 MB     |
| Session records     | ~3,500 users/day × 1 session × 30 days = 105K    | ~21 MB      |
| Messages            | 315K queries × 2 messages (Q+A) × ~2 KB          | ~1.26 GB    |
| Query usage logs    | 315K records × ~0.2 KB                            | ~63 MB      |
| **Total (monthly growth)** | —                                          | **~1.35 GB**|

> [!WARNING]
> The Free plan's 500 MB storage limit will be exceeded within the **first month** of production. The Pro plan's 8 GB limit provides ~6 months of headroom before needing cleanup or archival.

| Plan Recommended    | Monthly Cost |
|:--------------------|:------------:|
| **Pro Plan**        | **$25**      |

> [!TIP]
> **Cost Optimization**: Implement a message archival policy — delete messages older than 90 days. This keeps storage under 4 GB indefinitely and avoids Supabase overage charges.

---

## 4️⃣ App Hosting — Backend + Frontend Deployment

TaxBot has two deployable components:
- **Backend**: Python FastAPI server (handles RAG queries, Gemini API calls)
- **Frontend**: Next.js web application (user chat interface)

### Hosting Options Compared

| Provider          | Backend Cost | Frontend Cost | Total    | Pros                                    | Cons                              |
|:------------------|:-------------|:--------------|:---------|:----------------------------------------|:----------------------------------|
| **Render**        | $7–25/mo     | $0–7/mo       | **$7–32**| Predictable pricing, no cold starts (paid) | No India region (150ms+ latency) |
| **Railway**       | $5–20/mo     | $5–20/mo      | **$10–40**| Git-push deploy, great DX              | Usage-based, can spike            |
| **Vercel + Render**| $25/mo (Render) | $20/mo (Vercel)| **$45** | Best-in-class Next.js hosting          | Two providers to manage           |
| **Google Cloud Run**| $0–50/mo   | $0 (static)   | **$0–50**| Same ecosystem as Gemini, auto-scale   | Steeper learning curve            |

### Recommended Setup

| Component   | Provider              | Plan               | Monthly Cost |
|:------------|:----------------------|:-------------------|:------------:|
| **Backend** | Render (Standard)     | 1 CPU, 2 GB RAM    | **$25**      |
| **Frontend**| Render (Starter)      | Static/0.5 CPU     | **$7**       |
| **Total**   | —                     | —                  | **$32**      |

> [!TIP]
> **Alternative (Cheapest)**: Use **Google Cloud Run** for the backend (same Google ecosystem as Gemini). With 315K requests/month and ~500ms average response time, you'd stay within the free tier or pay ~$10–$15/month. Frontend can be deployed as a static export on Cloud Storage for ~$1/month.

---

## 5️⃣ Domain & SSL (Optional but Recommended)

| Service             | Provider       | Annual Cost   | Monthly Equivalent |
|:--------------------|:---------------|:--------------|:------------------:|
| Custom domain       | GoDaddy/Namecheap | $10–$15/year | **~$1**           |
| SSL Certificate     | Let's Encrypt  | Free           | **$0**            |
| **Domain Total**    | —              | —              | **~$1**           |

---

## 📋 Complete Monthly Cost Summary

### Scenario A: Budget-Optimized (Recommended to Start)

| #  | Service                    | Provider       | Plan           | Monthly Cost  |
|:--:|:---------------------------|:---------------|:---------------|:-------------:|
| 1  | Gemini Chat LLM            | Google AI      | Pay-as-you-go  | $732.38       |
| 2  | Gemini Embeddings          | Google AI      | Pay-as-you-go  | $3.15         |
| 3  | Vector Database            | Pinecone       | **Starter (Free)** | $0        |
| 4  | Relational Database        | Supabase       | **Pro**        | $25.00        |
| 5  | Backend Hosting            | Render         | Standard       | $25.00        |
| 6  | Frontend Hosting           | Render         | Starter        | $7.00         |
| 7  | Domain + SSL               | Namecheap + LE | Annual         | ~$1.00        |
|    | **TOTAL (Budget)**         |                |                | **$793.53**   |
|    | *With Context Caching*     |                |                | *~$655–$725*  |

---

### Scenario B: Production-Grade (With SLA & Redundancy)

| #  | Service                    | Provider       | Plan           | Monthly Cost  |
|:--:|:---------------------------|:---------------|:---------------|:-------------:|
| 1  | Gemini Chat LLM            | Google AI      | Pay-as-you-go  | $732.38       |
| 2  | Gemini Embeddings          | Google AI      | Pay-as-you-go  | $3.15         |
| 3  | Vector Database            | Pinecone       | **Standard**   | $50.00        |
| 4  | Relational Database        | Supabase       | **Pro**        | $25.00        |
| 5  | Backend Hosting            | Render         | Pro (2 CPU)    | $85.00        |
| 6  | Frontend Hosting           | Vercel         | Pro            | $20.00        |
| 7  | Domain + SSL               | Namecheap + LE | Annual         | ~$1.00        |
|    | **TOTAL (Production)**     |                |                | **$916.53**   |
|    | *With Context Caching*     |                |                | *~$780–$850*  |

---

### Scenario C: Maximum Savings (Google Cloud Ecosystem)

| #  | Service                    | Provider        | Plan           | Monthly Cost  |
|:--:|:---------------------------|:----------------|:---------------|:-------------:|
| 1  | Gemini Chat LLM            | Google AI       | Pay-as-you-go  | $732.38       |
| 2  | Gemini Embeddings          | Google AI       | Pay-as-you-go  | $3.15         |
| 3  | Vector Database            | Pinecone        | **Starter (Free)** | $0        |
| 4  | Relational Database        | Supabase        | **Pro**        | $25.00        |
| 5  | Backend Hosting            | Cloud Run       | Pay-as-you-go  | ~$12.00       |
| 6  | Frontend Hosting           | Cloud Storage   | Static hosting | ~$1.00        |
| 7  | Domain + SSL               | Namecheap + LE  | Annual         | ~$1.00        |
|    | **TOTAL (Max Savings)**    |                 |                | **~$774.53**  |
|    | *With Context Caching*     |                 |                | *~$638–$708*  |

---

## 📈 Cost Scaling by User Count

How monthly costs scale as your active user base grows:

| Active Users/Day | Queries/Month | Gemini LLM Cost | Gemini Embed Cost | Total Estimated |
|:-----------------|:--------------|:-----------------|:------------------|:----------------|
| 500              | 45,000        | ~$105            | ~$0.45            | **~$171**       |
| 1,000            | 90,000        | ~$209            | ~$0.90            | **~$276**       |
| 2,000            | 180,000       | ~$418            | ~$1.80            | **~$487**       |
| **3,500 (target)** | **315,000** | **~$732**        | **~$3.15**        | **~$794**       |
| 5,000            | 450,000       | ~$1,047          | ~$4.50            | **~$1,109**     |
| 7,000            | 630,000       | ~$1,465          | ~$6.30            | **~$1,530**     |
| 10,000           | 900,000       | ~$2,093          | ~$9.00            | **~$2,160**     |

> [!NOTE]
> Gemini API costs scale **linearly** with query volume. All other services (Pinecone, Supabase, Hosting) remain mostly fixed until you exceed ~10,000 active users/day.

---

## 💡 Cost Optimization Strategies

### Immediate Savings (No Code Changes)

| Strategy                  | Potential Savings | How                                                    |
|:--------------------------|:------------------|:-------------------------------------------------------|
| **Context Caching**       | 15–20% off Gemini | Cache system prompt + frequent doc chunks               |
| **Batch API for Suggestions** | 50% off follow-ups | Use async Batch API instead of real-time for suggestions |
| **Reduce query limit**   | Up to 33%          | Change from 3 to 2 queries/day for basic users         |

### Medium-Term Savings (Code Changes)

| Strategy                     | Potential Savings | How                                                    |
|:-----------------------------|:------------------|:-------------------------------------------------------|
| **Use Flash-Lite for suggestions** | ~$98/month  | Use cheaper `gemini-2.5-flash-lite` ($0.10/$0.40) for follow-up suggestions only |
| **Smart chunking**           | ~10% off Gemini   | Reduce context from 18 chunks to 10 highest-scoring    |
| **Answer caching (Redis)**   | 5–15% off Gemini  | Cache answers for identical or near-identical questions |

### With All Optimizations Applied

| Configuration                          | Estimated Monthly Total |
|:---------------------------------------|:-----------------------:|
| Base (Budget Scenario A)               | $793.53                |
| + Context caching                      | ~$720                  |
| + Flash-Lite for suggestions           | ~$622                  |
| + Batch API for suggestions            | ~$560                  |
| + Reduce to 2 queries/day             | ~$420                  |
| **Fully Optimized**                    | **~$380–$430/month**   |

---

## 🔐 Accounts & Credentials Checklist

| Service         | Account Email             | Dashboard URL                               | Keys Needed                       |
|:----------------|:--------------------------|:--------------------------------------------|:----------------------------------|
| Google AI Studio| `taxbot0807@gmail.com`    | https://aistudio.google.com/                | `GEMINI_API_KEY`                  |
| Pinecone        | `taxbot0807@gmail.com`    | https://console.pinecone.io/               | `PINECONE_API_KEY`                |
| Supabase        | `taxbot0807@gmail.com`    | https://supabase.com/dashboard/             | `SUPABASE_URL`, `SUPABASE_KEY`    |
| Render/Vercel   | `taxbot0807@gmail.com`    | https://dashboard.render.com/               | Git integration                   |
| Domain Registrar| `taxbot0807@gmail.com`    | Provider dashboard                           | DNS records                       |

### Production `.env` File Template

```ini
# --- Core API Keys ---
GEMINI_API_KEY=your_gemini_api_key_here
PINECONE_API_KEY=your_pinecone_api_key_here

# --- LLM Configuration ---
LLM_PROVIDER=gemini
GEMINI_CHAT_MODEL=gemini-2.5-flash
GEMINI_EMBED_MODEL=gemini-embedding-2

# --- Supabase Database ---
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your-supabase-service-role-key

# --- Application ---
TAXBOT_JWT_SECRET=your-long-random-jwt-secret
```

---

## 🎯 Final Recommendation

> [!IMPORTANT]
> **Start with Scenario A (Budget-Optimized) at ~$794/month.** This gives you full production capability with Gemini 2.5 Flash, Pinecone free tier, and Supabase Pro. As you onboard users, implement Context Caching first (easiest win), then gradually apply other optimizations to bring costs below **$430/month**.

### Monthly Payment Schedule

| Service          | Billing Type      | When to Pay                    |
|:-----------------|:------------------|:-------------------------------|
| Google Gemini    | Pay-as-you-go     | Charged monthly to card on file |
| Pinecone         | Free / Monthly    | First of each month            |
| Supabase         | Monthly           | First of each month            |
| Render/Vercel    | Monthly           | First of each month            |
| Domain           | Annual            | Once per year                  |

---

*Document created: July 2026 · Prices based on published rates as of July 2026.*
*Prices may vary. Always verify on official pricing pages before committing.*
