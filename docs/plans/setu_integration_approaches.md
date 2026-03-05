# Setu Account Aggregator Integration - Brainstorming

To replace our CSV imports with Setu Account Aggregator, we need to build the FIU (Financial Information User) flow. 

Here is how the Setu flow works:
1. **Consent Request:** We create a "Consent Object" via API asking the user for their bank statements (e.g., from `2023-01-01` to `2024-01-01`).
2. **User Approval:** We redirect the user to Setu's hosted UI where they log in with their phone number, select their bank, enter an OTP, and approve.
3. **Webhook:** Setu hits our webhook to tell us the user approved.
4. **Data Fetch:** We ask Setu to fetch the data. They hit our webhook again when the FI Data (JSON bank statements) is ready.

---

Here are 3 approaches to integrating this into the SCALE APP:

### Approach 1: The "Sync" Approach (Recommended for MVP)
We handle the consent on the frontend, and the frontend waits for the backend to fetch the data.
* **Flow:** 
  1. User clicks "Connect Bank". Frontend calls our API `POST /api/bank-sync/consent`.
  2. Backend calls Setu, gets a redirect URL, and returns it. Frontend redirects user to Setu.
  3. User finishes on Setu, gets redirected back to our app (e.g. `/bank-sync/success`).
  4. The frontend polls a new endpoint `GET /api/bank-sync/status` until it says "COMPLETED".
  5. The backend, meanwhile, received the Setu webhooks, fetched the JSON data, converted it to our internal transaction format, and saved it to the DB.
* **Pros:** Easiest to build right now. Good user experience (they see a loading spinner when they return to the app until data is ready).
* **Cons:** Takes slightly longer for the user since they have to wait on the screen for the data to process before they can see their transactions.

### Approach 2: The "Background" Approach
We treat Account Aggregator exactly like a background job (similar to how we handle machine learning categorization).
* **Flow:**
  1. User approves consent on Setu and returns to the app.
  2. The app immediately says "Success! We are fetching your data in the background."
  3. When Setu's webhook fires, our backend kicks off a background job (e.g. using `BackgroundTasks` in FastAPI) that downloads the JSON, parses it, and saves it.
  4. The user sees the transactions appear later when they refresh the page.
* **Pros:** Non-blocking. The user can go do other things immediately. 
* **Cons:** Requires more robust background error handling. What if the FIP (bank) fails to provide the data? We need a way to show that error to the user later.

### Approach 3: Setu "Insights" (Waitlist)
Instead of processing the raw bank statements ourselves, we pay Setu extra to use their "Insights" product.
* **Flow:** Setu downloads the data, categorizes the transactions, identifies recurring payments, and gives us a clean, summarized API.
* **Pros:** Zero work for us regarding parsing messy bank narrations.
* **Cons:** Costs more. We lose control over categorization rules (we've already built our own ML categorizer).

---

### My Recommendation

I recommend **Approach 1 (Sync Approach)** to start. It relies heavily on Webhooks but provides immediate gratification to the user because they don't leave the loading screen until their transactions are physically in the database. Since we already have our own ML pipeline for categorization, we do NOT need Approach 3.

**Questions for you:**
1. Does Approach 1 sound good for the architecture?
2. Do you have a Setu Sandbox account/API keys created, or do we need to mock Setu's API responses for the initial implementation phase?
