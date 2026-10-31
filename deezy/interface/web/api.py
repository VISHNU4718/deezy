"""
FastAPI backend for the Deezy web UI.

Plain REST: tasks are planned and executed inside the request (no WebSockets,
no background threads), so the same app runs locally and on serverless hosts.
"""

import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import deezy.tools.mock_tools  # noqa: F401  (registers the built-in tools)
from deezy.brain import get_tool_registry
from deezy.config import get_settings, is_demo
from deezy.core.agent import MAX_OBJECTIVE_LENGTH, Agent
from deezy.core.planner import Plan
from deezy.memory import get_db

# --- Pydantic Models ---


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
    demo: bool = False


class SettingsResponse(BaseModel):
    llm: Dict[str, Any]
    agent: Dict[str, Any]
    voice: Dict[str, Any]
    approval: Dict[str, Any]


class SettingsUpdate(BaseModel):
    llm: Optional[Dict[str, Any]] = None
    agent: Optional[Dict[str, Any]] = None
    voice: Optional[Dict[str, Any]] = None
    approval: Optional[Dict[str, Any]] = None


class TaskCreate(BaseModel):
    objective: str = Field(min_length=1, max_length=MAX_OBJECTIVE_LENGTH)


class TaskStep(BaseModel):
    step_id: str
    description: str
    tool: str
    params: Dict[str, Any] = {}
    status: str = "pending"
    risk_level: str = "low"
    verified: bool = False
    result: Optional[Any] = None
    error: Optional[str] = None


class Task(BaseModel):
    id: int
    objective: str
    user_input: str = ""
    status: str = "pending"
    created_at: str
    completed_at: Optional[str] = None
    steps: List[TaskStep] = []
    current_step_index: int = 0
    plan_version: int = 1
    risk_level: str = "low"
    result: Optional[Dict[str, Any]] = None


class ConversationBase(BaseModel):
    id: str
    title: str
    message_count: int = 0
    created_at: str
    updated_at: str


class ConversationCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class ConversationUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class ConversationMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant|tool)$")
    content: str = Field(min_length=1, max_length=20000)
    metadata: Optional[Dict[str, Any]] = None
    timestamp: str = ""


class ConversationWithMessages(ConversationBase):
    messages: List[ConversationMessage] = []


class ConversationExport(BaseModel):
    id: str
    title: str
    messages: List[ConversationMessage]
    created_at: str
    updated_at: str


class ConversationImport(BaseModel):
    title: str
    messages: List[ConversationMessage]


class ConversationBranch(BaseModel):
    conversation_id: str
    message_index: int
    title: str


class ConversationBranchResult(BaseModel):
    conversation_id: str


class Memory(BaseModel):
    id: int
    category: str
    content: str
    tags: List[str] = []
    importance: float = 1.0
    source: str = "user"
    access_count: int = 0
    last_accessed: Optional[str] = None
    created_at: str
    updated_at: str


class MemoryCreate(BaseModel):
    category: str = Field(min_length=1, max_length=50)
    content: str = Field(min_length=1, max_length=2000)
    tags: List[str] = Field(default=[], max_length=20)
    importance: float = Field(default=1.0, ge=0.0, le=1.0)
    source: str = Field(default="user", max_length=20)


class MemoryUpdate(BaseModel):
    category: Optional[str] = Field(default=None, min_length=1, max_length=50)
    content: Optional[str] = Field(default=None, min_length=1, max_length=2000)
    tags: Optional[List[str]] = Field(default=None, max_length=20)
    importance: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class ToolSchema(BaseModel):
    name: str
    description: str
    category: str
    risk_level: str
    parameters: Dict[str, Any]


# --- Database Helper Functions ---


def get_db_connection():
    return get_db()


def init_conversation_tables():
    """Initialize conversation-related tables if not exist."""
    db = get_db_connection()
    db.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS conversation_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.execute("""
        CREATE INDEX IF NOT EXISTS idx_conversation_messages_conv_id
        ON conversation_messages(conversation_id)
    """)


