# 📖 TaxBot — AI & Production Terminology Guide

> A practical reference of every term you'll encounter while managing, optimizing, and scaling TaxBot's AI infrastructure. Each term is explained in plain language with a direct connection to how it affects **your costs and system behavior**.

---

## 🧠 Core LLM Concepts

### Token

The fundamental unit of text that an AI model reads and writes. A token is **not** a word — it's a sub-word fragment that the model's internal dictionary (called a "tokenizer") breaks text into.

**Rules of Thumb:**
- 1 token ≈ **¾ of a word** in English
- 100 tokens ≈ **75 words**
- 1,000 tokens ≈ one full page of text

**Example:**
```
"The Income-tax Act, 2025" → ["The", " Income", "-", "tax", " Act", ",", " 2025"]
                            = 7 tokens
```

**Why It Matters for TaxBot:**
Every API call to Gemini is billed per token. The more tokens you send in (input) and receive back (output), the higher your monthly bill. This is the single most important unit for cost estimation.

---

### Input Tokens (Prompt Tokens)

The tokens you **send to** the model. For TaxBot, this includes three parts:

| Part               | Example                                     | ~Tokens |
|:--------------------|:---------------------------------------------|:--------|
| System Prompt       | "You are an expert Tax Law Assistant..."     | ~200    |
| RAG Context Chunks  | Retrieved document passages from Pinecone    | ~2,000  |
| User Question       | "What is the definition of Tax Year?"        | ~50     |
| **Total Input**     |                                               | **~2,250** |

**Cost Impact:** Gemini 2.5 Flash charges **$0.30 per 1M input tokens**. Input tokens are the largest volume component of your bill.

---

### Output Tokens (Completion Tokens)

The tokens the model **generates back** to you — i.e., the answer it writes.

**Example:**
```
"Under the new Act, the definition of a 'tax year' means the twelve-month
period of the financial year..." → ~50 tokens
```

**Cost Impact:** Gemini 2.5 Flash charges **$2.50 per 1M output tokens** — that's **8.3× more expensive** than input tokens. This is why shorter, more precise answers save significantly more money than reducing input size.

---

### Context Window (Context Length)

The maximum number of tokens a model can process in a **single request** (input + output combined).

| Model              | Context Window      |
|:--------------------|:--------------------|
| Gemini 2.5 Flash    | **1,048,576 tokens** (1M) |
| Llama 3.1 8B        | 128,000 tokens      |
| GPT-4o              | 128,000 tokens      |

**Why It Matters:**
Gemini's 1M token context window means you could theoretically feed it an **entire 800-page PDF** in one request. However, more context ≠ better answers — it means more input tokens billed. The sweet spot for TaxBot is sending only the most relevant ~18 chunks (~2,000 tokens).

---

### Temperature

A number between **0.0 and 2.0** that controls how "creative" vs "deterministic" the model's output is.

| Temperature | Behavior                | Best For                        |
|:------------|:------------------------|:--------------------------------|
| **0.0**     | Always picks the most probable next word. Deterministic — same input gives same output. | Legal/tax answers, factual Q&A |
| **0.3–0.7** | Some randomness. Varies output slightly each time. | Creative writing, summaries |
| **1.0+**    | High randomness. Output can be unpredictable. | Brainstorming, poetry |

**TaxBot Uses: `temperature = 0.0`** because tax law requires factual, reproducible answers. If a user asks the same question twice, they should get the same answer.

**Side Effect:** At `temperature = 0.0`, the model can sometimes generate an `<EOS>` token prematurely (see below), causing answers to cut off mid-sentence.

---

### EOS Token (End-of-Sequence)

A special invisible token that tells the model **"stop generating now."** Every LLM has one built into its vocabulary.

**How It Works:**
```
Model output: "The tax year is defined as" → [next token probabilities]
  "the"    → 45% probability
  "a"      → 30% probability
  "<EOS>"  → 25% probability ← if this wins, generation stops HERE
```

At `temperature = 0.0`, the model always picks the single highest-probability token. If `<EOS>` happens to be the most probable next token at any point, the model immediately stops — even mid-sentence.

**Why TaxBot Answers Sometimes Cut Off:**
This is exactly what happens when you see an answer like:
> *"Under the new Act, the definition of a 'tax year' means the twelve-month period of the"*

The model predicted `<EOS>` as the most likely next token and stopped. Raising `temperature` to `0.1–0.2` or increasing `max_output_tokens` can help mitigate this.

---

