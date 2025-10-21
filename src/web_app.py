from fastapi import FastAPI, Request, APIRouter
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import os

# Reuse the mock API to keep parity with local dev
try:
    from src.mock_api import app as mock_app
except Exception:
    mock_app = None

# Import the single-turn entrypoint
try:
    from src.agent import run_agent_once
except Exception:
    run_agent_once = None

app = FastAPI(title="API Copilot (Web)")

# CORS (loose for demo; tighten if needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the mock API at /mock for parity with local runs
if mock_app:
    app.mount("/mock", mock_app)


@app.get("/", response_class=HTMLResponse)
async def index():
    # Minimal, non-intrusive UI with HTMX + Tailwind CDN
    return HTMLResponse(
        """
<!doctype html>
<html>
  <head>
    <meta charset="utf-8"/>
    <title>API Copilot</title>
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <script src="https://cdn.tailwindcss.com"></script>
  </head>
  <body class="min-h-screen bg-slate-50 text-slate-900">
    <div class="max-w-3xl mx-auto p-6 space-y-6">
      <header class="flex items-center justify-between">
        <h1 class="text-2xl font-semibold">API Copilot</h1>
        <a href="/mock/status" class="text-sm text-slate-500 hover:text-slate-700 underline">Mock API Status</a>
      </header>

      <section class="bg-white rounded-2xl shadow p-4">
        <form hx-post="/chat" hx-trigger="submit" hx-target="#reply" hx-swap="innerHTML">
          <label class="block text-sm mb-2">Ask the agent</label>
          <input name="message" required
                 class="w-full border rounded-xl px-3 py-2 focus:outline-none focus:ring"
                 placeholder="e.g. How do I authenticate to the API?" />
          <div class="flex items-center justify-between mt-3">
            <button class="px-4 py-2 bg-slate-900 text-white rounded-xl">Send</button>
            <span class="text-xs text-slate-500">
              Using: <code>""" + os.getenv("MODEL_NAME", "gemini-2.5-flash-lite") + """</code>
            </span>
          </div>
        </form>
      </section>

      <section id="reply" class="bg-white rounded-2xl shadow p-4 text-sm text-slate-800">
        <p class="text-slate-500">Responses will appear here.</p>
      </section>

      <section class="bg-white rounded-2xl shadow p-4">
        <h2 class="font-medium mb-2">Features coming soon</h2>
        <ul class="list-disc ml-6 space-y-1 text-slate-700">
          <li>Multi-turn chat with memory and citations</li>
          <li>Auto-triage to multiple internal APIs</li>
          <li>One-click “try it” live calls with masked keys</li>
          <li>Export answers to Markdown/Confluence</li>
        </ul>
      </section>

      <footer class="text-xs text-slate-400 text-center">
        &copy; """ + str(os.getenv("APP_OWNER", "Internal Demo")) + """
      </footer>
    </div>
  </body>
</html>
        """)


@app.post("/chat")
async def chat(request: Request):
    form = await request.form()
    message = (form.get("message") or "").strip()
    if not message:
        return HTMLResponse('<p class="text-red-600">Please enter a message.</p>', status_code=400)

    if run_agent_once is None:
        return HTMLResponse('<p class="text-red-600">Agent not available in this build.</p>', status_code=500)

    try:
        result = run_agent_once(message) or {}
        final_text = result.get("final_text") or "No reply."
        api_name = result.get("selected_api") or "n/a"
        status = result.get("api_status")
        status_badge = ""
        if isinstance(status, dict) and status.get("status"):
            color = "bg-green-100 text-green-800" if status.get("status") == "Operational" else "bg-amber-100 text-amber-800"
            status_badge = f'<span class="px-2 py-1 {color} rounded">{status.get("status")}</span>'

        html = f"""
          <div class="space-y-3">
            <div class="text-xs text-slate-500">API: <b>{api_name}</b> {status_badge}</div>
            <div class="whitespace-pre-wrap leading-relaxed">{final_text}</div>
          </div>
        """
        return HTMLResponse(html)
    except Exception as e:
        return HTMLResponse(f'<p class="text-red-600">Error: {e}</p>', status_code=500)


@app.get("/healthz")
def healthz():
    return {"ok": True}

