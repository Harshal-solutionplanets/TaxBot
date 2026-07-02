# Plan: Supabase Migration + Taxsutra Auth with Per-User Query Limits

> **Scope:** Replace the local `taxbot.db` SQLite file with a hosted Supabase PostgreSQL database, and implement a complete auth flow where only registered taxsutra.com users can access TaxBot — with a 3-query-per-day rate limit enforced at the database level.

---

## Overview of the Full Flow

```
taxsutra.com Website
  └─ User clicks "Chat with TaxBot" button
        │
        ├─ Is user logged in AND registered?
        │       │
        │       ├─ NO  →  Redirect to taxsutra.com/user/register
        │       │
        │       └─ YES →  taxsutra.com backend generates signed JWT
        │                    │
        │                    └─ Redirect to taxsutra.taxbot.com/auth?token=<JWT>
        │
taxsutra.taxbot.com (TaxBot Next.js)
  └─ /auth page validates JWT via FastAPI
        ├─ JWT invalid / expired  → Show error, link back to taxsutra.com
        └─ JWT valid
              └─ FastAPI creates/updates user in Supabase
                    └─ Creates 8-hour session cookie
                          └─ Redirects to /chat

  (On each query)
    └─ FastAPI checks query_usage table for today's count for this user
          ├─ count >= 3  →  Return 429 "Daily limit reached" response
          └─ count < 3   →  Run query, increment counter, return response
```

---

## Part 1: Supabase Setup (Manual Steps — Do These First)

### Step 1: Create a Supabase Project

1. Go to **https://supabase.com** → Sign up / Log in
2. Click **"New Project"**
3. Fill in:
   - **Project name:** `taxbot`
   - **Database password:** *(generate a strong one, save it securely)*
   - **Region:** `Southeast Asia (Singapore)` *(closest to India)*
4. Wait ~2 minutes for the project to provision.

---

### Step 2: Create the Database Tables

Go to your Supabase project → **SQL Editor** → click **"New Query"** → paste and run the following SQL:

```sql
-- =============================================
-- TABLE 1: taxbot_users
-- Stores verified taxsutra.com users who have
-- accessed TaxBot at least once.
-- =============================================
CREATE TABLE IF NOT EXISTS taxbot_users (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    taxsutra_id    TEXT NOT NULL UNIQUE,  -- user.id from taxsutra.com JWT
    email          TEXT NOT NULL UNIQUE,
    full_name      TEXT,
    plan           TEXT DEFAULT 'basic',  -- 'basic', 'premium', etc.
    created_at     TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at   TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================
-- TABLE 2: taxbot_sessions
-- Each conversation thread. Replaces SQLite
-- sessions table.
-- =============================================
CREATE TABLE IF NOT EXISTS taxbot_sessions (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL REFERENCES taxbot_users(id) ON DELETE CASCADE,
    title        TEXT NOT NULL DEFAULT 'New Chat',
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================
-- TABLE 3: taxbot_messages
-- Individual messages in each session.
-- =============================================
CREATE TABLE IF NOT EXISTS taxbot_messages (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id  UUID NOT NULL REFERENCES taxbot_sessions(id) ON DELETE CASCADE,
    role        TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content     TEXT NOT NULL,
    source      TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================
-- TABLE 4: taxbot_query_usage
-- Tracks daily query count per user for the
-- 3-queries-per-day rate limit.
-- =============================================
CREATE TABLE IF NOT EXISTS taxbot_query_usage (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID NOT NULL REFERENCES taxbot_users(id) ON DELETE CASCADE,
    usage_date DATE NOT NULL DEFAULT CURRENT_DATE,
    count      INTEGER NOT NULL DEFAULT 0,
    UNIQUE (user_id, usage_date)   -- one row per user per day
);

-- =============================================
-- INDEXES (for query performance)
-- =============================================
CREATE INDEX IF NOT EXISTS idx_sessions_user_id     ON taxbot_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_session_id  ON taxbot_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_usage_user_date      ON taxbot_query_usage(user_id, usage_date);
```

---

### Step 3: Get Your Supabase Credentials

1. In your Supabase project, go to **Settings → API**
2. Copy:
   - **Project URL** (looks like `https://xyzxyz.supabase.co`)
   - **anon/public key** (use this for server-side calls from FastAPI)
   - **service_role key** (optional — more privileged, keep secret)

---

### Step 4: Add to `.env`

Add these lines to your **`e:\SP Projects\TaxBot\.env`** file:

```env
# --- Supabase ---
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your-anon-or-service-role-key

# --- Taxsutra JWT Auth ---
TAXBOT_JWT_SECRET=a-very-long-random-string-shared-with-taxsutra-team
```

---

## Part 2: Backend Implementation Plan (What Code Changes)

### File: `backend/database.py` — Migrate to Supabase

**Replace SQLite with Supabase Python client.** The public interface (function names) stays the same so `main.py` doesn't need major changes.

Install the required library first:
```bash
pip install supabase
```