### Max Output Tokens

A hard cap on **how many tokens** the model is allowed to generate in its response. If the model hasn't produced an `<EOS>` token by this limit, it is forcefully cut off.

**TaxBot's Current Setting:** `max_output_tokens = 1024` (~750 words)

| Setting          | Effect                                                     |
|:-----------------|:-----------------------------------------------------------|
| Too low (256)    | Answers will be truncated frequently                       |
| Sweet spot (1024–2048) | Enough for detailed tax answers with citations       |
| Too high (8192)  | Model may ramble; costs more if it generates long responses |

**Cost Impact:** Higher `max_output_tokens` doesn't cost more **unless the model actually generates more text**. It's just a ceiling, not a guarantee.

---

### Finish Reason

When a model stops generating, it reports **why** it stopped. This is critical for debugging cut-off answers.

| Finish Reason    | Meaning                                             | TaxBot Action             |
|:-----------------|:----------------------------------------------------|:--------------------------|
| `STOP`           | Model naturally finished (hit `<EOS>`)               | ✅ Normal — answer complete |
| `MAX_TOKENS`     | Hit the `max_output_tokens` limit                    | ⚠️ Answer was truncated    |
| `SAFETY`         | Model refused due to safety filters                  | ❌ Review the prompt       |
| `RECITATION`     | Model detected it was copying verbatim from training | ⚠️ Rephrase the question  |

---

### System Prompt (System Instruction)

A special message sent at the **beginning** of every API call that defines the model's behavior, personality, and rules. It is invisible to the end-user.

**TaxBot's System Prompt:**
```
"You are an expert Tax Law Assistant operating under strict 'Open-Book' guidelines.
Your task is to answer the user's question using ONLY the provided Source passages.
CRITICAL RULES:
1. If the provided Source passages do not contain information related to the question,
   you must respond: 'I cannot find the answer to this question in the provided tax documents.'
..."
```

**Cost Impact:** This ~200-token prompt is sent with **every single API call** — that's 315,000 copies/month. With Context Caching (see below), you can cache it once and pay only 10% of the input cost for subsequent calls.

---

### Streaming

Instead of waiting for the **entire** response to be generated before showing it, streaming delivers tokens **one by one** as they're produced — creating the "typing" effect you see in ChatGPT and TaxBot.

**How TaxBot Uses It:**
```
Backend sends:  {"event": "content", "text": "The"}
Backend sends:  {"event": "content", "text": " tax"}
Backend sends:  {"event": "content", "text": " year"}
Backend sends:  {"event": "content", "text": " is"}
...
Backend sends:  {"event": "done"}
```

**Cost Impact:** None. Streaming doesn't change the total tokens generated — it just changes **when** the user sees them. Same bill whether streamed or not.

---

## 📚 RAG (Retrieval-Augmented Generation) Concepts

### RAG

**Retrieval-Augmented Generation** — the architecture pattern TaxBot uses. Instead of relying on the model's training data (which may be outdated or wrong), we **retrieve** relevant document passages first, then **augment** the prompt with them before **generating** an answer.

**TaxBot's RAG Flow:**
```
User Question → Embed Question → Search Pinecone → Get Top 18 Chunks
→ Inject Chunks into Prompt → Send to Gemini → Stream Answer Back
```

**Why RAG?** Without RAG, asking Gemini "What is Section 44AD?" would give you a generic (and potentially outdated) answer. With RAG, Gemini reads the **actual 2025 Act text** you uploaded and answers based on that.

---

### Chunking

The process of breaking large documents into smaller, overlapping pieces ("chunks") that can be individually embedded and searched.

**Why Not Embed Entire PDFs?**
- A 900-page PDF has ~500,000 tokens — far too large for a single embedding
- Search precision drops when chunks are too large (the embedding becomes a blurry average)
- Smaller chunks = more precise retrieval = better answers

**TaxBot's Chunking Strategy:**
| Parameter         | Value      |
|:-------------------|:-----------|
| Chunk size         | ~500 chars |
| Overlap            | ~100 chars |
| Total chunks       | ~9,200     |
| Avg tokens/chunk   | ~75        |

**The overlap** ensures that if a sentence spans two chunks, at least one chunk will contain the complete sentence.

---

### Embedding (Dense Embedding)

A mathematical representation of text as a **list of numbers** (a "vector"). Texts with similar meanings produce vectors that are close together in high-dimensional space.

