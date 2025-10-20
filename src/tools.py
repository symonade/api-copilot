import os
import time
import requests
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from langchain.tools import tool
from datetime import datetime

# --- Rich (color logs) with safe fallback ---
try:
    from rich.console import Console
    from rich.table import Table
    HAVE_RICH = True
except ImportError:
    HAVE_RICH = False

    class Console:
        def log(self, *args, **kwargs): print(*args)
        def rule(self, msg): print(str(msg))
        def print(self, *args, **kwargs): print(*args)

    Table = None

console = Console()

# --- Vector store imports (prefer standalone) ---
try:
    from langchain_chroma import Chroma  # pip install -U langchain-chroma
except ImportError:
    from langchain_community.vectorstores import Chroma

from langchain_google_genai import GoogleGenerativeAIEmbeddings

# --- Load Environment ---
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=dotenv_path)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY not found in .env")
# Ensure nested libs can see the key
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

# --- Setup Chroma Vector Store ---
CHROMA_PERSIST_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "chroma_db"))
console.log(f"[bold yellow]Attempting to load ChromaDB from:[/bold yellow] {CHROMA_PERSIST_DIR}")

embedding_model: Optional[GoogleGenerativeAIEmbeddings] = None
vector_store: Optional[Chroma] = None

try:
    embedding_model = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
except Exception as e:
    console.log(f"[red]❌ Failed to initialize embeddings: {e}[/red]")

if embedding_model is not None:
    try:
        vector_store = Chroma(
            persist_directory=CHROMA_PERSIST_DIR,
            embedding_function=embedding_model
        )
        console.log("[green]✅ ChromaDB loaded successfully for RAG tool.[/green]")
    except Exception as e:
        console.log(f"[red]❌ Failed to load ChromaDB: {e}[/red]")
        console.log("Please ensure ingestion has been run successfully.")
else:
    console.log("[red]Embeddings unavailable; RAG tool will be disabled.[/red]")


# --- RAG Tool: Documentation Search ---
@tool
def search_documentation(query: str, k: int = 4, api_hint: str = "") -> List[Dict[str, Any]]:
    """
    Searches the ConTech API documentation for the most relevant context.
    Returns the top-k results with relevance scores and metadata.
    """
    if vector_store is None:
        return [{"error": "Vector store not initialized. Run ingestion first."}]

    console.rule("[bold blue]RAG Search Initiated[/bold blue]")
    console.log(f"🔍 Query: [cyan]{query}[/cyan]")

    try:
        results = vector_store.similarity_search_with_relevance_scores(query, k=k)
        console.log(f"[green]Found {len(results)} results.[/green]")

        formatted_results: List[Dict[str, Any]] = []
        for doc, score in results:
            # Apply soft filter by api_hint if provided and metadata has a 'source'
            if api_hint and isinstance(doc.metadata, dict):
                src = str(doc.metadata.get("source") or "").lower()
                if api_hint.lower() not in src:
                    continue
            formatted_results.append(
                {
                    "page_content": doc.page_content,
                    "metadata": doc.metadata,
                    "relevance_score": float(round(float(score), 3)),
                }
            )

        if not formatted_results:
            console.log("[yellow]No relevant results found.[/yellow]")
            return [{"message": "No matching documentation found."}]

        if HAVE_RICH and Table is not None:
            table = Table(title="Top Retrieved Chunks", show_header=True, header_style="bold magenta")
            table.add_column("Relevance", justify="right")
            table.add_column("Snippet", justify="left")
            for item in formatted_results:
                snippet = (item["page_content"] or "").replace("\n", " ")[:80] + "..."
                table.add_row(str(item["relevance_score"]), snippet)
            console.print(table)

        return formatted_results

    except Exception as e:
        console.log(f"[red]Error during RAG search:[/red] {e}")
        return [{"error": f"RAG search failed: {e}"}]


# --- Retry Logic Helper ---
def _retry_request(request_fn, max_retries=3, delay=2):
    last_exc: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            return request_fn()
        except (requests.exceptions.Timeout,
                requests.exceptions.ConnectionError,
                requests.exceptions.HTTPError) as e:
            last_exc = e
            if attempt < max_retries - 1:
                console.log(f"[yellow]⚠️ Attempt {attempt + 1} failed ({e}). Retrying in {delay}s...[/yellow]")
                time.sleep(delay)
            else:
                raise e
    if last_exc:
        raise last_exc


