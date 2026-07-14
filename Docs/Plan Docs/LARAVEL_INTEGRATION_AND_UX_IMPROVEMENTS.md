# Laravel Integration & RAG UX Improvement Plan

This document outlines:
1. How TaxBot can securely authenticate and manage users by communicating with a **PHP/Laravel-based** taxsutra.com website.
2. User Experience (UX) improvement suggestions specifically tailored for our Income Tax Act RAG pipeline.

---

## Part 1: Laravel Stack Integration Strategy

If taxsutra.com is built on **PHP / Laravel**, we can seamlessly manage user sessions, subscription validation, and registration redirects using standard Laravel patterns.

### Option A: Laravel-Issued JWT Redirect (Recommended)

This is the cleanest approach. Laravel securely generates a JWT signed with a shared key when a logged-in subscriber clicks "Chat with TaxBot" and redirects the user to TaxBot's domain.

#### 1. Implementation on the Laravel Side (Taxsutra Dev Team)

**Step A: Install JWT library in Laravel**
```bash
composer require firebase/php-jwt
```

**Step B: Configure the Shared Secret**
Add to Laravel's `.env`:
```env
TAXBOT_SHARED_SECRET=your_long_random_shared_key_here
TAXBOT_REDIRECT_URL=https://taxsutra.taxbot.com/auth
```

**Step C: Create the Redirection Controller**
Create a new controller or add a route to handle the transition:

```php
<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Firebase\JWT\JWT;
use Illuminate\Support\Facades\Auth;

class TaxBotController extends Controller
{
    /**
     * Handle the redirection of authenticated subscribers to TaxBot.
     */
    public function redirectToTaxBot(Request $request)
    {
        $user = Auth::user();

        // 1. Guard: Check if the user is logged in
        if (!$user) {
            return redirect('https://www.taxsutra.com/user/register');
        }

        // 2. Guard: Check subscription status (e.g., active membership)
        // Adjust this check based on Laravel's actual database/plans setup
        if (!$user->is_active_subscriber) {
            return redirect('https://www.taxsutra.com/user/register');
        }

        // 3. Generate Payload
        $key = env('TAXBOT_SHARED_SECRET');
        $payload = [
            'sub'   => (string)$user->id,               // Unique Laravel User ID
            'email' => $user->email,                    // User Email
            'name'  => $user->name,                     // Full Name
            'plan'  => $user->subscription_plan ?? 'basic', // Plan type
            'iat'   => time(),                          // Issued at
            'exp'   => time() + 900                     // Expires in 15 minutes
        ];

        // Encode using HS256 algorithm
        $jwt = JWT::encode($payload, $key, 'HS256');

        // Redirect to TaxBot's Next.js login gateway
        $redirectUrl = env('TAXBOT_REDIRECT_URL') . '?token=' . $jwt;

        return redirect($redirectUrl);
    }
}
```

**Step D: Define Route in Laravel**
Add to `routes/web.php`:
```php
use App\Http\Controllers\TaxBotController;

Route::middleware(['auth'])->group(function () {
    Route::get('/chat-with-taxbot', [TaxBotController::class, 'redirectToTaxBot'])->name('taxbot.redirect');
});
```

---

### Option B: Laravel API Check (Backchannel Validation)

If the taxsutra.com team prefers not to use JWTs, they can build a simple internal API endpoint. When a user logs in, TaxBot calls back to the Laravel application directly to verify the user's login session.

```
[User] ──► Opens TaxBot ──► TaxBot Backend ──► API Call ──► [Laravel API]
                                                                  │
                                                          Validates status
                                                                  │
◄── Session Active & Subscribed ◄── User status ◄─────────────────┘
```

#### 1. Endpoint on Laravel (`routes/api.php`)
```php
use Illuminate\Http\Request;
use App\Models\User;

Route::middleware('api.key')->get('/v1/verify-user', function (Request $request) {
    $email = $request->query('email');
    
    $user = User::where('email', $email)->first();
    
    if (!$user || !$user->is_active_subscriber) {
        return response()->json([
            'registered' => false,
            'reason' => 'No active subscription found'
        ], 403);
    }
    
    return response()->json([
        'registered' => true,
        'user_id' => $user->id,
        'email' => $user->email,
        'plan' => $user->subscription_plan
    ]);
});
```

#### 2. Call on TaxBot FastAPI Backend
```python
import requests

def verify_user_with_laravel(email: str) -> bool:
    try:
        response = requests.get(
            "https://www.taxsutra.com/api/v1/verify-user",
            params={"email": email},
            headers={"Authorization": f"Bearer {SECRET_API_KEY}"},
            timeout=5
        )
        if response.status_code == 200:
            return response.json().get("registered", False)
    except requests.exceptions.RequestException:
        pass
    return False
```

---

## Part 2: User Experience (UX) Improvement Suggestions for RAG

To transition this application from a local proof-of-concept into a premium, customer-facing product, we should implement the following RAG UX enhancements:

### 1. Real-time Answer Streaming (Token-by-Token)
*   **The Issue:** Waiting 5 to 15 seconds for a full RAG retrieval and response to complete causes users to think the site is frozen.
*   **Improvement:** Update the FastAPI endpoint to stream response chunks as they generate using `EventSource` (Server-Sent Events) and display them incrementally in Next.js.
*   **Impact:** Reduces perceived latency to under 1 second.

### 2. Interactive Document Split-Screen Viewer
*   **The Issue:** The assistant mentions sections like `[Source 1]: Income Tax Act 1961 (Page 29)` but the user has no way of verifying the text directly without manually opening a PDF.
*   **Improvement:** Make citation links clickable. When clicked, open a split-screen container on the right side of the screen displaying the PDF page (or PPT slide) exactly at that timestamp or page number.
*   **Impact:** Significantly boosts user confidence in the accuracy of the grounding and provides an "open-book" validation process.

### 3. Suggested Smart Follow-up Questions
*   **The Issue:** Users often don't know what to ask or how to phrase follow-up questions to drill down on tax updates.
*   **Improvement:** Use the LLM to generate 3 suggested follow-up prompts based on the current conversation context (e.g., if asking about Sec 44AD, suggest "How does Sec 44ADA differ for professionals?").
*   **Impact:** Increases engagement and guides the CA through complex tax structures.

### 4. Interactive Feedback Loops (Thumb Up / Down)
*   **The Issue:** Developers need to know if the model is hallucinating, if citations are incorrect, or if the retrieval model failed.
*   **Improvement:** Place small thumb up/down buttons on each assistant message. If a user clicks thumbs down, prompt them for a quick comment ("Incorrect citation", "Too slow", "Wrong calculation").
*   **Impact:** Creates an evaluation database to refine chunking strategies and prompts.

### 5. Amber/Red Warnings for Potential Discrepancies
*   **The Issue:** Tax laws overlap or have legacy clauses that contradict new updates.
*   **Improvement:** If the search retrieves highly similar passages with different numbers/dates, highlight them with an Amber warning flag (e.g., *"Notice: We found conflicting information between Finance Act 2024 and Finance Act 2026 guidelines. Please double-check Section 115BAC default regimes."*)
*   **Impact:** Protects the CAs from acting on legacy data and prevents liability.

### 6. Export Conversation History
*   **The Issue:** CAs use the bot for research and need to copy findings into emails, client reports, or internal memos.
*   **Improvement:** Add an "Export Chat" button allowing the user to download the entire conversation thread formatted cleanly as a PDF, Word document, or Markdown text.
*   **Impact:** Saves CAs time and integrates the tool into their daily workflow.

---

_Document last updated: July 3, 2026_
