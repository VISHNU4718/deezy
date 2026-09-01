"""
FastAPI backend for Deezy Web UI.

Provides REST API and WebSocket for the React frontend.
"""

import os
import json
import uuid
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional, Set
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from deezy.memory import get_db
from deezy.core.agent import Agent
from deezy.brain import get_tool_registry
from deezy.config import get_settings


# --- Pydantic Models ---

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"


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
    objective: str


class TaskResponse(BaseModel):
    task_id: int


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
    title: str


class ConversationUpdate(BaseModel):
    title: str


class ConversationMessage(BaseModel):
    role: str
    content: str
    metadata: Optional[Dict[str, Any]] = None
    timestamp: str


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
    category: str
    content: str
    tags: List[str] = []
    importance: float = 1.0
    source: str = "user"


class MemoryUpdate(BaseModel):
    category: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[List[str]] = None
    importance: Optional[float] = None


class ToolSchema(BaseModel):
    name: str
    description: str
    category: str
    risk_level: str
    parameters: Dict[str, Any]


# --- WebSocket Connection Manager ---

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.task_subscriptions: Dict[int, Set[str]] = {}

    async def connect(self, client_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        # Remove from all task subscriptions
        for task_id, subs in self.task_subscriptions.items():
            subs.discard(client_id)

    def subscribe_to_task(self, client_id: str, task_id: int):
        if task_id not in self.task_subscriptions:
            self.task_subscriptions[task_id] = set()
        self.task_subscriptions[task_id].add(client_id)

    async def send_to_task(self, task_id: int, message: Dict[str, Any]):
        if task_id in self.task_subscriptions:
            disconnected = []
            for client_id in self.task_subscriptions[task_id]:
                if client_id in self.active_connections:
                    try:
                        await self.active_connections[client_id].send_json(message)
                    except Exception:
                        disconnected.append(client_id)
            for client_id in disconnected:
                self.disconnect(client_id)


manager = ConnectionManager()


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


def init_memory_table():
    """Ensure memories table exists (from M7)."""
    db = get_db_connection()
    db.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            content TEXT NOT NULL,
            tags TEXT,
            importance REAL DEFAULT 1.0,
            source TEXT,
            access_count INTEGER DEFAULT 0,
            last_accessed TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


# --- Lifespan ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_conversation_tables()
    init_memory_table()
    yield
    # Shutdown
    pass


# --- FastAPI App ---

app = FastAPI(
    title="Deezy API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- REST Endpoints ---

@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse()


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
            "enabled": getattr(settings, 'voice', {}).get('enabled', True),
            "stt_provider": getattr(settings, 'voice', {}).get('stt_provider', 'web_speech'),
            "tts_provider": getattr(settings, 'voice', {}).get('tts_provider', 'web_speech'),
            "language": getattr(settings, 'voice', {}).get('language', 'en-US'),
            "auto_play": getattr(settings, 'voice', {}).get('auto_play', True),
            "continuous": getattr(settings, 'voice', {}).get('continuous', False),
        },
        approval={
            "risk_levels": settings.approval.risk_levels,
            "notification_methods": settings.approval.notification_methods,
        }
    )


@app.put("/api/settings", response_model=SettingsResponse)
async def update_settings_endpoint(update: SettingsUpdate):
    settings = get_settings()
    
    if update.llm:
        settings.llm.provider = update.llm.get("provider", settings.llm.provider)
        settings.llm.model = update.llm.get("model", settings.llm.model)
        settings.llm.temperature = update.llm.get("temperature", settings.llm.temperature)
        settings.llm.max_tokens = update.llm.get("max_tokens", settings.llm.max_tokens)
    
    if update.agent:
        settings.agent.max_iterations = update.agent.get("max_iterations", settings.agent.max_iterations)
        settings.agent.max_tool_calls_per_iteration = update.agent.get("max_tool_calls_per_iteration", settings.agent.max_tool_calls_per_iteration)
        settings.agent.enable_memory = update.agent.get("enable_memory", settings.agent.enable_memory)
        settings.agent.memory_limit = update.agent.get("memory_limit", settings.agent.memory_limit)
        settings.agent.approval_required_for_high_risk = update.agent.get("approval_required_for_high_risk", settings.agent.approval_required_for_high_risk)
        settings.agent.approval_required_for_medium_risk = update.agent.get("approval_required_for_medium_risk", settings.agent.approval_required_for_medium_risk)
        settings.agent.auto_approve_low_risk = update.agent.get("auto_approve_low_risk", settings.agent.auto_approve_low_risk)
    
    # Save to config file (simplified - in production would write to YAML)
    # For now, just return updated settings
    return await get_settings_endpoint()