**Example:**
```
"Income tax rate"     → [0.12, -0.45, 0.78, ..., 0.33]  (768 numbers)
"Tax on earnings"     → [0.11, -0.44, 0.79, ..., 0.34]  (very similar!)
"Weather forecast"    → [0.92, 0.15, -0.67, ..., -0.88] (completely different)
```

**TaxBot Uses Two Embedding Models:**

| Model              | Used For              | Dimension | Cost           |
|:--------------------|:----------------------|:----------|:---------------|
| Gemini Embedding-2  | Production (Gemini)   | 768       | $0.20/1M tokens |
| nomic-embed-text     | Local dev (Ollama)    | 768       | Free (local)   |

> ⚠️ **Critical Rule:** The embedding model used at **ingestion time** (to store chunks) must be the **same model** used at **query time** (to search). Mixing models (e.g., storing with nomic, searching with Gemini) produces garbage results because the vector spaces don't align.

---

### Sparse Embedding (BM25)

A traditional keyword-based search technique that scores documents by **exact word matches**, weighted by how rare each word is.

**How BM25 Differs from Dense Embeddings:**

| Feature          | Dense Embedding (Gemini) | Sparse Embedding (BM25) |
|:-----------------|:-------------------------|:------------------------|
| Understands meaning | ✅ Yes ("tax" ≈ "levy") | ❌ No (exact words only) |
| Handles typos    | ✅ Somewhat               | ❌ No                   |
| Finds exact terms | ⚠️ Sometimes misses      | ✅ Excellent             |
| Cost             | API call required         | Free (local computation)|

**TaxBot combines both** in a "Hybrid Search" to get the best of both worlds.

---

### Hybrid Search

Combining dense embeddings (semantic meaning) and sparse embeddings (keyword matching) into a single search result. TaxBot uses an **alpha parameter** to control the blend:

```
final_score = alpha × dense_score + (1 - alpha) × sparse_score
```

| Alpha Value | Behavior                                        |
|:------------|:------------------------------------------------|
| `alpha = 1.0` | 100% semantic search (ignore keywords)        |
| `alpha = 0.5` | Equal blend of semantic + keyword (TaxBot default) |
| `alpha = 0.0` | 100% keyword search (ignore meaning)          |

---

### Vector Database

A specialized database designed to store and search embedding vectors at scale. Unlike traditional databases (SQL) that search by exact field values, vector databases find the **most similar** vectors using mathematical distance.

**TaxBot uses Pinecone** — a cloud-hosted serverless vector database.

| Concept      | Meaning in Pinecone Context                        |
|:-------------|:---------------------------------------------------|
| **Index**    | A named collection of vectors (like a SQL table)   |
| **Namespace**| A partition within an index (for multi-tenancy)    |
| **Upsert**   | Insert or update vectors (Write Unit)              |
| **Query**    | Search for similar vectors (Read Unit)             |
| **Read Unit (RU)**  | Billing unit for search operations           |
| **Write Unit (WU)** | Billing unit for insert/update operations    |

---

### Top-K

The number of most-similar document chunks to retrieve from the vector database for each query.

**TaxBot's Setting:** `top_k = 5` per search type (dense + sparse), resulting in **~18 unique chunks** after hybrid merge and deduplication.

| top_k Value | Effect                                              | Cost Impact           |
|:------------|:----------------------------------------------------|:----------------------|
| Low (3)     | Faster, cheaper (fewer input tokens), may miss info | ~1,200 input tokens   |
| Default (5) | Balanced                                             | ~2,000 input tokens   |
| High (10)   | More context, slower, more expensive                 | ~4,000 input tokens   |

**Cost Optimization:** Reducing `top_k` from 5 to 3 would cut your RAG context tokens by ~40%, saving ~$85/month on input costs.

---

## 💰 Cost Optimization Concepts

### Context Caching

A Gemini API feature where you **pre-upload** content (like your system prompt or frequently used document chunks) to Google's servers. Subsequent API calls that reference the cached content are charged at **~10% of the normal input token rate**.

**How It Works:**
```
Step 1: Cache the system prompt (200 tokens) → stored on Google's servers
Step 2: Every API call references the cache instead of sending 200 tokens
Step 3: Billed at $0.03/1M tokens instead of $0.30/1M tokens (90% savings!)
```

**Potential Savings for TaxBot:**
- System prompt alone: 315,000 calls × 200 tokens = 63M tokens/month
- Without caching: 63 × $0.30 = $18.90/month
- With caching: 63 × $0.03 = $1.89/month
- **Savings: ~$17/month** (on system prompt alone)

