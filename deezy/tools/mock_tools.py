"""
Built-in tools for Deezy.

Most of these are deliberately simple stand-ins: the product tools read a small
bundled sample catalog and ``search_web`` returns canned results. The file and
system tools do real work on the machine they run on, so in demo mode
(``DEEZY_DEMO=1``) the file tools are confined to a scratch directory and the
system tools are not registered at all.
"""

import os
import platform
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from deezy.brain import register_tool
from deezy.brain.models import BaseTool, RiskLevel, ToolCategory, ToolParameter, ToolResult
from deezy.config import is_demo

MAX_FILE_BYTES = 64 * 1024
MAX_DEMO_FILES = 50

# --- Sample catalog (fictional prices in USD) --------------------------------

SAMPLE_CATALOG: List[Dict[str, Any]] = [
    {
        "asin": "DZ0001",
        "title": "Adjustable LED Desk Lamp with USB Port",
        "price": 34.99,
        "rating": 4.6,
        "category": "lighting-ambience",
    },
    {
        "asin": "DZ0002",
        "title": "Architect Clamp Desk Lamp",
        "price": 27.50,
        "rating": 4.4,
        "category": "lighting-ambience",
    },
    {
        "asin": "DZ0003",
        "title": "Monitor Light Bar for Desk Setups",
        "price": 49.00,
        "rating": 4.7,
        "category": "lighting-ambience",
    },
    {
        "asin": "DZ0004",
        "title": "Warm Glow Bedside Lamp",
        "price": 19.99,
        "rating": 4.2,
        "category": "lighting-ambience",
    },
    {
        "asin": "DZ0005",
        "title": "Ergonomic Mesh Office Chair",
        "price": 189.00,
        "rating": 4.5,
        "category": "chairs-ergonomics",
    },
    {
        "asin": "DZ0006",
        "title": "Lumbar Support Cushion for Chairs",
        "price": 21.99,
        "rating": 4.3,
        "category": "chairs-ergonomics",
    },
    {
        "asin": "DZ0007",
        "title": "Dual Monitor Arm Mount",
        "price": 79.99,
        "rating": 4.6,
        "category": "desk-accessories",
    },
    {"asin": "DZ0008", "title": "Bamboo Desk Organizer", "price": 24.99, "rating": 4.3, "category": "desk-accessories"},
    {
        "asin": "DZ0009",
        "title": "Under-Desk Cable Management Tray",
        "price": 16.99,
        "rating": 4.4,
        "category": "cable-cord-organization",
    },
    {
        "asin": "DZ0010",
        "title": "Cable Sleeve and Clip Set",
        "price": 11.49,
        "rating": 4.1,
        "category": "cable-cord-organization",
    },
    {
        "asin": "DZ0011",
        "title": "Stackable Storage Shelf Riser",
        "price": 29.00,
        "rating": 4.5,
        "category": "storage-shelving",
    },
    {
        "asin": "DZ0012",
        "title": "Dorm Study Desk Fold-Away Table",
        "price": 64.00,
        "rating": 4.0,
        "category": "study-dorm",
    },
]

_STOPWORDS = {
    "a",
    "an",
    "the",
    "for",
    "me",
    "find",
    "search",
    "some",
    "good",
    "best",
    "under",
    "below",
    "less",
    "than",
    "cheap",
    "with",
    "and",
    "of",
    "to",
    "please",
    "product",
    "products",
    "research",
    "discover",
    "buy",
    "show",
}


def _terms(text: str) -> List[str]:
    cleaned = "".join(c if c.isalnum() else " " for c in text.lower())
    return [w for w in cleaned.split() if w not in _STOPWORDS and not w.isdigit()]


def _find_product(asin: str):
    return next((p for p in SAMPLE_CATALOG if p["asin"] == asin), None)


