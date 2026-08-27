"""
Mock tools for testing Deezy without external dependencies.
"""
import json
from typing import Dict, Any
from datetime import datetime
from deezy.brain.models import BaseTool, ToolParameter, ToolResult, ToolCategory, RiskLevel
from deezy.brain import register_tool
import platform
import psutil


class SearchProductsTool(BaseTool):
    """Mock product search tool."""
    name = "search_products"
    description = "Search for products by query (mock implementation)"
    category = ToolCategory.PRODUCT_RESEARCH
    risk_level = RiskLevel.LOW
    parameters = [
        ToolParameter("query", "string", "Search query", required=True),
        ToolParameter("limit", "integer", "Maximum results", required=False, default=10),
    ]

    def execute(self, **kwargs) -> ToolResult:
        query = kwargs.get("query", "")
        limit = kwargs.get("limit", 10)

        # Mock product data
        mock_products = [
            {
                "asin": "B08N5WRWNW",
                "title": "BenQ ScreenBar Halo LED Desk Lamp",
                "price": "$129.99",
                "rating": 4.7,
                "category": "lighting-ambience",
                "url": "https://example.com/product1"
            },
            {
                "asin": "B09XYZ1234",
                "title": "Ergonomic Mesh Office Chair",
                "price": "$299.99",
                "rating": 4.5,
                "category": "chairs-ergonomics",
                "url": "https://example.com/product2"
            },
            {
                "asin": "B08ABC1234",
                "title": "Dual Monitor Arm Mount",
                "price": "$89.99",
                "rating": 4.6,
                "category": "desk-accessories",
                "url": "https://example.com/product3"
            },
            {
                "asin": "B08ABC1234",
                "title": "Cable Management Tray",
                "price": "$24.99",
                "rating": 4.4,
                "category": "cable-cord-organization",
                "url": "https://example.com/product4"
            },
            {
                "asin": "B09GHI9012",
                "title": "Bamboo Desk Organizer",
                "price": "$34.99",
                "rating": 4.3,
                "category": "desk-accessories",
                "url": "https://example.com/product5"
            },
        ]

        # Filter by query - match individual keywords
        query_words = query.lower().split()
        filtered = []
        for p in mock_products:
            title_lower = p["title"].lower()
            # Match if any query word is in the title
            if any(word in title_lower for word in query_words):
                filtered.append(p)

        # If no matches, return all products (fallback)
        if not filtered:
            filtered = mock_products

        results = filtered[:limit]

        return ToolResult(
            success=True,
            data={"products": results, "count": len(results)}
        )


class EvaluateProductTool(BaseTool):
    """Mock product evaluation tool."""
    name = "evaluate_product"
    description = "Evaluate a product against criteria (mock implementation)"
    category = ToolCategory.PRODUCT_RESEARCH
    risk_level = RiskLevel.LOW
    parameters = [
        ToolParameter("asin", "string", "Product ASIN", required=True),
        ToolParameter("criteria", "object", "Evaluation criteria", required=False),
    ]

    def execute(self, **kwargs) -> ToolResult:
        asin = kwargs.get("asin", "")
        criteria = kwargs.get("criteria", {})

        # Mock evaluation
        evaluation = {
            "asin": asin,
            "overall_score": 0.82,
            "scores": {
                "relevance": 0.85,
                "search_demand": 0.75,
                "competition": 0.65,
                "price": 0.80,
                "commission_potential": 0.70,
                "product_quality": 0.85,
                "content_potential": 0.75,
                "pinterest_potential": 0.80
            },
            "recommendation": "RECOMMEND",
            "notes": "Strong product with good ratings and commission potential"
        }

        return ToolResult(
            success=True,
            data=evaluation
        )


class GetSystemInfoTool(BaseTool):
    """Get system information."""
    name = "get_system_info"
    description = "Get system information (CPU, RAM, GPU, OS)"
    category = ToolCategory.SYSTEM
    risk_level = RiskLevel.LOW
    parameters = []

    def execute(self, **kwargs) -> ToolResult:
        info = {
            "os": platform.system(),
            "os_version": platform.version(),
            "processor": platform.processor(),
            "architecture": platform.machine(),
            "python_version": "3.14.6",
            "cpu_count": psutil.cpu_count(),
            "memory_total_gb": round(psutil.virtual_memory().total / (1024**3), 1),
            "memory_available_gb": round(psutil.virtual_memory().available / (1024**3), 1),
}
 
        return ToolResult(
            success=True,
            data=info
        )
 
 