If you also cache frequently retrieved document chunks, savings scale dramatically.

> **Cache Lifetime:** Caches expire after a configurable TTL (time-to-live). Google charges a small hourly storage fee for maintaining caches.

---

### Batch API

A Gemini API feature for **non-real-time** workloads. Instead of sending requests one-by-one and waiting for immediate responses, you submit a batch of requests and Google processes them within a **24-hour window** at a **50% discount**.

**TaxBot Use Case:** Follow-up suggestions don't need instant responses — they can be pre-generated in the background.

| API Type     | Response Time | Cost         |
|:-------------|:--------------|:-------------|
| Standard API | ~1–5 seconds  | Full price   |
| Batch API    | Up to 24 hours| **50% off**  |

**Potential Savings:** Follow-up suggestions cost ~$126/month. With Batch API: ~$63/month → **$63/month saved**.

---

### Rate Limiting

Artificial caps on how many API requests a user or application can make within a time period. Rate limits exist at **two levels** in TaxBot:

**1. Google's API Rate Limits (Provider-Side):**

| Tier        | Gemini 2.5 Flash Limit              |
|:------------|:-------------------------------------|
| Free Tier   | 15 RPM, 1,500 RPD, 100K TPM         |
| Pay-as-you-go | 2,000 RPM, unlimited RPD, 4M TPM |

*RPM = Requests Per Minute, RPD = Requests Per Day, TPM = Tokens Per Minute*

**2. TaxBot's User Rate Limit (Application-Side):**
- **3 queries/day per user** — enforced in `taxbot_query_usage` table in Supabase
- This caps your maximum possible spend regardless of user count

**Cost Impact:** Your rate limit is your **cost ceiling**. At 3 queries/day × 3,500 users = 10,500 queries/day maximum. Reducing to 2 queries/day instantly cuts Gemini costs by 33%.

---

### RPM / RPD / TPM

Standard abbreviations used in API documentation:

| Abbreviation | Full Form                 | Meaning                              |
|:-------------|:--------------------------|:-------------------------------------|
| **RPM**      | Requests Per Minute        | Max API calls allowed per minute     |
| **RPD**      | Requests Per Day           | Max API calls allowed per 24 hours   |
| **TPM**      | Tokens Per Minute          | Max tokens processed per minute      |
| **TPD**      | Tokens Per Day             | Max tokens processed per 24 hours    |

**The Free Tier's biggest limitation** is RPD — only 20 requests per day for Gemini 2.5 Flash, which is why TaxBot hit 429 errors almost instantly during testing.

---

### 429 Error (Rate Limit Exceeded)

An HTTP status code meaning **"Too Many Requests."** The API is telling you: *"Slow down, you've exceeded your quota."*

**TaxBot Experience:**
```
429 You exceeded your current quota
Quota exceeded for: generativelanguage.googleapis.com/generate_content_free_tier_requests
Limit: 20, model: gemini-2.5-flash
Please retry in 49.234988982s
```

**How to Avoid:**
1. **Upgrade to pay-as-you-go** billing (removes RPD limits)
2. Implement **exponential backoff** (retry after progressively longer delays)
3. Use **request queuing** to smooth out burst traffic

---

## 🏗️ Infrastructure Concepts

### Serverless

A deployment model where **you don't manage servers**. The cloud provider automatically provisions, scales, and bills resources based on actual usage. You pay only when your code runs.

**TaxBot's Serverless Services:**
- **Pinecone** (serverless vector DB — scales to zero when idle)
- **Supabase** (managed PostgreSQL — always-on but auto-managed)
- **Google Cloud Run** (optional — FastAPI backend that scales to zero)

**Opposite:** Self-hosted Ollama (you rent a GPU server 24/7 whether anyone is using it or not).

---

### Cold Start

The delay that occurs when a serverless function "wakes up" after being idle. Since the service scaled to zero to save money, the first request must wait for the container to spin up.

| Service        | Cold Start Time  | Impact                  |
|:---------------|:-----------------|:------------------------|
| Cloud Run      | 2–10 seconds     | First user of the day waits |
| Render (Free)  | 30–60 seconds    | Unacceptable for production |
| Render (Paid)  | 0 seconds        | Always-on, no cold starts   |
| Pinecone       | ~100ms           | Negligible               |

**Cost Trade-off:** Paying for an "always-on" instance ($7–25/month) eliminates cold starts. Serverless is cheaper but adds latency.

---

### Ingestion