# --- Health Check Tool ---
@tool
def check_api_status(base_url: str = "http://localhost:8000", timeout: int = 5) -> Dict[str, Any]:
    """
    Checks operational status of a target API using health endpoints.
    Retries up to 3 times with delay to handle transient network failures.
    """
    console.rule("[bold blue]API Health Check[/bold blue]")
    console.log(f"🌍 Base URL: [cyan]{base_url}[/cyan]")

    endpoints = ["/status", "/health", "/"]
    for endpoint in endpoints:
        url = base_url.rstrip('/') + endpoint

        def probe():
            # HEAD first (cheap), fallback to GET if needed
            try:
                resp = requests.head(url, timeout=timeout, allow_redirects=True)
            except requests.exceptions.RequestException:
                resp = None

            if resp is None or resp.status_code >= 400:
                resp = requests.get(url, timeout=timeout)

            # Map 503 to HTTPError for retry and upstream handling
            if resp.status_code == 503:
                raise requests.exceptions.HTTPError("Service Unavailable", response=resp)

            # Treat non-2xx/3xx as failure to allow retry/next endpoint
            if not (200 <= resp.status_code < 400):
                raise requests.exceptions.HTTPError(f"Bad status: {resp.status_code}", response=resp)

            return resp

        try:
            resp = _retry_request(probe)
            console.log(f"[green]✅ {url} responded with {resp.status_code}[/green]")
            return {
                "status": "Operational",
                "checked_endpoint": url,
                "status_code": int(resp.status_code),
                "details": f"API responded successfully from {endpoint}."
            }
        except requests.exceptions.HTTPError as e:
            code = getattr(getattr(e, "response", None), "status_code", None)
            if code == 503:
                console.log(f"[yellow]⚠️ {url} returned 503 Service Unavailable[/yellow]")
                return {
                    "status": "Unavailable",
                    "checked_endpoint": url,
                    "status_code": 503,
                    "details": "Service Unavailable (503). Likely maintenance or overload."
                }
            console.log(f"[red]❌ Failed probing {url}: {e}[/red]")
        except Exception as e:
            console.log(f"[red]❌ Failed probing {url}: {e}[/red]")

    console.log(f"[red]All health endpoints failed for {base_url}[/red]")
    return {
        "status": "Unreachable",
        "checked_endpoint": base_url,
        "status_code": None,
        "details": f"All health endpoints failed for {base_url}."
    }


# --- Export Tools ---
available_tools = [search_documentation, check_api_status]

def get_tools():
    return available_tools

# --- New: Real API tools (Block 7) ---
from typing import Optional


@tool
def create_project(payload: Dict[str, Any], base_url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 10) -> Dict[str, Any]:
    """
    Create a new project via POST {base_url}/projects.
    Returns: { ok: bool, data?: dict, status_code?: int, error?: str }
    """
    def _ensure_auth(h: Optional[Dict[str, str]], base: str) -> Dict[str, str]:
        out = dict(h or {})
        # If only X-API-Key is provided, mirror it as Bearer for mock compatibility
        if "Authorization" not in out:
            api_key = out.get("X-API-Key") or out.get("x-api-key")
            if api_key:
                out["Authorization"] = f"Bearer {api_key}"
            elif base.startswith("http://localhost:8000") or base.startswith("https://localhost:8000"):
                # Mock API accepts any Bearer token
                out["Authorization"] = "Bearer dev"
        return out

    def _coerce_project_payload(p: Dict[str, Any]) -> Dict[str, Any]:
        name = p.get("name") or p.get("projectName") or "New Project"
        description = p.get("description")
        out: Dict[str, Any] = {"name": name}
        if description:
            out["description"] = description
        return out

    url = base_url.rstrip("/") + "/projects"
    console.rule("[bold blue]Create Project[/bold blue]")
    console.log(f"POST {url}")
    try:
        payload = _coerce_project_payload(payload or {})
        send_headers = _ensure_auth(headers, base_url)
        resp = requests.post(url, json=payload, headers=send_headers, timeout=timeout)
        console.log(f"[green]→ Status: {resp.status_code}[/green]")
        try:
            resp.raise_for_status()
        except requests.exceptions.HTTPError as e:
            # If API expects Bearer and we sent X-API-Key, retry with Bearer using same key
            try:
                h = headers or {}
                api_key = h.get("X-API-Key") or h.get("x-api-key")
                if resp.status_code == 401 and api_key:
                    retry_headers = dict(h)
                    retry_headers.pop("X-API-Key", None)
                    retry_headers.pop("x-api-key", None)
                    retry_headers["Authorization"] = f"Bearer {api_key}"
                    console.log("[yellow]⚠️ 401 Unauthorized; retrying with Bearer token header...[/yellow]")
                    resp = requests.post(url, json=payload, headers=retry_headers, timeout=timeout)
                    resp.raise_for_status()
                else:
                    raise
            except Exception:
                raise
        data = resp.json()
        console.log(f"→ Response: {data}")
        return {"ok": True, "data": data, "status_code": int(resp.status_code)}
    except requests.exceptions.RequestException as e:
        console.log(f"[red]Create project failed:[/red] {e}")
        return {"ok": False, "error": str(e)}