class SearchProductsTool(BaseTool):
    name = "search_products"
    description = "Search the bundled sample product catalog by keywords, optionally under a maximum price"
    category = ToolCategory.PRODUCT_RESEARCH
    risk_level = RiskLevel.LOW
    parameters = [
        ToolParameter("query", "string", "Search query", required=True),
        ToolParameter("limit", "integer", "Maximum results", required=False, default=5),
        ToolParameter("max_price", "number", "Maximum price in USD", required=False),
    ]

    def execute(self, **kwargs) -> ToolResult:
        query = str(kwargs.get("query", "")).strip()
        if not query:
            return ToolResult(success=False, error="Invalid argument: query is required")
        try:
            limit = max(1, min(int(kwargs.get("limit", 5)), 20))
            max_price = kwargs.get("max_price")
            max_price = float(max_price) if max_price not in (None, "") else None
        except (TypeError, ValueError):
            return ToolResult(success=False, error="Invalid argument: limit and max_price must be numbers")

        terms = _terms(query)
        scored = []
        for product in SAMPLE_CATALOG:
            if max_price is not None and product["price"] > max_price:
                continue
            haystack = f"{product['title']} {product['category']}".lower()
            score = sum(1 for t in terms if t in haystack)
            if score:
                scored.append((score, product["rating"], product))
        scored.sort(key=lambda x: (-x[0], -x[1]))
        results = [dict(p, price=f"${p['price']:.2f}", price_value=p["price"]) for _, _, p in scored[:limit]]
        return ToolResult(
            success=True,
            data={
                "products": results,
                "count": len(results),
                "query": query,
                "max_price": max_price,
                "source": "sample catalog",
            },
        )


class EvaluateProductTool(BaseTool):
    name = "evaluate_product"
    description = "Score a product from the sample catalog on price, quality and overall fit (simple heuristic)"
    category = ToolCategory.PRODUCT_RESEARCH
    risk_level = RiskLevel.LOW
    parameters = [
        ToolParameter("asin", "string", "Product ASIN from search_products", required=True),
        ToolParameter("criteria", "string", "Comma-separated criteria (informational)", required=False),
    ]

    def execute(self, **kwargs) -> ToolResult:
        asin = str(kwargs.get("asin", "")).strip().strip('"')
        product = _find_product(asin)
        if product is None:
            return ToolResult(success=False, error=f"Product not found in sample catalog: {asin!r}")
        quality = round(product["rating"] / 5, 2)
        prices = [p["price"] for p in SAMPLE_CATALOG]
        price_score = round(1 - (product["price"] - min(prices)) / (max(prices) - min(prices)), 2)
        overall = round(0.6 * quality + 0.4 * price_score, 2)
        recommendation = "RECOMMEND" if overall >= 0.75 else "REVIEW" if overall >= 0.55 else "SKIP"
        return ToolResult(
            success=True,
            data={
                "asin": asin,
                "title": product["title"],
                "price": f"${product['price']:.2f}",
                "overall_score": overall,
                "scores": {"quality": quality, "price": price_score},
                "recommendation": recommendation,
                "method": "0.6 x rating/5 + 0.4 x relative price position in the sample catalog",
            },
        )


class GetCurrentTimeTool(BaseTool):
    name = "get_current_time"
    description = "Get the current date, time, timezone and day of week on the server"
    category = ToolCategory.SYSTEM
    risk_level = RiskLevel.LOW
    parameters = []

    def execute(self, **kwargs) -> ToolResult:
        now = datetime.now().astimezone()
        return ToolResult(
            success=True,
            data={
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M:%S"),
                "timezone": now.tzname() or "UTC",
                "day_of_week": now.strftime("%A"),
                "iso_format": now.isoformat(),
            },
        )


class GetSystemInfoTool(BaseTool):
    name = "get_system_info"
    description = "Get system information (OS, CPU count, memory) of the machine Deezy runs on"
    category = ToolCategory.SYSTEM
    risk_level = RiskLevel.LOW
    parameters = []

    def execute(self, **kwargs) -> ToolResult:
        import psutil

        memory = psutil.virtual_memory()
        return ToolResult(
            success=True,
            data={
                "os": platform.system(),
                "os_version": platform.release(),
                "architecture": platform.machine(),
                "python_version": platform.python_version(),
                "cpu_count": psutil.cpu_count(),
                "memory_total_gb": round(memory.total / 1024**3, 1),
                "memory_available_gb": round(memory.available / 1024**3, 1),
            },
        )


class ListRunningAppsTool(BaseTool):
    name = "list_running_apps"
    description = "List the processes using the most memory on the machine Deezy runs on"
    category = ToolCategory.SYSTEM
    risk_level = RiskLevel.LOW
    parameters = []

    def execute(self, **kwargs) -> ToolResult:
        import psutil

        apps = []
        for proc in psutil.process_iter(["pid", "name", "memory_percent"]):
            try:
                info = proc.info
                if info["name"]:
                    apps.append(
                        {
                            "pid": info["pid"],
                            "name": info["name"],
                            "memory_percent": round(info["memory_percent"] or 0, 2),
                        }
                    )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        apps.sort(key=lambda a: a["memory_percent"], reverse=True)
        return ToolResult(success=True, data={"apps": apps[:20], "count": len(apps)})


