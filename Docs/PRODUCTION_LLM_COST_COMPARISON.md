# TaxBot Production LLM Cost Comparison: Gemini API vs Self-Hosted Ollama

> **Target Scale**: 6,000–7,000 registered users, ~3,000–3,500 concurrent active users, **3 queries/day limit** per user.

---

## 📊 Usage Assumptions

| Parameter                        | Value                     |
|:---------------------------------|:--------------------------|
| Total registered users           | 7,000                     |
| Active users per day             | ~5,000 (assumed 70%)      |
| Queries per user per day         | 3 (hard limit)            |
| **Total queries per day**        | **15,000**                |
| **Total queries per month**      | **450,000**               |
| Follow-up suggestion calls/query | 1 (AI-generated)          |
| Embedding calls per query        | 1                         |
| **Total LLM calls per month**    | **900,000** (query + suggestion) |
| **Total embedding calls per month** | **450,000**            |

### Token Estimates per Query

| Component                | Tokens        |
|:-------------------------|:--------------|
| User question (input)    | ~50 tokens    |
| RAG context chunks (input) | ~2,000 tokens |
| System prompt (input)    | ~200 tokens   |
| **Total input per LLM call** | **~2,250 tokens** |
| **Output per LLM call**  | **~500 tokens** |
| Follow-up input          | ~500 tokens   |
| Follow-up output         | ~100 tokens   |
| Embedding input          | ~50 tokens    |

---

## 💰 Option A: Gemini API (Pay-as-you-go)

We have three viable Gemini model tiers to choose from. Here is the cost breakdown for each:

### A1: Gemini 2.5 Flash-Lite (Best Value — Recommended)

| Metric | Input | Output |
|:---|:---|:---|
| **Price** | $0.10 / 1M tokens | $0.40 / 1M tokens |

**Main Query LLM Cost:**
- Monthly input tokens: 450,000 × 2,250 = **1,012.5M tokens**
- Monthly output tokens: 450,000 × 500 = **225M tokens**
- Input cost: 1,012.5 × $0.10 = **$101.25**
- Output cost: 225 × $0.40 = **$90.00**

**Follow-up Suggestion Cost:**
- Input tokens: 450,000 × 500 = **225M tokens**
- Output tokens: 450,000 × 100 = **45M tokens**
- Input cost: 225 × $0.10 = **$22.50**
- Output cost: 45 × $0.40 = **$18.00**

**Embedding Cost (text-embedding-004):**
- **FREE** (Google does not charge for text-embedding-004)

| Component | Monthly Cost |
|:--|--:|
| Main query LLM | $191.25 |
| Follow-up suggestions | $40.50 |
| Embeddings | $0.00 |
| **Total** | **$231.75/month** |

---

### A2: Gemini 3 Flash (Higher Accuracy, 5× cost)

| Metric | Input | Output |
|:---|:---|:---|
| **Price** | $0.50 / 1M tokens | $3.00 / 1M tokens |

| Component | Monthly Cost |
|:--|--:|
| Main query input | $506.25 |
| Main query output | $675.00 |
| Follow-up input | $112.50 |
| Follow-up output | $135.00 |
| Embeddings | $0.00 |
| **Total** | **$1,428.75/month** |

---

### A3: Gemini 3.5 Flash (Frontier Accuracy, 15× cost)

| Metric | Input | Output |
|:---|:---|:---|
| **Price** | $1.50 / 1M tokens | $9.00 / 1M tokens |

| Component | Monthly Cost |
|:--|--:|
| Main query input | $1,518.75 |
| Main query output | $2,025.00 |
| Follow-up input | $337.50 |
| Follow-up output | $405.00 |
| Embeddings | $0.00 |
| **Total** | **$4,286.25/month** |

---

## 🖥️ Option B: Self-Hosted Ollama (Llama 3.1 8B + nomic-embed-text)

Self-hosting means renting cloud GPU servers to run the models 24/7.

### Peak Load Calculation
- Peak window: 8 hours of activity
- Peak queries: 15,000 queries in 8 hours ≈ **~0.5 queries/second** average
- Burst peak (3× average): **~1.5 queries/second**
- Llama 3.1 8B on A10G: ~15–25 tokens/sec per request, can handle ~5–8 concurrent requests
- **Minimum requirement: 1× A10G GPU server** (with headroom)
- **Recommended for production: 2× GPU servers** (redundancy + load balancing)

### Cloud GPU Costs (Monthly, On-Demand, 24/7)

| Provider | GPU | Hourly Rate | Monthly (730 hrs) |
|:---------|:----|:------------|:-------------------|
| AWS (g5.xlarge) | A10G | $0.80/hr | **$584** |
| Lambda Cloud | A10G | $0.60/hr | **$438** |
| RunPod | A10G | $0.50/hr | **$365** |
| Vast.ai | A10G | $0.35–0.50/hr | **$255–$365** |
| AWS (g5.2xlarge) | A10G | $1.00/hr | **$730** |

### Realistic Production Setup

