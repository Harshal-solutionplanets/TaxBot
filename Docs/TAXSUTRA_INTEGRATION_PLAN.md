# TaxBot × Taxsutra.com — Integration & Auth Plan

> **Goal:** Enable a "Chat with TaxBot" button on taxsutra.com that only allows **verified, logged-in taxsutra.com subscribers** to access the TaxBot RAG system.

---

## Problem Statement

```
[taxsutra.com User] → Clicks "Chat with TaxBot" → Should enter TaxBot ONLY if they
                                                     are a registered taxsutra.com subscriber
                                                     ↓
                                                   Otherwise → Redirect to taxsutra.com login
```

**The core challenge:** TaxBot and taxsutra.com are two separate systems. TaxBot has no way to know who is a registered taxsutra.com subscriber unless taxsutra.com explicitly tells TaxBot.

---

## Three Integration Architecture Options

---

### Option 1: Signed JWT Handoff (⭐ Recommended — Simplest & Most Secure)

**How it works:**
When a logged-in taxsutra.com user clicks the button, taxsutra.com's backend generates a **cryptographically signed JWT token** containing the user's verified identity and hands it to TaxBot via a URL redirect. TaxBot validates the signature and trusts the identity — no password re-entry, no separate auth system needed.

```
[Taxsutra.com]                              [TaxBot]
     │                                           │
  User clicks                                    │
"Chat with TaxBot"                               │
     │                                           │
  Backend                                        │
  generates                                      │
  signed JWT                                     │
  {email, plan,                                  │
   expiry: 15min}                                │
     │                                           │
     │── HTTPS Redirect ──────────────────────► │
     │  /auth?token=eyJhbG...                   │
     │                                           │
     │                              Validate JWT │
     │                              signature    │
     │                              ✅ Valid?    │
     │                                 │         │
     │                              Create TaxBot│
     │                              session      │
     │                              (SQLite DB)  │
     │                                 │         │
     │                           Redirect to     │
     │                           /chat UI ✅     │
```

**What taxsutra.com team needs to implement (1–2 days for their dev team):**
```python
# Example: In taxsutra.com backend (Python/Django/Flask)
import jwt, datetime

TAXBOT_SHARED_SECRET = "a-very-long-random-secret-key-shared-with-taxbot-team"

def generate_taxbot_redirect(user):
    payload = {
        "sub":    user.id,                         # taxsutra user ID
        "email":  user.email,                      # verified email
        "name":   user.full_name,
        "plan":   user.subscription_plan,          # e.g. "premium", "basic"
        "iat":    datetime.datetime.utcnow(),
        "exp":    datetime.datetime.utcnow() + datetime.timedelta(minutes=15)
    }
    token = jwt.encode(payload, TAXBOT_SHARED_SECRET, algorithm="HS256")
    return f"https://taxbot.taxsutra.com/auth?token={token}"

# Button click handler
def taxbot_redirect_view(request):
    if not request.user.is_authenticated:
        return redirect("/login?next=/taxbot")     # Not logged in → login page
    if not request.user.has_active_subscription:
        return redirect("/subscribe")              # Not subscribed → paywall
    redirect_url = generate_taxbot_redirect(request.user)
    return redirect(redirect_url)
```

**What TaxBot needs to implement:**
- A new `/auth` route in FastAPI that validates the JWT and creates a TaxBot session
- JWT validation middleware for all `/api/query` calls
- A session table in `database.py` to store verified user sessions

**Security properties:**
- ✅ Token expires in 15 minutes (one-time use)
- ✅ Signed with a shared secret — cannot be forged
- ✅ Token is never stored on the browser (only in redirect URL)
- ✅ No user password or credentials cross between systems
- ✅ Works across different domains (taxsutra.com → taxbot.taxsutra.com)

---

### Option 2: OAuth2 / OpenID Connect (More Standard, Higher Effort)

**How it works:**
taxsutra.com acts as an OAuth2 Identity Provider (IdP). TaxBot redirects users to taxsutra.com's login page, and after successful login, taxsutra.com issues an access token back to TaxBot.

```
[User → TaxBot] → TaxBot redirects to taxsutra.com/oauth/authorize
               ← User logs in at taxsutra.com
               → taxsutra.com redirects back with ?code=XXXX
               → TaxBot exchanges code for access token (server-to-server)
               → TaxBot calls taxsutra.com/oauth/userinfo
               → Gets user email + subscription status
               → Creates session ✅
```

**What taxsutra.com needs:** A full OAuth2 server implementation (authorization endpoint, token endpoint, userinfo endpoint). If taxsutra.com already uses Django, they can use `django-oauth-toolkit`. If they're on Node.js, `node-oidc-provider`.

