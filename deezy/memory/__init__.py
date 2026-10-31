"""
Memory management for Deezy.
Handles short-term conversation context and persistent long-term memory.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from deezy.config import get_settings
from deezy.memory.database import get_db, init_db


@dataclass
class ConversationTurn:
    """A single turn in a conversation."""

    role: str  # user, assistant, tool
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryEntry:
    """A persistent memory entry."""

    id: Optional[int] = None
    category: str = ""  # fact, preference, project, task, decision, observation
    content: str = ""
    tags: List[str] = field(default_factory=list)
    importance: float = 1.0  # 0.0 to 1.0
    source: str = "user"  # user, agent, system
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    last_accessed: Optional[datetime] = None


class ShortTermMemory:
    """Short-term conversation context (in-memory)."""

    def __init__(self, max_turns: int = 50):
        self.max_turns = max_turns
        self.turns: List[ConversationTurn] = []
        self.current_session_id = f"session_{int(datetime.now().timestamp())}"

    def add_turn(self, role: str, content: str, metadata: Dict = None):
        """Add a conversation turn."""
        turn = ConversationTurn(role=role, content=content, metadata=metadata or {})
        self.turns.append(turn)

        # Trim to max turns
        if len(self.turns) > self.max_turns:
            self.turns = self.turns[-self.max_turns :]

    def get_recent_turns(self, n: int = 10) -> List[ConversationTurn]:
        """Get last N turns."""
        return self.turns[-n:]

    def get_context_string(self, max_turns: int = 10) -> str:
        """Get formatted conversation context for LLM."""
        turns = self.get_recent_turns(max_turns)
        if not turns:
            return "No previous conversation."

        lines = []
        for turn in turns:
            role_label = turn.role.upper()
            lines.append(f"[{role_label}] {turn.content}")
        return "\n".join(lines)

    def clear(self):
        """Clear conversation history."""
        self.turns = []


class LongTermMemory:
    """Persistent long-term memory using SQLite."""

    def __init__(self, db_path: str = "data/deezy.db"):
        self.db = get_db()

    def store(self, entry: MemoryEntry) -> int:
        """Store a memory entry."""
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO memories (category, content, tags, importance, source, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    entry.category,
                    entry.content,
                    json.dumps(entry.tags),
                    entry.importance,
                    entry.source,
                    entry.created_at,
                    entry.updated_at,
                ),
            )
            entry.id = cursor.lastrowid
            return entry.id

    def retrieve(
        self, query: str = "", category: str = None, limit: int = 10, min_importance: float = 0.0
    ) -> List[MemoryEntry]:
        """Retrieve relevant memories."""
        params = []

        # Build query
        where_parts = ["importance >= ?"]
        params.append(min_importance)

        if category:
            where_parts.append("category = ?")
            params.append(category)

        if query:
            # Simple text search in content
            where_parts.append("(content LIKE ? OR tags LIKE ?)")
            params.extend([f"%{query}%", f"%{query}%"])

        where_clause = " AND ".join(where_parts)

        query_sql = f"""
            SELECT * FROM memories
            WHERE {where_clause}
            ORDER BY importance DESC, access_count DESC, last_accessed DESC
            LIMIT ?
        """
        params.append(limit)

        rows = self.db.fetchall(query_sql, tuple(params))
        return [self._row_to_memory(row) for row in rows]

    def _row_to_memory(self, row) -> MemoryEntry:
        """Convert database row to MemoryEntry."""
        return MemoryEntry(
            id=row["id"],
            category=row["category"],
            content=row["content"],
            tags=json.loads(row["tags"]) if row["tags"] else [],
            importance=row["importance"],
            source=row["source"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            access_count=row["access_count"],
            last_accessed=row["last_accessed"],
        )

    def update_access(self, memory_id: int):
        """Update access statistics."""
        self.db.execute(
            """
            UPDATE memories
            SET access_count = access_count + 1,
                last_accessed = ?
            WHERE id = ?
        """,
            (datetime.now(), memory_id),
        )

    def add_fact(self, content: str, category: str = "fact", importance: float = 1.0, tags: List[str] = None) -> int:
        """Quick add a fact."""
        entry = MemoryEntry(category=category, content=content, tags=tags or [], importance=importance, source="user")
        return self.store(entry)

    def add_preference(self, content: str, importance: float = 0.8) -> int:
        """Add a user preference."""
        return self.add_fact(content, "preference", importance, ["preference"])

    def add_observation(self, content: str, category: str = "observation", importance: float = 0.7) -> int:
        """Add an observation."""
        return self.add_fact(content, category, importance, ["observation"])


class MemoryManager:
    """Unified memory interface combining short and long-term memory."""

    def __init__(self, db_path: str = "data/deezy.db"):
        self.short_term = ShortTermMemory()
        self.long_term = LongTermMemory()
        self.settings = get_settings()

    def add_conversation_turn(self, role: str, content: str, metadata: Dict = None):
        """Add a conversation turn to short-term memory."""
        self.short_term.add_turn(role, content, metadata)

        # Also store important exchanges in long-term memory
        if role == "user" and len(content) > 20:
            self.long_term.add_fact(
                f"User said: {content}", category="conversation", importance=0.5, tags=["conversation", "user_input"]
            )

    def get_context_for_llm(self, max_short_term: int = 10, max_long_term: int = 5) -> str:
        """Build context string for LLM with both memory types."""
        parts = []

        # Short-term conversation context
        st_context = self.short_term.get_context_string(max_short_term)
        if st_context != "No previous conversation.":
            parts.append(f"RECENT CONVERSATION:\n{st_context}")

        # Relevant long-term memories
        ltm = self.long_term.retrieve("", limit=max_long_term)
        if ltm:
            parts.append("RELEVANT MEMORIES:")
            for mem in ltm:
                parts.append(f"- [{mem.category}] {mem.content} (importance: {mem.importance})")

        return "\n\n".join(parts) if parts else "No previous context."

    def remember(self, content: str, category: str = "fact", importance: float = 1.0, tags: List[str] = None) -> int:
        """Store something in long-term memory."""
        return self.long_term.add_fact(content, category, importance, tags)

    def recall(self, query: str = "", category: str = None, limit: int = 5) -> List[MemoryEntry]:
        """Recall relevant memories."""
        return self.long_term.retrieve(query, category, limit)

    def get_conversation_history(self, limit: int = 20) -> List[Dict]:
        """Get formatted conversation history."""
        turns = self.short_term.get_recent_turns(limit)
        return [{"role": t.role, "content": t.content, "timestamp": t.timestamp.isoformat()} for t in turns]

    def clear_short_term(self):
        """Clear short-term conversation history."""
        self.short_term.clear()

    def get_stats(self) -> Dict:
        """Get memory statistics."""
        ltm_count = len(self.long_term.retrieve(""))
        return {
            "short_term_turns": len(self.short_term.turns),
            "long_term_memories": ltm_count,
            "session_id": self.short_term.current_session_id,
        }


# Global memory manager instance
_memory_manager: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    """Get global memory manager instance."""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager


def init_memory(db_path: str = "data/deezy.db"):
    """Initialize memory system."""
    init_db(db_path)
    get_memory_manager()


__all__ = [
    "ConversationTurn",
    "MemoryEntry",
    "ShortTermMemory",
    "LongTermMemory",
    "MemoryManager",
    "get_memory_manager",
    "init_memory",
]
