# Unified memory management system

from typing import List, Dict
from datetime import datetime


class UnifiedConversationMemory:
    """Manages conversation memory for both Azure AI Foundry and EDI queries"""
    
    def __init__(self):
        # Azure AI Foundry thread management
        self.session_threads = {}
        # EDI conversation memory
        self.edi_memories = {}
        # Cross-system conversation tracking
        self.conversation_registry = {}
    
    def get_or_create_azure_thread(self, conversation_id: str, project_client):
        """Get or create Azure AI Foundry thread for a conversation"""
        if conversation_id not in self.session_threads:
            thread = project_client.agents.threads.create()
            self.session_threads[conversation_id] = thread
            # Register this conversation
            self._register_conversation(conversation_id, "azure_thread", thread.id)
        else:
            thread = project_client.agents.threads.get(self.session_threads[conversation_id].id)
        return thread
    
    def get_edi_conversation_history(self, conversation_id: str) -> List[Dict]:
        """Get EDI conversation history for a given conversation ID"""
        if conversation_id and conversation_id in self.edi_memories:
            return self.edi_memories[conversation_id]
        return []
    
    def add_edi_message(self, conversation_id: str, role: str, content: str, metadata: Dict = None):
        """Add a message to EDI conversation history"""
        if not conversation_id:
            return
            
        if conversation_id not in self.edi_memories:
            self.edi_memories[conversation_id] = []
        
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        
        self.edi_memories[conversation_id].append(message)
        
        # Keep only last 20 messages to prevent memory bloat
        if len(self.edi_memories[conversation_id]) > 20:
            self.edi_memories[conversation_id] = self.edi_memories[conversation_id][-20:]
        
        # Register this conversation if not already registered
        self._register_conversation(conversation_id, "edi_memory", None)
    
    def get_unified_context(self, conversation_id: str, current_query: str, max_messages: int = 5) -> str:
        """Get unified conversation context from both systems"""
        context_parts = []
        
        # Get EDI conversation history
        edi_history = self.get_edi_conversation_history(conversation_id)
        if edi_history:
            recent_edi = edi_history[-max_messages:] if len(edi_history) > max_messages else edi_history
            for msg in recent_edi:
                if msg["role"] == "user":
                    context_parts.append(f"User (EDI): {msg['content']}")
                elif msg["role"] == "assistant":
                    context_parts.append(f"Assistant (EDI): {msg['content']}")
        
        # Get Azure thread messages if available
        if conversation_id in self.session_threads:
            try:
                # This would require access to project_client, so we'll handle it in the calling function
                pass
            except:
                pass
        
        if context_parts:
            return "Previous conversation context:\n" + "\n".join(context_parts) + "\n\n"
        
        return ""
    
    def get_edi_relevant_context(self, conversation_id: str, current_query: str, max_messages: int = 5) -> str:
        """Get relevant context from EDI conversation history"""
        history = self.get_edi_conversation_history(conversation_id)
        
        if not history:
            return ""
        
        # Get recent messages (excluding the current one)
        recent_messages = history[-max_messages:] if len(history) > max_messages else history
        
        context_parts = []
        for msg in recent_messages:
            if msg["role"] == "user":
                context_parts.append(f"User: {msg['content']}")
            elif msg["role"] == "assistant":
                context_parts.append(f"Assistant: {msg['content']}")
        
        if context_parts:
            return "Previous conversation context:\n" + "\n".join(context_parts) + "\n\n"
        
        return ""
    
    def _register_conversation(self, conversation_id: str, system_type: str, thread_id: str = None):
        """Register a conversation in the cross-system registry"""
        if conversation_id not in self.conversation_registry:
            self.conversation_registry[conversation_id] = {
                "azure_thread_id": None,
                "edi_memory_active": False,
                "created_at": datetime.now().isoformat(),
                "last_activity": datetime.now().isoformat()
            }
        
        if system_type == "azure_thread":
            self.conversation_registry[conversation_id]["azure_thread_id"] = thread_id
        elif system_type == "edi_memory":
            self.conversation_registry[conversation_id]["edi_memory_active"] = True
        
        self.conversation_registry[conversation_id]["last_activity"] = datetime.now().isoformat()
    
    def get_conversation_info(self, conversation_id: str) -> Dict:
        """Get information about a conversation across both systems"""
        return self.conversation_registry.get(conversation_id, {})



# Legacy compatibility - keep the old conversation_memory for existing code
class ConversationMemory:
    """Legacy wrapper for backward compatibility"""
    
    def __init__(self, unified_memory):
        self.unified_memory = unified_memory
    
    def get_conversation_history(self, conversation_id: str) -> List[Dict]:
        return self.unified_memory.get_edi_conversation_history(conversation_id)
    
    def add_message(self, conversation_id: str, role: str, content: str, metadata: Dict = None):
        self.unified_memory.add_edi_message(conversation_id, role, content, metadata)
    
    def get_relevant_context(self, conversation_id: str, current_query: str, max_messages: int = 5) -> str:
        return self.unified_memory.get_edi_relevant_context(conversation_id, current_query, max_messages)

# Initialize conversation memory for backward compatibility
