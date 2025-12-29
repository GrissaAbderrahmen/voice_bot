"""
Conversation management with memory and persistence.
Tracks message history and saves conversations to disk.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from ..core.logger import get_logger
from ..core.config import Config

logger = get_logger("nova.ai.conversation")


class ConversationManager:
    """
    Manages conversation history with persistence.
    """
    
    def __init__(
        self,
        system_prompt: Optional[str] = None,
        max_history: int = 20,
        persist: bool = True,
        persist_path: Optional[str] = None,
        session_id: Optional[str] = None
    ):
        """
        Initialize conversation manager.
        
        Args:
            system_prompt: System prompt for the assistant
            max_history: Maximum messages to keep in history
            persist: Whether to save conversations to disk
            persist_path: Directory to save conversations
            session_id: Session ID (None = generate new)
        """
        config = Config()
        
        self.system_prompt = system_prompt or config.system_prompt
        self.max_history = max_history
        self.persist = persist
        self.persist_path = Path(persist_path or config.conversations_path)
        
        # Session management
        self.session_id = session_id or self._generate_session_id()
        self.created_at = datetime.now()
        
        # Message history
        self._messages: List[Dict[str, str]] = []
        
        # Add system prompt
        if self.system_prompt:
            self._messages.append({
                "role": "system",
                "content": self.system_prompt
            })
        
        # Ensure persist directory exists
        if self.persist:
            self.persist_path.mkdir(parents=True, exist_ok=True)
        
        logger.debug(f"Conversation started: {self.session_id}")
    
    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        short_uuid = str(uuid.uuid4())[:8]
        return f"{timestamp}_{short_uuid}"
    
    @property
    def messages(self) -> List[Dict[str, str]]:
        """Get all messages including system prompt."""
        return self._messages.copy()
    
    @property
    def messages_for_llm(self) -> List[Dict[str, str]]:
        """Get messages formatted for LLM (respects max_history)."""
        if len(self._messages) <= self.max_history + 1:  # +1 for system prompt
            return self._messages.copy()
        
        # Keep system prompt + last N messages
        return [self._messages[0]] + self._messages[-(self.max_history):]
    
    @property
    def user_messages(self) -> List[str]:
        """Get only user messages."""
        return [m["content"] for m in self._messages if m["role"] == "user"]
    
    @property
    def assistant_messages(self) -> List[str]:
        """Get only assistant messages."""
        return [m["content"] for m in self._messages if m["role"] == "assistant"]
    
    def add_user_message(self, content: str) -> None:
        """Add a user message to history."""
        self._messages.append({
            "role": "user",
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        logger.debug(f"User: {content[:50]}...")
        
        if self.persist:
            self._auto_save()
    
    def add_assistant_message(self, content: str) -> None:
        """Add an assistant message to history."""
        self._messages.append({
            "role": "assistant",
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        logger.debug(f"Assistant: {content[:50]}...")
        
        if self.persist:
            self._auto_save()
    
    def add_message(self, role: str, content: str) -> None:
        """Add a message with specified role."""
        if role == "user":
            self.add_user_message(content)
        elif role == "assistant":
            self.add_assistant_message(content)
        else:
            self._messages.append({"role": role, "content": content})
    
    def clear_history(self, keep_system: bool = True) -> None:
        """Clear conversation history."""
        if keep_system and self.system_prompt:
            self._messages = [{
                "role": "system",
                "content": self.system_prompt
            }]
        else:
            self._messages = []
        
        logger.info("Conversation history cleared")
    
    def get_context_summary(self) -> str:
        """Get a brief summary of the conversation context."""
        user_count = len(self.user_messages)
        assistant_count = len(self.assistant_messages)
        return f"Session {self.session_id}: {user_count} user messages, {assistant_count} responses"
    
    def _auto_save(self) -> None:
        """Auto-save on each message if persistence is enabled."""
        try:
            self.save()
        except Exception as e:
            logger.warning(f"Auto-save failed: {e}")
    
    def save(self, path: Optional[str] = None) -> str:
        """
        Save conversation to JSON file.
        
        Args:
            path: Custom save path (None = use default)
        
        Returns:
            Path to saved file
        """
        if path:
            save_path = Path(path)
        else:
            save_path = self.persist_path / f"{self.session_id}.json"
        
        data = {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": datetime.now().isoformat(),
            "system_prompt": self.system_prompt,
            "messages": [
                {k: v for k, v in m.items() if k != "timestamp"} 
                for m in self._messages if m["role"] != "system"
            ],
            "metadata": {
                "user_message_count": len(self.user_messages),
                "assistant_message_count": len(self.assistant_messages)
            }
        }
        
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.debug(f"Conversation saved: {save_path}")
        return str(save_path)
    
    @classmethod
    def load(cls, path: str) -> 'ConversationManager':
        """
        Load conversation from JSON file.
        
        Args:
            path: Path to conversation file
        
        Returns:
            Loaded ConversationManager instance
        """
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Create instance
        manager = cls(
            system_prompt=data.get("system_prompt"),
            session_id=data.get("session_id"),
            persist=True
        )
        
        # Restore messages
        for msg in data.get("messages", []):
            manager.add_message(msg["role"], msg["content"])
        
        logger.info(f"Conversation loaded: {path}")
        return manager
    
    @classmethod
    def list_sessions(cls, persist_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all saved conversation sessions.
        
        Args:
            persist_path: Path to search for sessions
        
        Returns:
            List of session info dicts
        """
        config = Config()
        path = Path(persist_path or config.conversations_path)
        
        if not path.exists():
            return []
        
        sessions = []
        for file in path.glob("*.json"):
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    sessions.append({
                        "session_id": data.get("session_id"),
                        "created_at": data.get("created_at"),
                        "updated_at": data.get("updated_at"),
                        "message_count": data.get("metadata", {}).get("user_message_count", 0),
                        "path": str(file)
                    })
            except Exception as e:
                logger.warning(f"Failed to read session file {file}: {e}")
        
        # Sort by updated_at descending
        sessions.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return sessions
    
    @classmethod
    def load_latest(cls, persist_path: Optional[str] = None) -> Optional['ConversationManager']:
        """Load the most recent conversation session."""
        sessions = cls.list_sessions(persist_path)
        
        if sessions:
            return cls.load(sessions[0]["path"])
        return None
    
    def __len__(self) -> int:
        """Number of messages (excluding system)."""
        return len([m for m in self._messages if m["role"] != "system"])
    
    def __repr__(self) -> str:
        return f"ConversationManager(session={self.session_id}, messages={len(self)})"