**Effort:** Medium (3–7 days for taxsutra.com team, 2–3 days for TaxBot team)

**Best for:** If taxsutra.com wants to support multiple third-party integrations beyond TaxBot in the future (standard, reusable).

---

### Option 3: One-Time Token via Taxsutra API (No JWT Library Needed)

**How it works:**
taxsutra.com generates a random one-time-use token, stores it in their database, and sends it with the redirect. TaxBot calls back to a taxsutra.com verification API to confirm the token is valid.

```
[taxsutra.com] generates OTP "abc123" → stores in DB → redirects to:
   https://taxbot.taxsutra.com/auth?code=abc123

[TaxBot backend] calls:
   POST https://api.taxsutra.com/verify-taxbot-token
   { "code": "abc123", "api_key": "taxbot-secret-key" }
   
[taxsutra.com] responds:
   { "valid": true, "email": "ca@firm.com", "plan": "premium" }
   (and marks token as used — cannot be replayed)
```

**Effort:** Low for TaxBot, Low for taxsutra.com (simpler than OAuth2, no JWT library needed)

**Downside:** Requires real-time API call from TaxBot back to taxsutra.com on every login (network dependency)

---

## Recommended Approach: Option 1 (JWT Handoff)

### Why:
- taxsutra.com only needs to add one function + one button URL — minimal dev work
- TaxBot needs ~50–80 lines of new code in `main.py` + `database.py`
- No ongoing API dependency — TaxBot validates JWT locally (offline verification)
- Industry-standard pattern used by Stripe, Notion, Intercom embeds

---

## Detailed Implementation Plan

### Phase 1: Backend — TaxBot Auth Route (3–4 days)

#### Step 1: Add `user_sessions` table to `database.py`

```python
# New table in init_db()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_sessions (
        session_token TEXT PRIMARY KEY,    -- TaxBot's own session token
        taxsutra_user_id TEXT NOT NULL,
        email TEXT NOT NULL,
        name TEXT,
        plan TEXT,                         -- "premium", "basic", etc.
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP NOT NULL
    )
""")
```

#### Step 2: Add `/auth` endpoint to `main.py`

```python
import jwt as pyjwt
import secrets
from datetime import datetime, timedelta

TAXBOT_JWT_SECRET = os.getenv("TAXBOT_JWT_SECRET")   # shared with taxsutra.com

@app.get("/auth")
def taxbot_auth_handoff(token: str):
    """
    Validates the JWT from taxsutra.com and creates a TaxBot session.
    Redirects to the chat UI on success, or to an error page on failure.
    """
    try:
        # 1. Decode and validate JWT
        payload = pyjwt.decode(
            token,
            TAXBOT_JWT_SECRET,
            algorithms=["HS256"]
        )
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session link expired. Please click the button again on taxsutra.com.")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid access token. Please return to taxsutra.com.")

    # 2. Create TaxBot session
    session_token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=8)   # 8-hour session

    conn = get_db_connection()
    conn.execute("""
        INSERT INTO user_sessions (session_token, taxsutra_user_id, email, name, plan, expires_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (session_token, payload["sub"], payload["email"],
          payload.get("name"), payload.get("plan"), expires_at))
    conn.commit()
    conn.close()

    # 3. Redirect to chat UI with session token as URL param or cookie
    from fastapi.responses import RedirectResponse
    response = RedirectResponse(url="https://taxbot.taxsutra.com/")
    response.set_cookie(
        key="taxbot_session",
        value=session_token,
        httponly=True,       # not readable by JS
        secure=True,         # HTTPS only
        samesite="lax",
        max_age=28800        # 8 hours in seconds
    )
    return response
```

#### Step 3: Protect `/api/query` with session verification

```python
async def get_current_user(taxbot_session: str = Cookie(None)):
    if not taxbot_session:
        raise HTTPException(status_code=401, detail="Not authenticated. Please access TaxBot from taxsutra.com.")
    
    conn = get_db_connection()
    row = conn.execute("""
        SELECT * FROM user_sessions
        WHERE session_token = ?
        AND expires_at > CURRENT_TIMESTAMP
    """, (taxbot_session,)).fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=401, detail="Session expired. Please click 'Chat with TaxBot' again.")
    
    return dict(row)

@app.post("/api/query")
async def process_tax_query(request: QueryRequest, user=Depends(get_current_user)):
    # user["email"] and user["plan"] are now available
    # Use user["email"] as user_id for chat history sessions
    ...
```

---

### Phase 2: Frontend — Auth Gate in Streamlit (1 day)