@tool
def add_cost_item(project_id: str, item: Dict[str, Any], base_url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 10) -> Dict[str, Any]:
    """
    Add a cost item via POST {base_url}/projects/{project_id}/cost-items.
    Returns: { ok: bool, data?: dict, status_code?: int, error?: str }
    """
    def _ensure_auth(h: Optional[Dict[str, str]], base: str) -> Dict[str, str]:
        out = dict(h or {})
        if "Authorization" not in out:
            api_key = out.get("X-API-Key") or out.get("x-api-key")
            if api_key:
                out["Authorization"] = f"Bearer {api_key}"
            elif base.startswith("http://localhost:8000") or base.startswith("https://localhost:8000"):
                out["Authorization"] = "Bearer dev"
        return out

    def _coerce_cost_payload(it: Dict[str, Any]) -> Dict[str, Any]:
        # Mock expects {"items": [{"code": str, "amount": float}]}
        code = it.get("code") or it.get("itemCode") or "ITEM"
        amount: Optional[float] = None
        if "amount" in it:
            try:
                amount = float(it.get("amount") or 0)
            except Exception:
                amount = None
        if amount is None:
            q = it.get("quantity") or it.get("qty")
            u = it.get("unitCost") or it.get("unit_cost") or it.get("unit")
            try:
                if q is not None and u is not None:
                    amount = float(q) * float(u)
            except Exception:
                amount = None
        if amount is None:
            amount = 0.0
        return {"items": [{"code": code, "amount": float(amount)}]}

    path = f"/projects/{project_id}/cost-items"
    url = base_url.rstrip("/") + path
    console.rule("[bold blue]Add Cost Item[/bold blue]")
    console.log(f"POST {url}")
    try:
        send_item = _coerce_cost_payload(item or {})
        send_headers = _ensure_auth(headers, base_url)
        resp = requests.post(url, json=send_item, headers=send_headers, timeout=timeout)
        console.log(f"[green]→ Status: {resp.status_code}[/green]")
        try:
            resp.raise_for_status()
        except requests.exceptions.HTTPError as e:
            try:
                h = headers or {}
                api_key = h.get("X-API-Key") or h.get("x-api-key")
                if resp.status_code == 401 and api_key:
                    retry_headers = dict(h)
                    retry_headers.pop("X-API-Key", None)
                    retry_headers.pop("x-api-key", None)
                    retry_headers["Authorization"] = f"Bearer {api_key}"
                    console.log("[yellow]⚠️ 401 Unauthorized; retrying with Bearer token header...[/yellow]")
                    resp = requests.post(url, json=send_item, headers=retry_headers, timeout=timeout)
                    resp.raise_for_status()
                else:
                    raise
            except Exception:
                raise
        data = resp.json()
        console.log(f"→ Response: {data}")
        return {"ok": True, "data": data, "status_code": int(resp.status_code)}
    except requests.exceptions.RequestException as e:
        console.log(f"[red]Add cost item failed:[/red] {e}")
        return {"ok": False, "error": str(e)}

# extend available tools
available_tools = [search_documentation, check_api_status, create_project, add_cost_item]
