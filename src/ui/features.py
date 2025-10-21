from pathlib import Path
import json
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()


def _read_roadmap() -> dict:
    p = Path(__file__).resolve().parents[1] / "product" / "roadmap.json"
    return json.loads(p.read_text(encoding="utf-8"))


@router.get("/features", response_class=HTMLResponse)
async def features(request: Request):
    data = _read_roadmap()
    return f"""
<!doctype html>
<html><head>
<meta charset="utf-8"/>
<title>Features Coming Soon</title>
<style>
body {{ font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 24px; color:#111; }}
.wrap {{ max-width: 980px; margin: 0 auto; }}
h1 {{ margin-bottom: 8px; }}
.card {{ border:1px solid rgba(0,0,0,.08); border-radius:14px; padding:12px 14px; background:#fff; box-shadow:0 1px 2px rgba(0,0,0,.04); margin-bottom:10px; }}
.small {{ color:#666; font-size:13px; }}
.pill {{ display:inline-block; padding:2px 8px; border-radius:999px; font-size:12px; opacity:.9; border:1px solid rgba(0,0,0,.08); }}
.pill-next {{ background:#f0f7ff; }}
.pill-later {{ background:#f7f7f7; }}
.dot-new {{ display:inline-block; width:6px; height:6px; background:#5ac8fa; border-radius:999px; margin-right:6px; }}
.section-title {{ margin: 18px 0 8px; }}
hr {{ border:none; border-top:1px solid #eee; margin:16px 0; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>Features Coming Soon</h1>
  <div class="small">Version {data.get('version')} • Updated {data.get('updated')}</div>

  <div class="section-title"><h3>Next up</h3></div>
  {''.join([
    f'''<div class="card">
          <div><span class="dot-new"></span><b>{i['title']}</b> <span class="pill pill-next">Next</span></div>
          <div class="small">{i['desc']}</div>
        </div>'''
    for i in data.get('next', [])[:6]
  ])}

  <div class="section-title"><h3>Later</h3></div>
  {''.join([
    f'''<div class="card">
          <div><b>{i['title']}</b> <span class="pill pill-later">Later</span></div>
          <div class="small">{i['desc']}</div>
        </div>'''
    for i in data.get('later', [])[:4]
  ])}

  <hr/>
  <div class="small">Tip: turn on the CLI startup banner with <code>SHOW_FEATURES=1</code> in your .env.</div>
</div>
</body></html>
"""