New `database.py` will use:
```python
from supabase import create_client, Client

supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)
```

**Functions to rewrite using Supabase SDK:**

| Existing Function | New Supabase Implementation |
| ----------------- | ---------------------------- |
| `init_db()` | No longer needed (tables pre-created in Supabase dashboard) |
| `create_session(user_id, title)` | `supabase.table("taxbot_sessions").insert({...}).execute()` |
| `get_sessions(user_id)` | `supabase.table("taxbot_sessions").select("*").eq("user_id", user_id).execute()` |
| `delete_session(session_id)` | `supabase.table("taxbot_sessions").delete().eq("id", session_id).execute()` |
| `add_message(...)` | `supabase.table("taxbot_messages").insert({...}).execute()` |
| `get_session_messages(session_id)` | `supabase.table("taxbot_messages").select("*").eq("session_id", session_id).execute()` |

**New functions to add:**

```python
# Upsert a taxsutra.com user into the taxbot_users table
def upsert_user(taxsutra_id, email, full_name, plan) -> str:
    """Creates or updates a user record. Returns TaxBot user UUID."""

# Check and increment daily query count
def check_and_increment_query_usage(user_id: str, daily_limit: int = 3) -> dict:
    """
    Returns:
      { "allowed": True, "used": 2, "limit": 3 }   if under limit
      { "allowed": False, "used": 3, "limit": 3 }  if limit reached
    Uses Supabase upsert to atomically increment the counter for today's date.
    """
```

---

### File: `backend/main.py` — Add Auth Endpoint + Rate Limiting

**New `/auth` endpoint:**

```python
@app.get("/auth")
def taxsutra_auth_handoff(token: str, response: Response):
    """
    1. Validate signed JWT from taxsutra.com
    2. Upsert user into Supabase taxbot_users table
    3. Set an 8-hour secure session cookie
    4. Redirect to the Next.js frontend /chat page
    """
    try:
        payload = pyjwt.decode(token, TAXBOT_JWT_SECRET, algorithms=["HS256"])
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session link expired. Click 'Chat with TaxBot' again on taxsutra.com.")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token.")
    
    taxbot_user_id = upsert_user(
        taxsutra_id=payload["sub"],
        email=payload["email"],
        full_name=payload.get("name", ""),
        plan=payload.get("plan", "basic")
    )
    
    session_token = secrets.token_urlsafe(32)
    # Store session token → taxbot_user_id mapping (in Supabase or in-memory cache)
    
    redirect_response = RedirectResponse(url="http://taxsutra.taxbot.com/")
    redirect_response.set_cookie("taxbot_session", session_token, httponly=True, secure=True, max_age=28800)
    return redirect_response
```

**Updated `/api/query` endpoint with rate limiting:**

```python
@app.post("/api/query")
async def process_tax_query(request: QueryRequest, user=Depends(get_current_user)):
    # Check daily query limit BEFORE running the actual query
    usage = check_and_increment_query_usage(user["id"], daily_limit=3)
    if not usage["allowed"]:
        raise HTTPException(
            status_code=429,
            detail=f"You have used all {usage['limit']} queries for today. Your limit resets at midnight. Please come back tomorrow."
        )
    
    # ... rest of the existing query logic unchanged
```

---

### File: `frontend-next/src/components/ChatArea.js` — Handle Rate Limit UI

Add a friendly error state when the backend returns HTTP 429:

```jsx
if (res.status === 429) {
    const data = await res.json();
    setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: `⏳ **Daily Limit Reached**\n\n${data.detail}` 
    }]);
    return;
}
```

---

## Part 3: Taxsutra.com Side (What Their Dev Team Needs to Do)

> [!IMPORTANT]
> The following changes must be made by the **taxsutra.com development team**. Share this section with them.

### 1. Install PyJWT (or equivalent for their stack)
```bash
pip install PyJWT  # Python/Django
# OR
npm install jsonwebtoken  # Node.js
```

### 2. Add "Chat with TaxBot" Button Logic

```python
# Django/Flask view example
import jwt, datetime, os

TAXBOT_JWT_SECRET = os.environ["TAXBOT_JWT_SECRET"]  # same secret as TaxBot's .env

def taxbot_redirect_view(request):
    # Case 1: User is not logged in → redirect to registration
    if not request.user.is_authenticated:
        return redirect("https://www.taxsutra.com/user/register")
    
    # Case 2: User is logged in but not a subscriber → redirect to registration/upgrade
    # (Adjust condition based on taxsutra.com's subscription model)
    if not request.user.is_active_subscriber:
        return redirect("https://www.taxsutra.com/user/register")
    
    # Case 3: Valid registered subscriber → generate JWT and redirect to TaxBot
    payload = {
        "sub":   str(request.user.id),
        "email": request.user.email,
        "name":  request.user.get_full_name(),
        "plan":  request.user.subscription_plan,   # e.g. "premium"
        "iat":   datetime.datetime.utcnow(),
        "exp":   datetime.datetime.utcnow() + datetime.timedelta(minutes=15)
    }
    token = jwt.encode(payload, TAXBOT_JWT_SECRET, algorithm="HS256")
    return redirect(f"https://taxsutra.taxbot.com/auth?token={token}")
```