Add an auth check at the top of `app.py`. If no valid session cookie is present, show an error page with a button back to taxsutra.com.

```python
# At the top of app.py, before rendering anything
import streamlit as st

# Check if user arrived with a valid session
# (Streamlit reads cookies via st.context.cookies in newer versions)
if not user_is_authenticated():
    st.error("🔒 Access Restricted")
    st.markdown("You must be a registered **taxsutra.com subscriber** to use TaxBot.")
    st.markdown("[← Go to taxsutra.com](https://www.taxsutra.com/)", unsafe_allow_html=True)
    st.stop()
```

> **Note:** For production, a **Next.js frontend** handles cookie-based auth much more cleanly than Streamlit. This is the strongest technical argument for migrating to Next.js when you go live on taxsutra.com.

---

### Phase 3: Taxsutra.com Button (0.5 days — their team)

taxsutra.com team adds this button anywhere on their site (dashboard, article pages, etc.):

```html
<!-- In taxsutra.com header or user dashboard -->
<a href="/redirect-to-taxbot" class="taxbot-btn">
  💬 Chat with TaxBot
</a>

<!-- Their backend generates the signed JWT redirect URL -->
```

---

### Phase 4: Subscription-Gated Access (Optional)

If only **premium subscribers** should have access:

```python
# In /auth endpoint, after decoding JWT
if payload.get("plan") not in ["premium", "pro", "enterprise"]:
    raise HTTPException(
        status_code=403,
        detail="TaxBot is available to Premium subscribers only. Upgrade at taxsutra.com/subscribe."
    )
```

This means taxsutra.com controls who can use TaxBot simply by setting the `plan` field in the JWT. **No code change on TaxBot side** when subscription tiers change.

---

## What Each Team Does

### Taxsutra.com Dev Team (1–2 days)

| Task | Effort |
| ---- | ------ |
| Generate JWT on button click (Python/Node.js) | 2 hours |
| Add "Chat with TaxBot" button to user dashboard | 1 hour |
| Handle unauthenticated users → redirect to login | 1 hour |
| Handle non-subscribers → redirect to paywall | 1 hour |
| Share `TAXBOT_JWT_SECRET` securely with TaxBot team | 30 min |

### TaxBot Dev Team (3–5 days)

| Task | Effort |
| ---- | ------ |
| Add `user_sessions` table to `database.py` | 2 hours |
| Build `/auth` JWT validation + session creation endpoint | 4 hours |
| Add `get_current_user` dependency to `/api/query` | 2 hours |
| Add auth gate to Streamlit frontend | 2 hours |
| Deploy both backend and frontend to production URLs | 4 hours |
| End-to-end integration testing with taxsutra.com | 4 hours |

---

## Deployment Architecture (Post-Integration)

```
taxsutra.com
  ├── User Dashboard
  │     └── "💬 Chat with TaxBot" button
  │           └── Click → taxsutra.com backend generates JWT
  │                        └── Redirect to:
  │
taxbot.taxsutra.com (or taxbot.solutionplanets.com)
  ├── /auth?token=<JWT>          ← Validates JWT, creates session
  ├── /                          ← Chat UI (requires session cookie)
  │
  ↓ API calls with session cookie
taxbot-api.render.com (FastAPI Backend)
  ├── GET  /api/sessions          ← Chat history
  ├── POST /api/query             ← Requires valid session cookie
  │
  ↓
Pinecone + Groq/Gemini
```

---

## Security Checklist

- [ ] `TAXBOT_JWT_SECRET` stored in `.env`, never committed to GitHub
- [ ] JWT `exp` (expiry) set to 15 minutes (one-time redirect link)
- [ ] TaxBot session cookie set with `httponly=True`, `secure=True`
- [ ] TaxBot session expires after 8 hours (forces re-verification via taxsutra.com)
- [ ] HTTPS enforced on both taxsutra.com redirect and taxbot domain
- [ ] Old sessions cleaned up from DB daily (cron job)
- [ ] CORS on FastAPI restricted to `https://taxbot.taxsutra.com` only

---

## Open Questions for taxsutra.com Team

> [!IMPORTANT]
> Before development begins, we need answers from the taxsutra.com technical team:
>
> 1. **What backend stack does taxsutra.com run?** (Django, Laravel, Node.js, etc.) — determines which JWT library to use
> 2. **Do they already have a user API?** — Could simplify integration
> 3. **Which subscription plans should get TaxBot access?** — Determines the `plan` field check
> 4. **What is the preferred subdomain for TaxBot?** — `taxbot.taxsutra.com` vs. hosted separately

---

_Document last updated: July 2, 2026_