# --- File tools -----------------------------------------------------------------


def _sandbox_root() -> Path:
    root = Path(os.environ.get("DEEZY_SANDBOX_DIR") or Path(tempfile.gettempdir()) / "deezy-sandbox")
    root.mkdir(parents=True, exist_ok=True)
    welcome = root / "welcome.txt"
    if not welcome.exists():
        welcome.write_text(
            "This is the Deezy demo sandbox.\nFiles here are temporary and shared with nobody.\n", encoding="utf-8"
        )
    return root


def _resolve_path(raw: str) -> Path:
    """Local mode: the path as given. Demo mode: confined to the sandbox directory."""
    if not is_demo():
        return Path(raw).expanduser()
    root = _sandbox_root().resolve()
    relative = Path(str(raw).replace("\\", "/").lstrip("/~"))
    candidate = (root / relative).resolve()
    if candidate != root and root not in candidate.parents:
        raise PermissionError("Access denied: path is outside the demo sandbox")
    return candidate


def _display(path: Path) -> str:
    if is_demo():
        root = _sandbox_root().resolve()
        try:
            return "/" + path.resolve().relative_to(root).as_posix()
        except ValueError:
            return path.name
    return str(path)


class SearchFilesTool(BaseTool):
    name = "search_files"
    description = "Search for files matching a glob pattern"
    category = ToolCategory.FILES
    risk_level = RiskLevel.LOW
    parameters = [
        ToolParameter("path", "string", "Directory to search", required=False, default="."),
        ToolParameter("pattern", "string", "File pattern (glob)", required=False, default="*"),
        ToolParameter("recursive", "boolean", "Search recursively", required=False, default=True),
    ]

    def execute(self, **kwargs) -> ToolResult:
        try:
            base = _resolve_path(kwargs.get("path") or ("/" if is_demo() else "."))
            pattern = kwargs.get("pattern") or "*"
            if not base.exists():
                return ToolResult(success=False, error=f"Path does not exist: {_display(base)}")
            matches = base.rglob(pattern) if kwargs.get("recursive", True) else base.glob(pattern)
            results = []
            for f in matches:
                if len(results) >= 100:
                    break
                try:
                    stat = f.stat()
                except OSError:
                    continue
                results.append({"path": _display(f), "name": f.name, "size": stat.st_size, "is_dir": f.is_dir()})
            return ToolResult(
                success=True, data={"files": results, "count": len(results), "searched_path": _display(base)}
            )
        except PermissionError as e:
            return ToolResult(success=False, error=str(e))
        except Exception as e:
            return ToolResult(success=False, error=f"Invalid argument: {e}")