def init_app_tables():
    """Tables owned by the web layer (the rest come from the memory schema)."""
    db = get_db_connection()
    db.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)


# --- FastAPI App ---

app = FastAPI(title="Deezy API", version="0.1.0")

# Idempotent, and done at import time so it also works on hosts that skip ASGI lifespan events.
init_conversation_tables()
init_app_tables()

# The UI is served from the same origin. Cross-origin access is only needed for
# the Vite dev server, or when DEEZY_CORS_ORIGINS lists extra origins.
_cors_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
_cors_origins += [o.strip() for o in os.environ.get("DEEZY_CORS_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
)


# --- REST Endpoints ---


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(demo=is_demo())


@app.get("/api/settings", response_model=SettingsResponse)
async def get_settings_endpoint():
    settings = get_settings()
    return SettingsResponse(
        llm={
            "provider": settings.llm.provider,
            "model": settings.llm.model,
            "temperature": settings.llm.temperature,
            "max_tokens": settings.llm.max_tokens,
        },
        agent={
            "max_iterations": settings.agent.max_iterations,
            "max_tool_calls_per_iteration": settings.agent.max_tool_calls_per_iteration,
            "enable_memory": settings.agent.enable_memory,
            "memory_limit": settings.agent.memory_limit,
            "approval_required_for_high_risk": settings.agent.approval_required_for_high_risk,
            "approval_required_for_medium_risk": settings.agent.approval_required_for_medium_risk,
            "auto_approve_low_risk": settings.agent.auto_approve_low_risk,
        },
        voice={
            "enabled": getattr(settings, "voice", {}).get("enabled", True),
            "stt_provider": getattr(settings, "voice", {}).get("stt_provider", "web_speech"),
            "tts_provider": getattr(settings, "voice", {}).get("tts_provider", "web_speech"),
            "language": getattr(settings, "voice", {}).get("language", "en-US"),
            "auto_play": getattr(settings, "voice", {}).get("auto_play", True),
            "continuous": getattr(settings, "voice", {}).get("continuous", False),
        },
        approval={
            "risk_levels": settings.approval.risk_levels,
            "notification_methods": settings.approval.notification_methods,
        },
    )


VALID_PROVIDERS = {"local", "openrouter", "openai", "anthropic", "mock"}

# field -> (type, min, max); bools have no range
_AGENT_FIELDS = {
    "max_iterations": (int, 1, 50),
    "max_tool_calls_per_iteration": (int, 1, 20),
    "enable_memory": (bool, None, None),
    "memory_limit": (int, 1, 500),
    "approval_required_for_high_risk": (bool, None, None),
    "approval_required_for_medium_risk": (bool, None, None),
    "auto_approve_low_risk": (bool, None, None),
}
_LLM_FIELDS = {
    "model": (str, None, None),
    "temperature": (float, 0.0, 2.0),
    "max_tokens": (int, 1, 32000),
}


def _check(section: str, name: str, value: Any, spec: tuple) -> Any:
    kind, low, high = spec
    ok = (
        isinstance(value, bool)
        if kind is bool
        else (
            isinstance(value, (int, float)) and not isinstance(value, bool)
            if kind in (int, float)
            else isinstance(value, str)
        )
    )
    if not ok:
        raise HTTPException(status_code=422, detail=f"{section}.{name} has the wrong type")
    if kind is int and isinstance(value, float) and value != int(value):
        raise HTTPException(status_code=422, detail=f"{section}.{name} must be a whole number")
    if low is not None and not (low <= value <= high):
        raise HTTPException(status_code=422, detail=f"{section}.{name} must be between {low} and {high}")
    if kind is str and not (1 <= len(value) <= 200):
        raise HTTPException(status_code=422, detail=f"{section}.{name} must be 1-200 characters")
    return kind(value) if kind in (int, float) else value


def _validated_updates(update: SettingsUpdate) -> Dict[str, Dict[str, Any]]:
    clean: Dict[str, Dict[str, Any]] = {"llm": {}, "agent": {}}
    for name, value in (update.llm or {}).items():
        if name == "provider":
            if value not in VALID_PROVIDERS:
                raise HTTPException(status_code=422, detail=f"llm.provider must be one of {sorted(VALID_PROVIDERS)}")
            if is_demo() and value != "mock":
                raise HTTPException(status_code=403, detail="The hosted demo is locked to the mock provider")
            clean["llm"]["provider"] = value
        elif name in _LLM_FIELDS:
            if is_demo() and name == "model":
                continue
            clean["llm"][name] = _check("llm", name, value, _LLM_FIELDS[name])
    for name, value in (update.agent or {}).items():
        if name in _AGENT_FIELDS:
            clean["agent"][name] = _check("agent", name, value, _AGENT_FIELDS[name])
    return clean


def _apply_settings(clean: Dict[str, Dict[str, Any]]) -> None:
    settings = get_settings()
    for name, value in clean.get("llm", {}).items():
        setattr(settings.llm, name, value)
    for name, value in clean.get("agent", {}).items():
        setattr(settings.agent, name, value)


def load_saved_settings() -> None:
    """Re-apply settings the user saved earlier (stored in the app_settings table)."""
    row = get_db_connection().fetchone("SELECT value FROM app_settings WHERE key = 'overrides'")
    if not row:
        return
    try:
        saved = json.loads(row["value"])
        if is_demo():
            saved.get("llm", {}).pop("provider", None)
            saved.get("llm", {}).pop("model", None)
        _apply_settings(saved)
    except (ValueError, TypeError, AttributeError):
        pass


load_saved_settings()


@app.put("/api/settings", response_model=SettingsResponse)
async def update_settings_endpoint(update: SettingsUpdate):
    clean = _validated_updates(update)
    _apply_settings(clean)

    db = get_db_connection()
    row = db.fetchone("SELECT value FROM app_settings WHERE key = 'overrides'")
    saved = json.loads(row["value"]) if row else {"llm": {}, "agent": {}}
    for section in ("llm", "agent"):
        saved.setdefault(section, {}).update(clean[section])
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO app_settings (key, value) VALUES ('overrides', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (json.dumps(saved),),
        )
    return await get_settings_endpoint()


# --- Tasks Endpoints ---


def _task_from_row(row) -> Task:
    """Rebuild a Task (with steps and result message) from the stored plan."""
    output = json.loads(row["output_data"]) if row["output_data"] else {}
    plan = output.get("plan") or {}
    steps = []
    for s in plan.get("steps", []):
        steps.append(
            TaskStep(
                step_id=s["step_id"],
                description=s["description"],
                tool=s["tool"],
                params=s.get("params") or {},
                status=s.get("status", "pending"),
                risk_level=s.get("risk_level", "low"),
                verified=s.get("status") == "completed",
                result=s.get("result"),
                error=s.get("error"),
            )
        )
    risks = [s.risk_level for s in steps]
    risk = "high" if "high" in risks else "medium" if "medium" in risks else "low"
    message = output.get("message")
    return Task(
        id=row["id"],
        objective=row["objective"] or row["name"] or "",
        user_input=row["objective"] or "",
        status=row["status"],
        created_at=str(row["created_at"]),
        completed_at=str(row["completed_at"]) if row["completed_at"] else None,
        steps=steps,
        risk_level=risk,
        result={"message": message} if message else None,
    )


def _get_task_row(task_id: int):
    row = get_db_connection().fetchone("SELECT * FROM tasks WHERE id = ?", (task_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Task not found")
    return row


@app.get("/api/tasks", response_model=List[Task])
async def list_tasks(status: Optional[str] = Query(None)):
    query = "SELECT * FROM tasks"
    params: tuple = ()
    if status:
        query += " WHERE status = ?"
        params = (status,)
    query += " ORDER BY id DESC LIMIT 50"
    return [_task_from_row(r) for r in get_db_connection().fetchall(query, params)]


@app.post("/api/tasks", response_model=Task)
async def create_task_endpoint(task_create: TaskCreate):
    """Plan the objective. Runs it right away unless a step needs approval."""
    agent = Agent()
    try:
        plan = agent.plan(task_create.objective)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    status = "waiting_for_approval" if plan.requires_approval else "running"
    now = datetime.now().isoformat(timespec="seconds")
    db = get_db_connection()
    with db.transaction() as conn:
        cur = conn.execute(
            "INSERT INTO tasks (name, objective, status, approval_required, output_data, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                plan.objective[:100],
                plan.objective,
                status,
                plan.requires_approval,
                json.dumps({"plan": plan.to_dict()}),
                now,
                now,
            ),
        )
        task_id = cur.lastrowid
    if not plan.requires_approval:
        agent.execute(plan, task_id=task_id)
    return _task_from_row(_get_task_row(task_id))


@app.get("/api/tasks/{task_id}", response_model=Task)
async def get_task_endpoint(task_id: int):
    return _task_from_row(_get_task_row(task_id))


def _waiting_plan(task_id: int) -> Plan:
    row = _get_task_row(task_id)
    if row["status"] != "waiting_for_approval":
        raise HTTPException(status_code=409, detail=f"Task is {row['status']}, not waiting for approval")
    return Plan.from_dict(json.loads(row["output_data"])["plan"])


@app.post("/api/tasks/{task_id}/approve", response_model=Task)
async def approve_task_endpoint(task_id: int):
    plan = _waiting_plan(task_id)
    db = get_db_connection()
    with db.transaction() as conn:
        conn.execute(
            "UPDATE tasks SET status = 'running', approved_by = 'user', approved_at = ? WHERE id = ?",
            (datetime.now().isoformat(timespec="seconds"), task_id),
        )
    Agent().execute(plan, task_id=task_id)
    return _task_from_row(_get_task_row(task_id))


@app.post("/api/tasks/{task_id}/reject", response_model=Task)
async def reject_task_endpoint(task_id: int):
    plan = _waiting_plan(task_id)
    plan.status = "cancelled"
    for step in plan.steps:
        step.status = "skipped"
        step.error = "plan rejected"
    message = "Plan was rejected; nothing was run."
    db = get_db_connection()
    with db.transaction() as conn:
        conn.execute(
            "UPDATE tasks SET status = 'cancelled', output_data = ?, completed_at = ?, updated_at = ? WHERE id = ?",
            (
                json.dumps({"plan": plan.to_dict(), "message": message}),
                datetime.now().isoformat(timespec="seconds"),
                datetime.now().isoformat(timespec="seconds"),
                task_id,
            ),
        )
    return _task_from_row(_get_task_row(task_id))


# --- Conversations Endpoints ---


@app.get("/api/conversations", response_model=List[ConversationBase])
async def list_conversations():
    db = get_db_connection()
    rows = db.fetchall("""
        SELECT c.*, COUNT(cm.id) as message_count
        FROM conversations c
        LEFT JOIN conversation_messages cm ON c.id = cm.conversation_id
        GROUP BY c.id
        ORDER BY c.updated_at DESC
    """)

    return [
        ConversationBase(
            id=row["id"],
            title=row["title"],
            message_count=row["message_count"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]


@app.post("/api/conversations", response_model=ConversationBase)
async def create_conversation_endpoint(conv: ConversationCreate):
    db = get_db_connection()
    conv_id = str(uuid.uuid4())
    now = datetime.now().isoformat()

    with db.transaction() as conn:
        conn.execute(
            """
            INSERT INTO conversations (id, title, created_at, updated_at)
            VALUES (?, ?, ?, ?)
        """,
            (conv_id, conv.title, now, now),
        )

    return ConversationBase(
        id=conv_id,
        title=conv.title,
        message_count=0,
        created_at=now,
        updated_at=now,
    )


@app.get("/api/conversations/{conv_id}", response_model=ConversationWithMessages)
async def get_conversation_endpoint(conv_id: str):
    db = get_db_connection()
    conv_row = db.fetchone("SELECT * FROM conversations WHERE id = ?", (conv_id,))
    if not conv_row:
        raise HTTPException(status_code=404, detail="Conversation not found")

    msg_rows = db.fetchall(
        """
        SELECT * FROM conversation_messages
        WHERE conversation_id = ?
        ORDER BY created_at ASC
    """,
        (conv_id,),
    )

    messages = [
        ConversationMessage(
            role=row["role"],
            content=row["content"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else None,
            timestamp=row["created_at"],
        )
        for row in msg_rows
    ]

    return ConversationWithMessages(
        id=conv_row["id"],
        title=conv_row["title"],
        message_count=len(messages),
        created_at=conv_row["created_at"],
        updated_at=conv_row["updated_at"],
        messages=messages,
    )


@app.patch("/api/conversations/{conv_id}", response_model=ConversationBase)
async def update_conversation_endpoint(conv_id: str, update: ConversationUpdate):
    db = get_db_connection()
    now = datetime.now().isoformat()

    with db.transaction() as conn:
        conn.execute(
            """
            UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?
        """,
            (update.title, now, conv_id),
        )

    return await get_conversation_endpoint(conv_id)


@app.delete("/api/conversations/{conv_id}")
async def delete_conversation_endpoint(conv_id: str):
    db = get_db_connection()
    with db.transaction() as conn:
        conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
    return {"success": True}


@app.post("/api/conversations/{conv_id}/messages")
async def add_conversation_message_endpoint(conv_id: str, message: ConversationMessage):
    db = get_db_connection()

    # Verify conversation exists
    conv = db.fetchone("SELECT id FROM conversations WHERE id = ?", (conv_id,))
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    now = datetime.now().isoformat()
    with db.transaction() as conn:
        conn.execute(
            """
            INSERT INTO conversation_messages (conversation_id, role, content, metadata, created_at)
            VALUES (?, ?, ?, ?, ?)
        """,
            (conv_id, message.role, message.content, json.dumps(message.metadata) if message.metadata else None, now),
        )

        # Update conversation updated_at
        conn.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conv_id))

    return {"success": True}


@app.get("/api/conversations/{conv_id}/export", response_model=ConversationExport)
async def export_conversation_endpoint(conv_id: str):
    conv = await get_conversation_endpoint(conv_id)
    return ConversationExport(
        id=conv.id,
        title=conv.title,
        messages=conv.messages,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )


@app.post("/api/conversations/import", response_model=ConversationBase)
async def import_conversation_endpoint(data: ConversationImport):
    db = get_db_connection()
    conv_id = str(uuid.uuid4())
    now = datetime.now().isoformat()

    with db.transaction() as conn:
        conn.execute(
            """
            INSERT INTO conversations (id, title, created_at, updated_at)
            VALUES (?, ?, ?, ?)
        """,
            (conv_id, data.title, now, now),
        )

        for msg in data.messages:
            conn.execute(
                """
                INSERT INTO conversation_messages (conversation_id, role, content, metadata, created_at)
                VALUES (?, ?, ?, ?, ?)
            """,
                (conv_id, msg.role, msg.content, json.dumps(msg.metadata) if msg.metadata else None, msg.timestamp),
            )

    return ConversationBase(
        id=conv_id,
        title=data.title,
        message_count=len(data.messages),
        created_at=now,
        updated_at=now,
    )


@app.post("/api/conversations/{conv_id}/branch", response_model=ConversationBranchResult)
async def branch_conversation_endpoint(conv_id: str, branch: ConversationBranch):
    # For now, just create a new conversation with the same messages up to the branch point
    conv = await get_conversation_endpoint(conv_id)
    branch_messages = conv.messages[: branch.message_index]

    new_conv = await import_conversation_endpoint(
        ConversationImport(
            title=branch.title,
            messages=branch_messages,
        )
    )

    return ConversationBranchResult(conversation_id=new_conv.id)


# --- Memories Endpoints ---


@app.get("/api/memories", response_model=List[Memory])
async def list_memories(category: Optional[str] = Query(None)):
    db = get_db_connection()
    query = "SELECT * FROM memories"
    params = ()
    if category:
        query += " WHERE category = ?"
        params = (category,)
    query += " ORDER BY importance DESC, created_at DESC"

    rows = db.fetchall(query, params)
    return [
        Memory(
            id=row["id"],
            category=row["category"],
            content=row["content"],
            tags=json.loads(row["tags"]) if row["tags"] else [],
            importance=row["importance"],
            source=row["source"],
            access_count=row["access_count"],
            last_accessed=row["last_accessed"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]


@app.post("/api/memories", response_model=Memory)
async def create_memory_endpoint(memory: MemoryCreate):
    db = get_db_connection()
    now = datetime.now().isoformat()

    with db.transaction() as conn:
        cursor = conn.execute(
            """
            INSERT INTO memories (category, content, tags, importance, source, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (memory.category, memory.content, json.dumps(memory.tags), memory.importance, memory.source, now, now),
        )
        memory_id = cursor.lastrowid

    return Memory(
        id=memory_id,
        category=memory.category,
        content=memory.content,
        tags=memory.tags,
        importance=memory.importance,
        source=memory.source,
        access_count=0,
        last_accessed=None,
        created_at=now,
        updated_at=now,
    )


@app.patch("/api/memories/{memory_id}", response_model=Memory)
async def update_memory_endpoint(memory_id: int, update: MemoryUpdate):
    db = get_db_connection()
    row = db.fetchone("SELECT * FROM memories WHERE id = ?", (memory_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Memory not found")

    now = datetime.now().isoformat()
    updates = []
    params = []

    if update.category is not None:
        updates.append("category = ?")
        params.append(update.category)
    if update.content is not None:
        updates.append("content = ?")
        params.append(update.content)
    if update.tags is not None:
        updates.append("tags = ?")
        params.append(json.dumps(update.tags))
    if update.importance is not None:
        updates.append("importance = ?")
        params.append(update.importance)

    if updates:
        updates.append("updated_at = ?")
        params.append(now)
        params.append(memory_id)

        with db.transaction() as conn:
            conn.execute(f"UPDATE memories SET {', '.join(updates)} WHERE id = ?", tuple(params))

    return await get_memory_endpoint(memory_id)


@app.get("/api/memories/{memory_id}", response_model=Memory)
async def get_memory_endpoint(memory_id: int):
    db = get_db_connection()
    row = db.fetchone("SELECT * FROM memories WHERE id = ?", (memory_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Memory not found")

    return Memory(
        id=row["id"],
        category=row["category"],
        content=row["content"],
        tags=json.loads(row["tags"]) if row["tags"] else [],
        importance=row["importance"],
        source=row["source"],
        access_count=row["access_count"],
        last_accessed=row["last_accessed"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@app.delete("/api/memories/{memory_id}")
async def delete_memory_endpoint(memory_id: int):
    db = get_db_connection()
    with db.transaction() as conn:
        conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
    return {"success": True}


@app.delete("/api/memories")
async def clear_memories_endpoint(category: Optional[str] = Query(None)):
    db = get_db_connection()
    if category:
        with db.transaction() as conn:
            conn.execute("DELETE FROM memories WHERE category = ?", (category,))
    else:
        with db.transaction() as conn:
            conn.execute("DELETE FROM memories")
    return {"success": True}


# --- Tools Endpoint ---


@app.get("/api/tools", response_model=List[ToolSchema])
async def list_tools_endpoint():
    registry = get_tool_registry()
    tools = registry.get_all()
    return [
        ToolSchema(
            name=tool.name,
            description=tool.description,
            category=tool.category.value,
            risk_level=tool.risk_level.value,
            parameters=tool.get_schema()["function"]["parameters"],
        )
        for tool in tools
    ]


# --- History Endpoint ---


@app.get("/api/history", response_model=List[Task])
async def get_history_endpoint():
    return await list_tasks(status=None)


# --- Serve React Frontend (after `npm run build` in this directory) ---

static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist")
if os.path.isdir(static_dir):
    app.mount("/assets", StaticFiles(directory=os.path.join(static_dir, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404)
        candidate = os.path.realpath(os.path.join(static_dir, full_path))
        if full_path and candidate.startswith(os.path.realpath(static_dir) + os.sep) and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(static_dir, "index.html"))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8000")))
