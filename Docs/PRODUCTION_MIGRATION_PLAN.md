# TaxBot Production Migration Plan

To move TaxBot to a production-grade environment under your central account (**taxbot0807@gmail.com**), we need to set up three key hosted services, configure billing to prevent rate-limiting, and migrate our database from local SQLite to Supabase.

Here is the step-by-step blueprint of what accounts need to be created, how to purchase subscriptions/set up billing, and how to link the codebase.

---

## 🛠️ Step 1: Establish Accounts under `taxbot0807@gmail.com`

Log out of your personal accounts and register/configure the following three services under your new email:

### 1. Google AI Studio & Google Cloud (LLM & Embeddings API)
*   **Purpose**: Supplies production Gemini models (`gemini-1.5-flash`, `gemini-1.5-pro`) and embedding models (`text-embedding-004`).
*   **Action Items**:
    1. Go to [Google AI Studio](https://aistudio.google.com/) and sign in with `taxbot0807@gmail.com`.
    2. Click **Create API Key** to generate a Gemini API key.
    3. **Set up Billing (Crucial)**: In Google AI Studio, click on **Plan & billing** or navigate to the [Google Cloud Console Billing](https://console.cloud.google.com/billing) under the same email. Add a credit/debit card.
        *   *Why?* The free tier of Gemini has strict rate limits (15 requests/minute). Linking a billing account elevates your limit to thousands of requests per minute (pay-as-you-go).

### 2. Pinecone (Vector Database)
*   **Purpose**: Stores document text chunks and dense/sparse vector representation indices for RAG semantic search.
*   **Action Items**:
    1. Go to [Pinecone Console](https://console.pinecone.io/) and click **Sign Up** using the Google OAuth option with `taxbot0807@gmail.com`.
    2. Retrieve your **Pinecone API Key** from the API keys tab.
    3. Create a serverless index:
        *   **Name**: `taxbot-hybrid-index`
        *   **Dimensions**: `768` (Matching `text-embedding-004` dimensions)
        *   **Metric**: `dotproduct` (Required for BM25 + Dense Hybrid search)
        *   **Cloud Provider**: AWS
        *   **Region**: `us-east-1` (or nearest region)

### 3. Supabase (Relational Database & User Management)
*   **Purpose**: Stores persistent user registration data, sessions, logs, daily query limits, and feedback flags.
*   **Action Items**:
    1. Go to [Supabase Console](https://supabase.com/) and register using the `taxbot0807@gmail.com` email.
    2. Click **New Project** and name it `taxbot-prod`.
    3. Choose a strong database password and select a server region close to your primary audience.
    4. Save your **Project URL** and **API Keys** (`anon` public key & `service_role` secret key).

---

## 💾 Step 2: Initialize Supabase Schema

Once your Supabase project is active, run the migration scripts to initialize our database schema:

1. Open your Supabase Dashboard, go to the **SQL Editor** from the left navigation bar.
2. Open a new query window.
3. Paste the contents of [supabase_table_init.sql](file:///e:/SP%20Projects/TaxBot/backend/supabase_table_init.sql) into the SQL editor and click **Run**.
4. This will create:
    *   `taxbot_users` (for registered taxsutra.com users)
    *   `taxbot_sessions` (for user chat sessions)
    *   `taxbot_messages` (storing the conversation history)
    *   `taxbot_query_usage` (enforcing the 3 queries/day rate limit)

---

## 📝 Step 3: Update Codebase Credentials

In the root of the project, we will update the `.env` file to transition from local models and SQLite to production-ready APIs.

Create/update [`.env`](file:///e:/SP%20Projects/TaxBot/.env) to look like this:

```ini
# --- Core API Keys ---
GEMINI_API_KEY=your_new_gemini_api_key_here
PINECONE_API_KEY=your_new_pinecone_api_key_here

# --- LLM Options ---
LLM_PROVIDER=gemini  # Set to gemini instead of ollama for production

# --- Supabase Database Options ---
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your-supabase-service-role-key-here
```

---

## 🚀 Step 4: Run Initial Vector Ingestion

With the new production Pinecone index configured:
1. Make sure all your PDF/PPT files are placed in `backend/data/`.
2. Access the **Admin Panel** (`http://localhost:3000/admin`).
3. Click **Start Ingestion** to process and embed all documents into the new Pinecone index under the `taxbot0807@gmail.com` account.

---

## 🔮 Next Steps & Action Plan
1. **Account Registrations**: Please sign up for Google AI Studio, Pinecone, and Supabase using `taxbot0807@gmail.com` as outlined above.
2. **API Keys Compilation**: Once done, collect the keys.
3. **Database Integration**: Once you have the keys ready, we will update the Python backend code (`database.py` and `main.py`) to connect to Supabase instead of SQLite `taxbot.db`.
