# The Layman's Guide to TaxBot's Tech Stack & Ingestion Pipeline

This document explains in simple, non-technical terms how TaxBot works under the hood, how to add new data, and how the ingestion system can be optimized and automated.

---

## Part 1: The Tech Stack (Explained for Non-Programmers)

Think of TaxBot as a highly efficient research assistant in a physical tax library. Here is what each part of our technology stack does:

| Tech Tool | Layman's Analogy | What it Actually Does in TaxBot | Why We Chose It |
| :--- | :--- | :--- | :--- |
| **FastAPI** (Python Backend) | **The Office Manager** | It receives the user's question, sends it to the library to fetch documents, hands them to the AI, and passes the answer back to the screen. | Incredibly fast, handles multiple tasks at once, and integrates perfectly with Python AI tools. |
| **Next.js** (React Frontend) | **The Clean Reception Desk** | The screen where the user types questions, scrolls through chat history, and toggles between Light and Dark modes. | Scalable, handles thousands of users at once, and loads instantly in the browser. |
| **Pinecone** (Vector Database) | **The Smart Filing Cabinet** | Instead of sorting folders alphabetically, it stores documents based on **meaning**. If you ask about "corporate tax limits," it instantly pulls pages discussing "company taxation caps," even if the word "limit" isn't on the page. | Can search millions of pages in milliseconds. |
| **BM25 Encoder** (Sparse Index) | **The Keyword Index** | The index at the back of a book. If you search for an exact code like "Section 115BAC," BM25 finds the exact matches immediately. | Combines with Pinecone to create a **"Hybrid Search"** (meaning search + exact keyword matching). |
| **Google Gemini / Llama 3.1** (LLM) | **The Expert Lawyer** | It takes the retrieved pages and writes a structured, human-readable summary with citations. It cannot make up answers; it only reads what was fetched. | Fast, cheap, and excellent at following strict instructions. |
| **Supabase** (Database) | **The Filing Cabinet for Chat History** | Stores user logins, remembers your past conversations, and tracks how many queries you have used today. | Secure, hosted in the cloud, and easily handles thousands of users. |

---

## Part 2: How to Add More Data to TaxBot

### 1. What File Formats Can We Use?
Currently, the ingestion script supports:
*   **PDFs (`.pdf`):** Best for official tax notifications, circulars, and act sections.
*   **PowerPoint Presentations (`.ppt` / `.pptx`):** Best for training decks or summaries of tax acts.
*   **Video Subtitles (`.vtt`):** Best for video transcripts, allowing you to search videos and jump to specific timestamps.

#### Can we add CSVs?
**Yes, but we must add a CSV parser to the code first.** 
Unlike a PDF which reads like a book, a CSV is a table of numbers and headers. To make the AI understand a CSV, the parser must convert table rows into narrative text, for example:
*   *CSV Row:* `Section: 44AD, Limit: 3 Crores, Year: 2026`
*   *Converted Text:* `For the year 2026, the limit under Section 44AD is 3 Crores.`
Once converted to text, it can be embedded and stored in Pinecone just like a PDF.

### 2. The Step-by-Step Developer Process to Add Files
1. Copy the new files (e.g., `budget_update_2026.pdf`) into the **`backend/data/`** folder.
2. Open a terminal and run:
   ```bash
   python ingestion.py
   ```
3. The script will automatically parse the new files, slice them into small chunks (approx. 1000 characters each), calculate their mathematical meanings (embeddings), and upload them to Pinecone.

---

## Part 3: Ingestion Timing & Hardware (GPU vs. CPU)

Because we use cloud-based APIs (like Google Gemini) to calculate the "meanings" (embeddings) of our text, **your local computer's hardware (GPU or CPU) does not affect the speed of ingestion.**

### Ingestion Speed Breakdown:
*   **Local Processing (Parsing & Chunking):** Extremely fast on a standard CPU (takes milliseconds per page).
*   **Embedding Generation & Upload (Cloud):** Takes about **1 to 3 seconds per page** because the script has to send the text to Google's servers, wait for the response, and then upload it to Pinecone.
*   **GPU vs. CPU:** Since Google's supercomputers handle the heavy math in the cloud, running the script on a computer with an expensive GPU will **not** make it run faster. It runs at the same speed on a cheap laptop as it does on a high-end server.

---

## Part 4: Why Re-run the Whole Script for Just One New File?

If you add just one new document, why can't we just upload that single file? Why do we have to wipe and rebuild everything?

### The Reason: The BM25 "Rare Word" Dictionary

To do exact keyword matching, the system uses a **BM25 Encoder**. Think of BM25 as a custom dictionary that calculates how "rare" and "important" every word in our library is.

1.  **Word Rarity Changes:** In tax law, common words like "the" or "tax" are not important. A word like "Equalisation" is rare and highly important.
2.  **Global Scoring:** To know if a word is rare, BM25 must count how many times it appears across **every single page in the entire library**.
3.  **The Mismatch Problem:** If you add a new document with new words without updating the dictionary, the scoring weights break. Old documents and new documents will use different "rarity scales," which confuses the search index and causes the bot to miss exact matches (like sections or specific percentages).

> **Conclusion:** To keep the keyword matching 100% accurate, the dictionary must be retrained on the entire document set, and the index must be updated.

---

## Part 5: Techniques to Automate Ingestion

Manually running `python ingestion.py` in a terminal is fine for a prototype, but in production, we should automate it. Here are three techniques to achieve this:

### Technique 1: Folder Watcher (Simple Local Automation)
We can use a Python library called `watchdog` to monitor the `backend/data/` folder.
*   **How it works:** A background service runs continuously. The moment you paste a new PDF into the folder, the script detects it, pauses for a few seconds, runs the ingestion pipeline, and logs the success.
*   **Best for:** Local servers or small-scale internal setups.

### Technique 2: Supabase Storage + Serverless Function (Production Grade)
Instead of local folders, upload documents to a **Supabase Storage Bucket** via an admin dashboard.
*   **How it works:** 
    1. Admin uploads a PDF to Supabase Storage.
    2. Supabase triggers a **WebHook** (HTTP call).
    3. The WebHook triggers a serverless background task (e.g., Render Background Worker or AWS Lambda).
    4. The background task downloads the new file, retrains the BM25 model, updates the Pinecone index, and sends a Slack/Email notification when finished: *"Ingestion complete. 1 new document added."*
*   **Best for:** Production-grade web apps where non-technical admins upload updates.

### Technique 3: Daily Batch Processing (Balanced Resource Use)
Instead of trigger-on-upload (which causes heavy processing if you upload 20 files in a row), run a scheduled job.
*   **How it works:** 
    - Set up a cron-job (timer) to run every night at 2:00 AM.
    - The script checks if any new files were added to the directory/database in the last 24 hours.
    - If yes, it runs the ingestion once.
*   **Best for:** Keeping server costs low and preventing Pinecone API limits from being hit during active work hours.

---

_Document last updated: July 3, 2026_