### 3. Add the Button to Taxsutra.com UI

```html
<!-- In any page on taxsutra.com (header, dashboard, article pages, etc.) -->
<a href="/redirect-to-taxbot" class="taxbot-btn">
    💬 Chat with TaxBot
</a>
```

---

## Part 4: Full User Journey (End-to-End)

### Journey A: Registered Subscriber

```
1. User is logged in on taxsutra.com
2. Clicks "Chat with TaxBot"
3. taxsutra.com backend: checks subscription → valid → generates JWT (15 min expiry)
4. Browser is redirected to: https://taxsutra.taxbot.com/auth?token=<JWT>
5. TaxBot FastAPI /auth validates JWT → creates/updates user in Supabase
6. TaxBot sets 8-hour session cookie → redirects to /chat UI
7. User sees TaxBot chat interface
8. User asks a question:
   - FastAPI checks: has this user asked < 3 questions today?
   - YES → runs RAG query, returns answer, increments counter
   - NO (3/3 used) → returns friendly "Daily limit reached" message
```

### Journey B: Not Registered / Not Logged In

```
1. User (not logged into taxsutra.com) somehow reaches the button
2. Clicks "Chat with TaxBot"
3. taxsutra.com backend: user is not authenticated
4. Redirect to: https://www.taxsutra.com/user/register
5. User registers/subscribes → then can click the button again
```

### Journey C: Expired JWT (Token > 15 min old)

```
1. User delays clicking the redirect URL (> 15 minutes)
2. TaxBot /auth receives expired JWT
3. TaxBot returns 401 error page with message:
   "Session link expired. Please click 'Chat with TaxBot' again on taxsutra.com."
4. User goes back and clicks the button again (new JWT generated)
```

---

## Part 5: Supabase Row-Level Security (RLS)

Once in production, enable Row-Level Security so users can only see their own data:

```sql
-- Enable RLS on all tables
ALTER TABLE taxbot_sessions  ENABLE ROW LEVEL SECURITY;
ALTER TABLE taxbot_messages  ENABLE ROW LEVEL SECURITY;
ALTER TABLE taxbot_query_usage ENABLE ROW LEVEL SECURITY;

-- Policy: users can only see their own sessions
CREATE POLICY "Users own their sessions"
  ON taxbot_sessions FOR ALL
  USING (user_id = auth.uid());

-- Policy: users can only see messages in their own sessions
CREATE POLICY "Users own their messages"
  ON taxbot_messages FOR ALL
  USING (session_id IN (
    SELECT id FROM taxbot_sessions WHERE user_id = auth.uid()
  ));
```

---

## Implementation Checklist

### One-Time Manual Setup (You do this)
- [ ] Create Supabase project at https://supabase.com
- [ ] Run the SQL from **Step 2** in Supabase SQL Editor
- [ ] Copy `SUPABASE_URL` and `SUPABASE_KEY` into `.env`
- [ ] Choose a strong `TAXBOT_JWT_SECRET` and add to `.env`
- [ ] Share `TAXBOT_JWT_SECRET` securely with taxsutra.com dev team

### Backend Code Changes (I will implement these)
- [ ] `pip install supabase PyJWT` → add to `requirements.txt`
- [ ] Rewrite `backend/database.py` to use Supabase client
- [ ] Add `/auth` JWT validation endpoint in `backend/main.py`
- [ ] Add `get_current_user` dependency (session cookie auth)
- [ ] Add `check_and_increment_query_usage` function
- [ ] Add rate-limit check to `/api/query` endpoint

### Frontend Changes (I will implement these)
- [ ] Add `/auth` route to Next.js frontend (show loading/error states)
- [ ] Handle HTTP 429 response in `ChatArea.js` with friendly message
- [ ] Show remaining daily query count in the UI (e.g. "3/3 queries left today")

### Taxsutra.com Changes (Their team does this)
- [ ] Add `redirect-to-taxbot` view with JWT generation
- [ ] Add "Chat with TaxBot" button to appropriate pages
- [ ] Configure redirect for non-registered users → `/user/register`

---

## Summary of Services Used

| Service | Purpose | Cost |
| ------- | ------- | ---- |
| Supabase Free Tier | Chat sessions + messages + users + rate limiting | **$0** (up to 500MB, 50K rows) |
| Supabase Pro | When > 500MB or production SLA needed | **$25/month** |
| PyJWT (Python library) | Validate taxsutra.com JWT tokens | Free |

> [!NOTE]
> For your scale of 7,500 users with 3 queries/day: estimated ~360K messages/month. Supabase Free tier handles this comfortably. Upgrade to Pro ($25/month) only when database size approaches 500MB.

---

_Document last updated: July 2, 2026_