| Component | Provider | Monthly Cost |
|:----------|:---------|:-------------|
| Primary LLM Server (1× A10G) | RunPod/Lambda | $365–$438 |
| Failover/Redundancy Server (1× A10G) | RunPod/Lambda | $365–$438 |
| CPU Server for API/Load Balancer | Any cloud | $30–$60 |
| Storage & Networking | Any cloud | $20–$40 |
| DevOps/Monitoring tools | — | $0–$30 |
| **Total (Minimum – 1 server)** | | **$415–$530/month** |
| **Total (Recommended – 2 servers)** | | **$780–$1,000/month** |

---

## 📈 Head-to-Head Comparison

| Factor | Gemini 2.5 Flash-Lite (API) | Self-Hosted Ollama (Llama 3.1 8B) |
|:-------|:----------------------------|:-----------------------------------|
| **Monthly Cost** | **~$232** ✅ | **$415–$1,000** |
| **Accuracy** | **Higher** (frontier-class reasoning) ✅ | Lower (8B parameter model) |
| **Scalability** | Auto-scales to any load ✅ | Fixed capacity, need more GPUs |
| **Uptime SLA** | 99.9% Google SLA ✅ | Self-managed, no SLA |
| **DevOps Required** | None (API call) ✅ | Significant (server management, monitoring, restarts, CUDA drivers) |
| **Latency** | ~1–3s (streaming) | ~2–5s (depends on GPU load) |
| **Data Privacy** | Data sent to Google's servers | Data stays on your servers ✅ |
| **Vendor Lock-in** | Moderate (can switch to other APIs easily) | None ✅ |
| **Setup Time** | 5 minutes (API key) ✅ | Days (server provisioning, model setup, load testing) |
| **Model Updates** | Automatic from Google ✅ | Manual download & restart |
| **Context Caching** | Available (up to 90% savings possible) ✅ | Not available |

---

## ✅ Recommendation: **Gemini 2.5 Flash-Lite** (Option A1)

**Why?**
1. **~57% cheaper** than the cheapest self-hosted option ($232 vs $415+).
2. **Significantly more accurate** than Llama 3.1 8B for Indian tax law reasoning.
3. **Zero DevOps burden** — no GPU management, no CUDA driver updates, no server monitoring.
4. **Auto-scales** — if your user count grows from 7,000 to 70,000, the API handles it. With self-hosting, you'd need to provision 10× more GPUs.
5. **Free embeddings** — `text-embedding-004` costs $0.
6. **Context Caching** — For repeating system prompts and legal document chunks, caching can reduce costs by another 50–90%.

> **With context caching enabled, the realistic monthly cost could drop to $120–$150/month.**

---

## 🚀 Step-by-Step Guide to Proceed with Gemini 2.5 Flash-Lite

### Step 1: Set Up Google AI Studio Billing
1. Go to [Google AI Studio](https://aistudio.google.com/) → Sign in with `taxbot0807@gmail.com`.
2. Navigate to **Settings → Plan & Billing**.
3. Click **Upgrade** or **Set up billing** → Add a credit/debit card.
4. Select the **Pay-as-you-go** plan (no upfront commitment).
5. Copy your **API Key** from the API Keys section.

### Step 2: Update Your `.env` File
```ini
GEMINI_API_KEY=your_new_gemini_api_key_here
PINECONE_API_KEY=your_new_pinecone_api_key_here

# Switch from Ollama to Gemini
LLM_PROVIDER=gemini

# Supabase
SUPABASE_URL=https://vuebswpssjubjllazqjh.supabase.co
SUPABASE_KEY=your_supabase_key_here
```

### Step 3: Update the LLM Model in Backend Code
In `backend/main.py`, update the model used for query responses to `gemini-2.5-flash-lite`:
- The `generate_grounded_response_stream` function currently uses `gemini-1.5-flash`.
- Change it to `gemini-2.5-flash-lite` for the optimal cost/performance balance.

### Step 4: Update the Embedding Model
In `backend/main.py` and `backend/ingestion.py`:
- The code already uses `text-embedding-004` when `LLM_PROVIDER=gemini`.
- No changes needed here — it's free.

### Step 5: Re-run Ingestion
1. Go to **Admin Panel** (`http://localhost:3000/admin`).
2. Click **🚀 Start Ingestion** to re-embed all documents using Gemini's `text-embedding-004` model (instead of Ollama's `nomic-embed-text`).
3. This ensures your Pinecone vectors match the query-time embedding model.

### Step 6: Test and Validate
1. Open the TaxBot chat interface.
2. Ask a few test questions about Indian Income Tax.
3. Verify that responses are accurate, fast, and properly sourced.
4. Check the Admin Panel to confirm chat sessions are being stored in Supabase.

### Step 7: Monitor Usage & Costs
1. Go to [Google Cloud Console](https://console.cloud.google.com/) → **Billing** → **Reports**.
2. Monitor daily API spend.
3. Set up **budget alerts** (e.g., alert at $200/month) to avoid surprises.

---

## 💡 Additional Cost Optimization Tips

1. **Context Caching**: Cache the system prompt and frequently retrieved document chunks. This can reduce input token costs by up to 90%.
2. **Batch API**: If follow-up suggestions don't need real-time responses, use Google's Batch API for 50% discount on those calls.
3. **Rate Limiting**: The 3 queries/day limit already caps your costs. Consider reducing it to 2 for basic-tier users.
4. **Model Downgrade for Suggestions**: Use `gemini-2.5-flash-lite` for follow-up suggestions (lightweight task) even if you upgrade the main query model later.