class ReadFileTool(BaseTool):
    name = "read_file"
    description = "Read the contents of a text file"
    category = ToolCategory.FILES
    risk_level = RiskLevel.LOW
    parameters = [
        ToolParameter("path", "string", "File path", required=True),
    ]

    def execute(self, **kwargs) -> ToolResult:
        raw = str(kwargs.get("path", "")).strip()
        if not raw:
            return ToolResult(success=False, error="Invalid argument: path is required")
        try:
            path = _resolve_path(raw)
            if not path.is_file():
                return ToolResult(success=False, error=f"File not found: {raw}")
            if path.stat().st_size > MAX_FILE_BYTES:
                return ToolResult(success=False, error=f"File too large (limit {MAX_FILE_BYTES // 1024} KB)")
            content = path.read_text(encoding="utf-8", errors="replace")
            return ToolResult(success=True, data={"path": _display(path), "content": content, "size": len(content)})
        except PermissionError as e:
            return ToolResult(success=False, error=str(e))
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class CreateFileTool(BaseTool):
    name = "create_file"
    description = "Create a new text file with content"
    category = ToolCategory.FILES
    risk_level = RiskLevel.MEDIUM
    parameters = [
        ToolParameter("path", "string", "File path", required=True),
        ToolParameter("content", "string", "File content", required=False, default=""),
    ]

    def execute(self, **kwargs) -> ToolResult:
        raw = str(kwargs.get("path", "")).strip()
        content = str(kwargs.get("content", ""))
        if not raw:
            return ToolResult(success=False, error="Invalid argument: path is required")
        if len(content.encode("utf-8")) > MAX_FILE_BYTES:
            return ToolResult(success=False, error=f"Content too large (limit {MAX_FILE_BYTES // 1024} KB)")
        try:
            path = _resolve_path(raw)
            if is_demo() and not path.exists() and sum(1 for _ in _sandbox_root().rglob("*")) >= MAX_DEMO_FILES:
                return ToolResult(success=False, error="Demo sandbox is full")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return ToolResult(success=True, data={"path": _display(path), "size": len(content.encode("utf-8"))})
        except PermissionError as e:
            return ToolResult(success=False, error=str(e))
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class SearchWebTool(BaseTool):
    name = "search_web"
    description = "Web search stand-in: returns canned example results, no network access"
    category = ToolCategory.WEB_RESEARCH
    risk_level = RiskLevel.LOW
    parameters = [
        ToolParameter("query", "string", "Search query", required=True),
        ToolParameter("limit", "integer", "Number of results", required=False, default=3),
    ]

    def execute(self, **kwargs) -> ToolResult:
        query = str(kwargs.get("query", "")).strip()
        if not query:
            return ToolResult(success=False, error="Invalid argument: query is required")
        limit = max(1, min(int(kwargs.get("limit", 3) or 3), 5))
        results = [
            {
                "title": f"Example result {i} for '{query}'",
                "url": f"https://example.com/{i}",
                "snippet": f"Canned snippet {i} about {query}.",
            }
            for i in range(1, 6)
        ]
        return ToolResult(
            success=True, data={"results": results[:limit], "query": query, "note": "canned results, no live search"}
        )


# --- Todo tools -------------------------------------------------------------------


def _ensure_todo_table(db) -> None:
    db.execute(
        """CREATE TABLE IF NOT EXISTS todo_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )"""
    )


class CreateTaskTool(BaseTool):
    name = "create_task"
    description = "Add an item to the to-do list"
    category = ToolCategory.PRODUCTIVITY
    risk_level = RiskLevel.LOW
    parameters = [
        ToolParameter("title", "string", "Item title", required=True),
        ToolParameter("description", "string", "Item description", required=False),
    ]

    def execute(self, **kwargs) -> ToolResult:
        from deezy.memory import get_db

        title = str(kwargs.get("title", "")).strip()[:200]
        if not title:
            return ToolResult(success=False, error="Invalid argument: title is required")
        db = get_db()
        _ensure_todo_table(db)
        with db.transaction() as conn:
            cur = conn.execute(
                "INSERT INTO todo_items (title, description) VALUES (?, ?)",
                (title, str(kwargs.get("description") or "")[:1000]),
            )
        return ToolResult(success=True, data={"id": cur.lastrowid, "title": title, "status": "pending"})


class ListTasksTool(BaseTool):
    name = "list_tasks"
    description = "List items on the to-do list"
    category = ToolCategory.PRODUCTIVITY
    risk_level = RiskLevel.LOW
    parameters = [
        ToolParameter("status", "string", "Filter by status", required=False),
        ToolParameter("limit", "integer", "Maximum items", required=False, default=20),
    ]

    def execute(self, **kwargs) -> ToolResult:
        from deezy.memory import get_db

        db = get_db()
        _ensure_todo_table(db)
        limit = max(1, min(int(kwargs.get("limit", 20) or 20), 100))
        status = kwargs.get("status")
        if status:
            rows = db.fetchall("SELECT * FROM todo_items WHERE status = ? ORDER BY id DESC LIMIT ?", (status, limit))
        else:
            rows = db.fetchall("SELECT * FROM todo_items ORDER BY id DESC LIMIT ?", (limit,))
        items = [dict(r) for r in rows]
        return ToolResult(success=True, data={"items": items, "count": len(items)})


def register_mock_tools():
    """Register the built-in tools. System tools are skipped in demo mode."""
    tools = [
        SearchProductsTool(),
        EvaluateProductTool(),
        GetCurrentTimeTool(),
        SearchFilesTool(),
        ReadFileTool(),
        CreateFileTool(),
        SearchWebTool(),
        CreateTaskTool(),
        ListTasksTool(),
    ]
    if not is_demo():
        tools += [GetSystemInfoTool(), ListRunningAppsTool()]
    for tool in tools:
        register_tool(tool)


register_mock_tools()
