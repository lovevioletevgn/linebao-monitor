"""HTML 推送器：把本轮线报渲染成一个网页，方便本机预览/当面板看。"""
from __future__ import annotations

import html
import time
from pathlib import Path

from ..config import resolve_path
from ..sources import Item


def _esc(s: str) -> str:
    return html.escape(s or "", quote=True)


def _render(items: list[Item], generated_at: str) -> str:
    cards = []
    for it in items:
        price = f'<span class="price">¥{it.price}</span>' if it.price is not None else ""
        cards.append(
            f"""
      <article class="card">
        <h3 class="title">{_esc(it.title)}</h3>
        <div class="meta">{price}<span class="src">{_esc(it.source)}</span></div>
        <p class="sum">{_esc(it.summary[:180])}</p>
        <a class="link" href="{_esc(it.url)}" target="_blank" rel="noopener">查看详情 →</a>
      </article>"""
        )
    body = "\n".join(cards) if cards else '<p class="empty">本轮没有新线报。</p>'
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>线报监测 · 预览</title>
<style>
  :root {{ --bg:#f6f7f9; --card:#fff; --ink:#1a1d21; --muted:#6b7280; --accent:#d93025; --line:#e5e7eb; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
         font:15px/1.6 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif; }}
  header {{ background:#fff; border-bottom:1px solid var(--line); padding:22px 28px; }}
  h1 {{ margin:0 0 6px; font-size:20px; }}
  .sub {{ color:var(--muted); font-size:13px; }}
  .wrap {{ max-width:880px; margin:0 auto; padding:22px 16px 60px; }}
  .card {{ background:var(--card); border:1px solid var(--line); border-radius:10px;
           padding:16px 18px; margin-bottom:12px; }}
  .title {{ margin:0 0 8px; font-size:15px; font-weight:600; }}
  .meta {{ display:flex; align-items:center; gap:10px; margin-bottom:8px; }}
  .price {{ background:#fdecea; color:var(--accent); font-weight:700;
            padding:1px 8px; border-radius:5px; font-size:14px; }}
  .src {{ color:var(--muted); font-size:12px; }}
  .sum {{ color:#4b5563; font-size:13px; margin:0 0 10px; }}
  .link {{ color:#1a73e8; text-decoration:none; font-size:13px; }}
  .link:hover {{ text-decoration:underline; }}
  .empty {{ color:var(--muted); text-align:center; padding:40px; }}
</style>
</head>
<body>
<header>
  <h1>🛒 线报监测 · 预览</h1>
  <div class="sub">本轮 {len(items)} 条 · 生成于 {_esc(generated_at)} · 仅本地查看，未对外推送</div>
</header>
<div class="wrap">
{body}
</div>
</body>
</html>
"""


class HtmlNotifier:
    name = "html"

    def __init__(self, cfg: dict) -> None:
        self.output = cfg.get("output") or "data/preview.html"

    def send(self, items: list[Item]) -> bool:
        path: Path = resolve_path(self.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        doc = _render(items, time.strftime("%Y-%m-%d %H:%M:%S"))
        path.write_text(doc, encoding="utf-8")
        print(f"[html] 已生成预览: {path}")
        return True