# --- Tasks Endpoints ---

@app.get("/api/tasks", response_model=List[Task])
async def list_tasks(status: Optional[str] = Query(None)):
    db = get_db_connection()
    query = "SELECT * FROM tasks"
    params = ()
    if status:
        query += " WHERE status = ?"
        params = (status,)
    query += " ORDER BY created_at DESC LIMIT 50"
    
    rows = db.fetchall(query, params)
    tasks = []
    for row in rows:
        task = Task(
            id=row["id"],
            objective=row["objective"] or row["name"] or "",
            user_input=row["input_data"] or "",
            status=row["status"],
            created_at=row["created_at"],
            completed_at=row["completed_at"],
            steps=[],
            risk_level=row["risk_level"] or "low",
        )
        # Load steps from agent_decisions or reconstruct
        tasks.append(task)
    return tasks


@app.post("/api/tasks", response_model=TaskResponse)
async def create_task_endpoint(task_create: TaskCreate):
    db = get_db_connection()
    
    with db.transaction() as conn:
        cursor = conn.execute("""
            INSERT INTO tasks (name, description, objective, status, risk_level, input_data, created_at)
            VALUES (?, ?, ?, 'planning', 'low', ?, datetime('now'))
        """, (task_create.objective[:100], task_create.objective, task_create.objective, json.dumps({"objective": task_create.objective})))
        task_id = cursor.lastrowid
    
    return TaskResponse(task_id=task_id)


@app.get("/api/tasks/{task_id}", response_model=Task)
async def get_task_endpoint(task_id: int):
    db = get_db_connection()
    row = db.fetchone("SELECT * FROM tasks WHERE id = ?", (task_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return Task(
        id=row["id"],
        objective=row["objective"] or row["name"] or "",
        user_input=row["input_data"] or "",
        status=row["status"],
        created_at=row["created_at"],
        completed_at=row["completed_at"],
        steps=[],
        risk_level=row["risk_level"] or "low",
    )


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
        conn.execute("""
            INSERT INTO conversations (id, title, created_at, updated_at)
            VALUES (?, ?, ?, ?)
        """, (conv_id, conv.title, now, now))
    
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
    
    msg_rows = db.fetchall("""
        SELECT * FROM conversation_messages 
        WHERE conversation_id = ? 
        ORDER BY created_at ASC
    """, (conv_id,))
    
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
        conn.execute("""
            UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?
        """, (update.title, now, conv_id))
    
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
        conn.execute("""
            INSERT INTO conversation_messages (conversation_id, role, content, metadata, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (conv_id, message.role, message.content, json.dumps(message.metadata) if message.metadata else None, now))
        
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
        conn.execute("""
            INSERT INTO conversations (id, title, created_at, updated_at)
            VALUES (?, ?, ?, ?)
        """, (conv_id, data.title, now, now))
        
        for msg in data.messages:
            conn.execute("""
                INSERT INTO conversation_messages (conversation_id, role, content, metadata, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (conv_id, msg.role, msg.content, json.dumps(msg.metadata) if msg.metadata else None, msg.timestamp))
    
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
    branch_messages = conv.messages[:branch.message_index]
    
    new_conv = await import_conversation_endpoint(ConversationImport(
        title=branch.title,
        messages=branch_messages,
    ))
    
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
        cursor = conn.execute("""
            INSERT INTO memories (category, content, tags, importance, source, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (memory.category, memory.content, json.dumps(memory.tags), memory.importance, memory.source, now, now))
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
    return await list_tasks()


# --- WebSocket Endpoint ---

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(client_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "subscribe_task":
                task_id = data.get("task_id")
                if task_id:
                    manager.subscribe_to_task(client_id, task_id)
                    await websocket.send_json({"type": "subscribed", "task_id": task_id})
    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(client_id)


# --- Serve React Frontend ---

# Mount static files (built frontend)
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Serve index.html for all non-API routes
        if full_path.startswith("api/") or full_path.startswith("ws/"):
            raise HTTPException(status_code=404)
        index_path = os.path.join(static_dir, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        raise HTTPException(status_code=404)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)