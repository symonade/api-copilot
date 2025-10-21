from fastapi import FastAPI, Request, APIRouter, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import time
from uuid import uuid4
from typing import List

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

from src.analytics import ANALYTICS
from src.security import SecurityHeadersMiddleware
app.add_middleware(SecurityHeadersMiddleware)
# CORS (env-driven; dev defaults to *)
origins = os.getenv("ALLOWED_ORIGINS")
allow_origins = [o.strip() for o in origins.split(",") if o.strip()] if origins else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Mount the mock API at /mock for parity with local runs
if mock_app:
    app.mount("/mock", mock_app)


def _new_sid() -> str:
    return uuid4().hex


def _render_chat(transcript: List[dict]) -> str:
    # Find latest assistant meta for selected API
    api_badge = ""
    for turn in reversed(transcript):
        if turn.get("role") == "assistant":
            meta = turn.get("meta") or {}
            api = meta.get("selected_api")
            if api:
                api_badge = f"<div class=\"text-xs text-slate-500 mb-2\">Selected API: <b>{api}</b></div>"
            break
    bubbles = []
    for t in transcript:
        role = t.get("role")
        text = (t.get("text") or "").replace("<", "&lt;")
        if role == "user":
            bubbles.append(
                f"<div class='flex justify-end'><div class='max-w-[80%] bg-blue-50 border border-blue-100 rounded-2xl px-3 py-2 my-1'>{text}</div></div>"
            )
        else:
            bubbles.append(
                f"<div class='flex justify-start'><div class='max-w-[80%] bg-slate-50 border border-slate-200 rounded-2xl px-3 py-2 my-1 whitespace-pre-wrap'>{text}</div></div>"
            )
    return api_badge + "\n".join(bubbles) if bubbles else "<p class='text-slate-500'>No messages yet. Ask a question to begin.</p>"


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    sid = request.cookies.get("chat_sid")
    if not sid:
        sid = _new_sid()
    transcript = SESSION_STORE.get(sid)
    # Minimal, non-intrusive UI with HTMX + Tailwind CDN
    content = (
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
        <div class="flex items-center gap-3 text-sm">
          <span id="op-badge" class="px-2 py-1 rounded bg-amber-100 text-amber-800">🟠 Checking…</span>
          <a href="/mock/status" class="text-slate-500 hover:text-slate-700 underline">Mock API Status</a>
        </div>
      </header>

      <section id="chat-window" class="bg-white rounded-2xl shadow p-4 text-sm text-slate-800 min-h-[300px]">
        REPL_HERE
      </section>

      <section class="bg-white rounded-2xl shadow p-3 sticky bottom-0">
        <form hx-post="/chat" hx-trigger="submit" hx-target="#chat-window" hx-swap="innerHTML">
          <div class="flex gap-2">
            <textarea name="message" required rows="2" class="flex-1 border rounded-xl px-3 py-2 focus:outline-none focus:ring" placeholder="Ask a question…"></textarea>
            <button class="px-4 py-2 bg-slate-900 text-white rounded-xl h-fit">Send</button>
          </div>
          <div class="flex items-center justify-between mt-2 text-xs">
            <div class="space-x-2">
              <button type="button" class="underline" hx-post="/chat/new" hx-target="#chat-window" hx-swap="innerHTML">New Chat</button>
              <button type="button" class="underline" onclick="copyTranscript()">Copy Transcript</button>
              <button type="button" class="underline" hx-post="/chat/share" hx-target="#share-out" hx-swap="innerHTML">Share</button>
            </div>
            <span class="text-slate-500">Using: <code>""" + os.getenv("MODEL_NAME", "gemini-2.5-flash-lite") + """</code></span>
          </div>
        </form>
        <div id="share-out" class="mt-2 text-xs text-slate-600"></div>
      </section>
      <script>
      async function copyTranscript(){
        try{
          const resp = await fetch('/chat/transcript');
          const txt = await resp.text();
          await navigator.clipboard.writeText(txt);
          alert('Transcript copied');
        }catch(e){ alert('Copy failed'); }
      }
      // Small Operational badge via HTMX fetch to /mock/status
      window._setStatusBadge = function(e){
        try{
          const data = JSON.parse(e.detail.xhr.responseText || '{}');
          const ok = (data && (data.ok === true || data.status === 'OK' || data.ok === 'true'));
          const el = document.getElementById('op-badge');
          if(!el) return;
          if(ok){ el.className='px-2 py-1 rounded bg-green-100 text-green-800'; el.textContent='🟢 Operational'; }
          else { el.className='px-2 py-1 rounded bg-amber-100 text-amber-800'; el.textContent='🟠 Issues'; }
        }catch(err){ /* ignore */ }
      }
      </script>
      <div hx-get="/mock/status" hx-trigger="load" hx-swap="none" hx-on="htmx:afterOnLoad: window._setStatusBadge(event)"></div>

      <section class="bg-white rounded-2xl shadow p-4">
        <h2 class="font-medium mb-2">About this demo</h2>
        <p class="text-sm text-slate-700">A minimal agentic API copilot that performs health checks, retrieves docs with RAG, and routes queries between internal APIs. This is a local-first demo with an opt-in web UI and a simple REPL.</p>
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
        &copy; """ + str(os.getenv("APP_OWNER", "Internal Demo")) + """ • <a class="underline" href="/docs">/docs</a> • <a class="underline" href="/healthz">/healthz</a>
      </footer>
    </div>
  </body>
</html>
        """
    )
    content = content.replace("REPL_HERE", _render_chat(transcript))
    resp = HTMLResponse(content)
    resp.set_cookie("chat_sid", sid, httponly=True, samesite="lax")
    return resp


_RATE_LIMIT: dict = {}  # key -> list[timestamps]

def _parse_rl_env(val: str, default_count: int, default_window: float) -> (int, float):
    try:
        c, w = val.split("-", 1)
        return int(c), float(w)
    except Exception:
        return default_count, default_window


def _rate_limited(ip: str) -> bool:
    now = time.time()
    cnt, win = _parse_rl_env(os.getenv("RL_PER_IP", "10-60"), 10, 60.0)
    q = _RATE_LIMIT.get(ip, [])
    q = [t for t in q if now - t < win]
    if len(q) >= cnt:
        _RATE_LIMIT[ip] = q
        return True
    q.append(now)
    _RATE_LIMIT[ip] = q
    return False


def _mask_secrets(msg: str) -> str:
    if not msg:
        return msg
    for k in ("GOOGLE_API_KEY", "PUBLIC_CHAT_API_KEY", "SECRET_KEY", "ADMIN_SECRET"):
        val = os.getenv(k)
        if val and val in msg:
            msg = msg.replace(val, "****")
    return msg


@app.post("/chat")
async def chat(request: Request):
    req_id = f"req_{uuid4().hex[:8]}"
    form = await request.form()
    message = (form.get("message") or "").strip()
    if not message:
        return HTMLResponse('<p class="text-red-600">Please enter a message.</p>', status_code=400)

    # Kill-switch and optional key gate
    if os.getenv("DISABLE_CHAT", "false").lower() == "true":
        return HTMLResponse('<p class="text-amber-700">Chat is temporarily disabled.</p>', status_code=503)
    # Optional API key gate
    public_key = os.getenv("PUBLIC_CHAT_API_KEY")
    if public_key:
        header_key = request.headers.get("X-Public-Key")
        if header_key != public_key:
            return HTMLResponse('<p class="text-red-600">Unauthorized.</p>', status_code=401)

    # Simple per-IP rate limit
    client_ip = request.client.host if request.client else "0.0.0.0"
    if _rate_limited(client_ip):
        return HTMLResponse('<p class="text-amber-700">Rate limit—try again in a minute.</p>', status_code=429)

    if run_agent_once is None:
        return HTMLResponse('<p class="text-red-600">Agent not available in this build.</p>', status_code=500)

    # Session handling
    sid = request.cookies.get("chat_sid") or _new_sid()
    # Per-session rate limit from env (default 20-300)
    now = time.time();
    key = f"sid:{sid}"
    arr = _RATE_LIMIT.get(key, [])
    sc, sw = _parse_rl_env(os.getenv("RL_PER_SESSION", "20-300"), 20, 300.0)
    arr = [t for t in arr if now - t < sw]
    if len(arr) >= sc:
        _RATE_LIMIT[key] = arr
        return HTMLResponse('<p class="text-amber-700">Rate limit—try again in a few minutes.</p>', status_code=429)
    arr.append(now); _RATE_LIMIT[key]=arr

    # Append user turn
    SESSION_STORE.append(sid, "user", message)

    try:
        result = run_agent_once(message) or {}
        final_text = result.get("final_text") or "No reply."
        api_name = result.get("selected_api") or "n/a"
        status = result.get("api_status")
        status_badge = ""
        if isinstance(status, dict) and status.get("status"):
            color = "bg-green-100 text-green-800" if status.get("status") == "Operational" else "bg-amber-100 text-amber-800"
            status_badge = f'<span class="px-2 py-1 {color} rounded">{status.get("status")}</span>'

        # Append assistant turn with meta
        SESSION_STORE.append(sid, "assistant", final_text, meta={"selected_api": api_name, "api_status": status})
        # Return refreshed chat window
        transcript = SESSION_STORE.get(sid)
        html = _render_chat(transcript)
        resp = HTMLResponse(html)
        resp.set_cookie("chat_sid", sid, httponly=True, samesite="lax")
        try:
            ANALYTICS.record_event(sid, "/chat", int((time.monotonic()-start)*1000), api_name, True)
        except Exception:
            pass
        return resp
    except Exception as e:
        try:
            ANALYTICS.record_event(sid, "/chat", int((time.monotonic()-start)*1000), None, False, e.__class__.__name__)
        except Exception:
            pass
        return HTMLResponse(f'<p class="text-red-600">Error: {_mask_secrets(str(e))}</p>', status_code=500)


@app.post("/chat/new")
async def chat_new(request: Request):
    start = time.monotonic()
    sid = request.cookies.get("chat_sid") or _new_sid()
    SESSION_STORE.reset(sid)
    html = _render_chat([])
    resp = HTMLResponse(html)
    resp.set_cookie("chat_sid", sid, httponly=True, samesite="lax")
    try:
        ANALYTICS.record_event(sid, "/chat/new", int((time.monotonic()-start)*1000), None, True)
    except Exception:
        pass
    return resp


@app.get("/chat/transcript")
async def chat_transcript(request: Request):
    sid = request.cookies.get("chat_sid") or _new_sid()
    turns = SESSION_STORE.get(sid)
    lines = []
    for t in turns:
        role = t.get("role"); text = t.get("text") or ""
        lines.append(f"{role}: {text}")
    return HTMLResponse("\n".join(lines), media_type="text/plain")


@app.post("/chat/share")
async def chat_share(request: Request):
    sid = request.cookies.get("chat_sid") or _new_sid()
    turns = SESSION_STORE.get(sid)
    payload = [{"r": t.get("role"), "t": t.get("text") or ""} for t in turns if t.get("role") in ("user","assistant")]
    if not payload:
        return HTMLResponse('<p class="text-slate-600">Nothing to share yet.</p>', status_code=400)
    secret = os.getenv("SECRET_KEY", "dev-secret-change-me")
    token = pack_link(payload, secret)
    # size guard
    import zlib, json as _json
    comp_len = len(zlib.compress(_json.dumps(payload, separators=(",", ":")).encode("utf-8")))
    max_kb = int(os.getenv("MAX_SHARE_SIZE_KB", "32"))
    if comp_len > max_kb * 1024:
        return HTMLResponse('<p class="text-amber-700">Transcript too large to share. Try trimming it.</p>', status_code=413)
    origin = request.headers.get("origin") or request.url.scheme + "://" + request.headers.get("host", "")
    if not origin.strip():
        origin = request.url.scheme + "://" + request.client.host
    url = f"{origin}/c/{token}"
    html = f"""
      <div class='bg-slate-50 border border-slate-200 rounded-xl p-2'>
        <div class='text-xs mb-1'>Shareable link (read-only)</div>
        <div class='flex gap-2'>
          <input id='shareUrl' class='flex-1 border rounded px-2 py-1 text-xs' value='{url}' readonly />
          <button class='text-xs underline' onclick="navigator.clipboard.writeText(document.getElementById('shareUrl').value)">Copy</button>
        </div>
      </div>
    """
    try:
        ANALYTICS.record_share()
    except Exception:
        pass
    return HTMLResponse(html)


@app.get("/c/{token}", response_class=HTMLResponse)
async def view_shared(token: str):
    try:
        secret = os.getenv("SECRET_KEY", "dev-secret-change-me")
        transcript = unpack_link(token, secret)
        # Render read-only bubbles
        bubbles = []
        for t in transcript:
            role = t.get("r"); text = (t.get("t") or "").replace("<","&lt;")
            if role == "user":
                bubbles.append(f"<div class='flex justify-end'><div class='max-w-[80%] bg-blue-50 border border-blue-100 rounded-2xl px-3 py-2 my-1'>{text}</div></div>")
            else:
                bubbles.append(f"<div class='flex justify-start'><div class='max-w-[80%] bg-slate-50 border border-slate-200 rounded-2xl px-3 py-2 my-1 whitespace-pre-wrap'>{text}</div></div>")
        html = """
        <div class='max-w-3xl mx-auto p-6'>
          <div class='text-xs text-slate-500 mb-2'>Read-only share</div>
          <div class='bg-white rounded-2xl shadow p-4 text-sm'>
        """ + "\n".join(bubbles) + """
          </div>
          <div class='mt-3 text-xs'><a class='underline' href='/'>Start your own chat</a></div>
        </div>
        """
        return HTMLResponse(html)
    except Exception:
        return HTMLResponse("<p class='text-red-600'>Invalid or expired share link.</p>", status_code=400)


@app.get("/healthz")
def healthz():
    return {"ok": True}

# --- Admin endpoints ---
def _auth_admin(request: Request) -> bool:
    secret = os.getenv("ADMIN_SECRET")
    if not secret:
        return False
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer ") and auth[7:] == secret:
        return True
    if request.query_params.get("key") == secret:
        return True
    return False


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    if not _auth_admin(request):
        return HTMLResponse("<p>Unauthorized</p>", status_code=401)
    daily = ANALYTICS.snapshot_daily()
    totals = {
        "requests": sum(d.get("requests_total", 0) for d in daily),
        "sessions": sum(d.get("unique_sessions", 0) for d in daily),
        "shares": sum(d.get("share_clicks", 0) for d in daily),
        "avg_latency": (sum(d.get("avg_latency_ms", 0) for d in daily) // max(1, len(daily))) if daily else 0,
        "tool_calls": sum(d.get("tool_calls", 0) for d in daily),
    }
    recent = ANALYTICS.recent_events(50)
    rows = []
    for ev in recent:
        rows.append(f"<tr><td class='px-2 py-1 text-xs'>{ev['ts']}</td><td class='px-2 py-1 text-xs'>{ev['route']}</td><td class='px-2 py-1 text-xs'>{ev.get('selected_api') or ''}</td><td class='px-2 py-1 text-xs'>{ev['latency_ms']}</td><td class='px-2 py-1 text-xs'>{ev['result']}</td></tr>")
    html = f"""
    <div class='max-w-5xl mx-auto p-6'>
      <h1 class='text-xl font-semibold mb-3'>Admin Dashboard</h1>
      <div class='grid grid-cols-2 md:grid-cols-3 gap-3 mb-4'>
        <div class='bg-white rounded-xl border p-3'><div class='text-xs text-slate-500'>Requests (sum)</div><div class='text-lg'>{totals['requests']}</div></div>
        <div class='bg-white rounded-xl border p-3'><div class='text-xs text-slate-500'>Unique Sessions</div><div class='text-lg'>{totals['sessions']}</div></div>
        <div class='bg-white rounded-xl border p-3'><div class='text-xs text-slate-500'>Shares</div><div class='text-lg'>{totals['shares']}</div></div>
        <div class='bg-white rounded-xl border p-3'><div class='text-xs text-slate-500'>Avg Latency (ms)</div><div class='text-lg'>{totals['avg_latency']}</div></div>
        <div class='bg-white rounded-xl border p-3'><div class='text-xs text-slate-500'>Tool Calls</div><div class='text-lg'>{totals['tool_calls']}</div></div>
      </div>
      <div class='mb-3 space-x-3 text-sm'>
        <a class='underline' href='/admin/metrics.json?key={os.getenv('ADMIN_SECRET','')}' target='_blank'>JSON snapshot</a>
        <a class='underline' href='/admin/export.csv?key={os.getenv('ADMIN_SECRET','')}' target='_blank'>Export CSV</a>
      </div>
      <div class='bg-white rounded-xl border overflow-x-auto'>
        <table class='min-w-full'><thead><tr><th class='px-2 py-1 text-left text-xs'>Time</th><th class='px-2 py-1 text-left text-xs'>Route</th><th class='px-2 py-1 text-left text-xs'>API</th><th class='px-2 py-1 text-left text-xs'>Latency</th><th class='px-2 py-1 text-left text-xs'>Result</th></tr></thead><tbody>""" + "".join(rows) + """</tbody></table>
      </div>
    </div>
    """
    return HTMLResponse(html)


@app.get("/admin/metrics.json")
async def admin_metrics(request: Request):
    if not _auth_admin(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    daily = ANALYTICS.snapshot_daily()
    totals = {
        "requests": sum(d.get("requests_total", 0) for d in daily),
        "sessions": sum(d.get("unique_sessions", 0) for d in daily),
        "shares": sum(d.get("share_clicks", 0) for d in daily),
        "avg_latency": (sum(d.get("avg_latency_ms", 0) for d in daily) // max(1, len(daily))) if daily else 0,
        "tool_calls": sum(d.get("tool_calls", 0) for d in daily),
    }
    return JSONResponse({"daily": daily, "totals": totals})


@app.get("/admin/export.csv")
async def admin_export(request: Request):
    if not _auth_admin(request):
        return HTMLResponse("unauthorized", status_code=401)
    from src.analytics import ANALYTICS as _AN
    csv_text = _AN.to_csv()
    return Response(content=csv_text, media_type="text/csv")
from src.session_store import SESSION_STORE
from src.link_token import pack as pack_link, unpack as unpack_link