The one-time (or periodic) process of converting your raw documents (PDFs, PPTs, VTTs) into searchable vector embeddings stored in Pinecone.

**TaxBot's Ingestion Pipeline:**
```
PDF/PPT/VTT → Parse Text → Split into Chunks (~9,200)
→ Generate Dense Embeddings (Gemini/Ollama)
→ Generate Sparse Embeddings (BM25)
→ Upsert to Pinecone Index
→ Save BM25 Model (bm25_ollama.json)
```

**Cost:** Ingestion is a **one-time cost** (~$0.14 with Gemini Embedding-2). It only needs to be re-run when you add or update documents.

> ⚠️ **Important:** The BM25 model (`bm25_ollama.json`) is generated during ingestion and must be deployed alongside the backend. Without it, sparse search fails and retrieval quality drops significantly.

---

### Upsert

A database operation that means **"Insert if new, Update if exists."** In Pinecone, upserting a vector with an existing ID replaces the old vector instead of creating a duplicate.

**TaxBot uses this during ingestion** to ensure that re-running ingestion on the same documents doesn't create duplicate chunks.

---

## 🔧 Model Selection Concepts

### Model Family Tiers

Google's Gemini models come in tiers, each balancing speed, accuracy, and cost:

| Tier        | Model Example        | Speed   | Accuracy | Cost (Input/Output per 1M tokens) |
|:------------|:---------------------|:--------|:---------|:----------------------------------|
| **Lite**    | Gemini 2.5 Flash-Lite | Fastest | Good     | $0.10 / $0.40                     |
| **Flash**   | Gemini 2.5 Flash      | Fast    | Very Good| $0.30 / $2.50                     |
| **Pro**     | Gemini 2.5 Pro        | Slower  | Best     | $1.25 / $10.00                    |

**TaxBot's Strategy:** Use **Flash** for main queries (accuracy matters for tax law) and potentially **Flash-Lite** for follow-up suggestions (a lightweight task where top accuracy isn't critical).

---

### Multimodal

The ability of a model to process **multiple types of input** — not just text, but also images, audio, video, and PDFs.

**Relevance to TaxBot:**
- Gemini Embedding-2 is **multimodal** — it can embed images, videos, and PDFs natively
- This means you could potentially embed scanned tax documents (images) directly without OCR
- Currently, TaxBot only uses text embeddings

---

### Grounding

Ensuring that an LLM's response is based on **provided evidence** (your documents) rather than its training data. TaxBot's system prompt enforces grounding with rules like:

> *"You must respond: 'I cannot find the answer to this question in the provided tax documents.' Do not attempt to answer using general outside knowledge."*

Without grounding, the model might confidently state incorrect tax rates from its training data instead of admitting it doesn't know.

---

### Hallucination

When an LLM generates **factually incorrect information presented as truth**. This is the #1 risk for a legal/tax chatbot.

**Example of Hallucination:**
- User asks: "What is the tax rate for Section 44AD?"
- Model answers: "The rate is 6% for digital transactions" (← this could be wrong if the 2025 Act changed it)

**TaxBot's Defenses Against Hallucination:**
1. RAG (answers from actual documents, not training data)
2. `temperature = 0.0` (no creative improvisation)
3. Citation requirement (must reference Source [X])
4. Grounding instruction (refuse to answer if context is insufficient)

---

## 📊 Quick Reference: Cost Impact Cheat Sheet

| Term                | Direct Cost Impact | Optimization Lever |
|:--------------------|:-------------------|:-------------------|
| **Input Tokens**     | $0.30/1M           | Reduce chunks, cache system prompt |
| **Output Tokens**    | $2.50/1M           | Set max_output_tokens, concise prompts |
| **Temperature**      | None (indirect)     | Low = deterministic but may truncate |
| **Top-K**            | More chunks = more input tokens | Reduce from 18 to 10 chunks |
| **Context Caching**  | 90% savings on cached content | Cache system prompt + top docs |
| **Batch API**        | 50% discount        | Use for follow-up suggestions |
| **Rate Limit (user)**| Caps total spend    | 3→2 queries/day = 33% cost cut |
| **Chunking**         | Smaller chunks = more precise | Tune chunk size + overlap |
| **Embedding Model**  | $0.20/1M tokens    | One-time ingestion cost, negligible |
| **BM25 (Sparse)**    | Free (local)        | No API cost, boosts keyword accuracy |

---

*Document created: July 2026 · Tailored for TaxBot's production architecture.*