class GetCurrentTimeTool(BaseTool):
    """Get the current local date and time."""
    name = "get_current_time"
    description = "Get the current local date, time, timezone, and day of week"
    category = ToolCategory.SYSTEM
    risk_level = RiskLevel.LOW
    parameters = []
 
    def execute(self, **kwargs) -> ToolResult:
        from datetime import datetime
        import time
 
        now = datetime.now()
        timezone_name = time.tzname[0] if time.tzname[0] else "UTC"
        if time.daylight:
            timezone_name = time.tzname[1]
 
        return ToolResult(
            success=True,
            data={
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M:%S"),
                "timezone": timezone_name,
                "day_of_week": now.strftime("%A"),
                "iso_format": now.isoformat(),
            }
        )
 
 
class ListRunningAppsTool(BaseTool):
    """List running applications."""
    name = "list_running_apps"
    description = "List currently running applications"
    category = ToolCategory.SYSTEM
    risk_level = RiskLevel.LOW
    parameters = []

    def execute(self, **kwargs) -> ToolResult:
        apps = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                info = proc.info
                if info['name'] and info['cpu_percent'] > 0:
                    apps.append({
                        "pid": info['pid'],
                        "name": info['name'],
                        "cpu_percent": info['cpu_percent'],
                        "memory_percent": info['memory_percent']
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # Sort by CPU usage
        apps.sort(key=lambda x: x['cpu_percent'], reverse=True)
        return ToolResult(
            success=True,
            data={"apps": apps[:20], "count": len(apps)}
        )


class CreateNotificationTool(BaseTool):
    """Create a Windows notification."""
    name = "create_notification"
    description = "Create a Windows toast notification"
    category = ToolCategory.SYSTEM
    risk_level = RiskLevel.LOW
    parameters = [
        ToolParameter("title", "string", "Notification title", required=True),
        ToolParameter("message", "string", "Notification message", required=True),
        ToolParameter("duration", "integer", "Duration in seconds", required=False, default=5),
    ]

    def execute(self, **kwargs) -> ToolResult:
        title = kwargs.get("title", "")
        message = kwargs.get("message", "")
        duration = kwargs.get("duration", 5)

        try:
            import subprocess
            ps_script = f'''
            [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
            $template = [Windows.UI.Notifications.ToastTemplateType]::ToastText02
            $xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($template)
            $text = $xml.GetElementsByTagName("text")
            $text.Item(0).AppendChild($xml.CreateTextNode("{title}")) | Out-Null
            $text.Item(1).AppendChild($xml.CreateTextNode("{message}")) | Out-Null
            $toast = New-Object Windows.UI.Notifications.ToastNotification($xml)
            [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Deezy").Show($toast)
            '''
            subprocess.run(["powershell", "-Command", ps_script], capture_output=True, timeout=10)

            return ToolResult(
                success=True,
                data={"title": title, "message": message, "duration": duration}
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class SearchFilesTool(BaseTool):
    """Search for files."""
    name = "search_files"
    description = "Search for files matching a pattern"
    category = ToolCategory.FILES
    risk_level = RiskLevel.LOW
    parameters = [
        ToolParameter("path", "string", "Directory to search", required=True),
        ToolParameter("pattern", "string", "File pattern (glob)", required=False, default="*"),
        ToolParameter("recursive", "boolean", "Search recursively", required=False, default=True),
    ]

    def execute(self, **kwargs) -> ToolResult:
        from pathlib import Path

        path = kwargs.get("path", ".")
        pattern = kwargs.get("pattern", "*")
        recursive = kwargs.get("recursive", True)

        try:
            path_obj = Path(path).expanduser()
            if not path_obj.exists():
                return ToolResult(success=False, error=f"Path does not exist: {path}")

            if recursive:
                files = list(path_obj.rglob(pattern))
            else:
                files = list(path_obj.glob(pattern))

            results = []
            for f in files[:100]:
                try:
                    stat = f.stat()
                    results.append({
                        "path": str(f),
                        "name": f.name,
                        "size": stat.st_size,
                        "size_mb": round(stat.st_size / (1024**2), 2),
                        "modified": stat.st_mtime,
                        "is_dir": f.is_dir(),
                        "extension": f.suffix,
                    })
                except:
                    pass

            return ToolResult(
                success=True,
                data={"files": results, "count": len(results), "searched_path": str(path_obj)}
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class ReadFileTool(BaseTool):
    """Read a file."""
    name = "read_file"
    description = "Read the contents of a file"
    category = ToolCategory.FILES
    risk_level = RiskLevel.LOW
    parameters = [
        ToolParameter("path", "string", "File path", required=True),
        ToolParameter("encoding", "string", "File encoding", required=False, default="utf-8"),
    ]

    def execute(self, **kwargs) -> ToolResult:
        from pathlib import Path

        path = kwargs.get("path", "")
        encoding = kwargs.get("encoding", "utf-8")

        try:
            path_obj = Path(path).expanduser()
            if not path_obj.exists():
                return ToolResult(success=False, error=f"File not found: {path}")

            content = path_obj.read_text(encoding=encoding)
            return ToolResult(
                success=True,
                data={"path": str(path_obj), "content": content, "size": len(content)}
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class CreateFileTool(BaseTool):
    """Create a file."""
    name = "create_file"
    description = "Create a new file with content"
    category = ToolCategory.FILES
    risk_level = RiskLevel.MEDIUM
    parameters = [
        ToolParameter("path", "string", "File path", required=True),
        ToolParameter("content", "string", "File content", required=False, default=""),
        ToolParameter("encoding", "string", "File encoding", required=False, default="utf-8"),
    ]

    def execute(self, **kwargs) -> ToolResult:
        from pathlib import Path

        path = kwargs.get("path", "")
        content = kwargs.get("content", "")
        encoding = kwargs.get("encoding", "utf-8")

        try:
            path_obj = Path(path).expanduser()
            path_obj.parent.mkdir(parents=True, exist_ok=True)
            path_obj.write_text(content, encoding=encoding)
            return ToolResult(
                success=True,
                data={"path": str(path_obj), "size": len(content.encode(encoding))}
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class SearchWebTool(BaseTool):
    """Search the web (mock implementation)."""
    name = "search_web"
    description = "Search the web for information (mock)"
    category = ToolCategory.WEB_RESEARCH
    risk_level = RiskLevel.LOW
    parameters = [
        ToolParameter("query", "string", "Search query", required=True),
        ToolParameter("limit", "integer", "Number of results", required=False, default=5),
    ]

    def execute(self, **kwargs) -> ToolResult:
        query = kwargs.get("query", "")
        limit = kwargs.get("limit", 5)

        mock_results = [
            {
                "title": f"Result for '{query}' - Item 1",
                "url": "https://example.com/1",
                "snippet": f"This is a mock result for {query}...",
            },
            {
                "title": f"Result for '{query}' - Item 2",
                "url": "https://example.com/2",
                "snippet": f"Another mock result about {query}...",
            },
        ]

        return ToolResult(
            success=True,
            data={"results": mock_results[:limit], "query": query}
        )


class CreateTaskTool(BaseTool):
    """Create a task."""
    name = "create_task"
    description = "Create a new task"
    category = ToolCategory.PRODUCTIVITY
    risk_level = RiskLevel.LOW
    parameters = [
        ToolParameter("title", "string", "Task title", required=True),
        ToolParameter("description", "string", "Task description", required=False),
        ToolParameter("risk_level", "string", "Risk level: low/medium/high", required=False, default="low"),
    ]

    def execute(self, **kwargs) -> ToolResult:
        from deezy.memory import get_db
        db = get_db()

        title = kwargs.get("title", "")
        description = kwargs.get("description", "")
        risk_level = kwargs.get("risk_level", "low")

        with get_db().transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO tasks (name, description, status, risk_level, created_at)
                VALUES (?, ?, 'pending', ?, datetime('now'))
            """, (title, description, risk_level))
            task_id = cursor.lastrowid

        return ToolResult(
            success=True,
            data={"task_id": task_id, "title": title, "risk_level": risk_level}
        )


class ListTasksTool(BaseTool):
    """List tasks."""
    name = "list_tasks"
    description = "List tasks"
    category = ToolCategory.PRODUCTIVITY
    risk_level = RiskLevel.LOW
    parameters = [
        ToolParameter("status", "string", "Filter by status", required=False),
        ToolParameter("limit", "integer", "Maximum tasks", required=False, default=20),
    ]

    def execute(self, **kwargs) -> ToolResult:
        from deezy.memory import get_db
        db = get_db()

        status = kwargs.get("status")
        limit = kwargs.get("limit", 20)

        if status:
            tasks = db.fetchall("SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC LIMIT ?", (status, limit))
        else:
            tasks = db.fetchall("SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,))

        return ToolResult(
            success=True,
            data={"tasks": [dict(t) for t in tasks], "count": len(tasks)}
        )


def register_mock_tools():
    """Register all mock tools."""
    register_tool(SearchProductsTool())
    register_tool(EvaluateProductTool())
    register_tool(GetSystemInfoTool())
    register_tool(GetCurrentTimeTool())
    register_tool(ListRunningAppsTool())
    register_tool(CreateNotificationTool())
    register_tool(SearchFilesTool())
    register_tool(ReadFileTool())
    register_tool(CreateFileTool())
    register_tool(SearchWebTool())
    register_tool(CreateTaskTool())
    register_tool(ListTasksTool())


# Register tools at module import time
register_mock_tools()


if __name__ == "__main__":
    print("Mock tools registered")