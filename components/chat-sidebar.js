"use client";

import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  MessageSquarePlus,
  MessageSquare,
  ChevronLeft,
  ChevronRight,
  MoreHorizontal,
  Trash2,
  Edit3,
  Loader2
} from "lucide-react";
import { azureCosmosClient } from "@/lib/azure-cosmos-client";

export default function ChatSidebar({
  currentConversationId,
  onNewChat,
  onSelectConversation,
  onDeleteConversation,
  onRenameConversation,
  isCollapsed = false,
  onToggleCollapse,
  isMobile = false,
  user,
  getAuthHeaders
}) {
  const [hoveredConversation, setHoveredConversation] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [editingTitle, setEditingTitle] = useState("");
  const [conversations, setConversations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (user?.email) {
      loadUserSessions();
    }
  }, [user?.email]);

  // Set up auth headers for the Azure Cosmos client when component mounts
  useEffect(() => {
    if (getAuthHeaders) {
      azureCosmosClient.setAuthHeaders(getAuthHeaders);
    }
  }, [getAuthHeaders]);

  const loadUserSessions = async () => {
    if (!user?.email) return;

    setLoading(true);
    setError(null);

    try {
      const sessions = await azureCosmosClient.getSessionsForUserId(user.email);
      setConversations(sessions);
    } catch (err) {
      console.error("Error loading sessions:", err);
      setError("Failed to load chat sessions");
    } finally {
      setLoading(false);
    }
  };

  const handleNewChat = async () => {
    if (!user?.email) return;

    try {
      const sessionId = `chat_${Date.now()}`;
      const userId = user.email;
      const title = "New Chat";

      const newSession = await azureCosmosClient.createNewSession(sessionId, userId, title);

      // Add to local state
      setConversations(prev => [newSession, ...prev]);

      // Clear any errors on successful operation
      setError(null);

      // Call parent callback if provided
      if (onNewChat) {
        onNewChat(newSession);
      }

      // Select the new session
      if (onSelectConversation) {
        onSelectConversation(sessionId);
      }
    } catch (err) {
      console.error("Error creating new chat:", err);
      setError("Failed to create new chat");
    }
  };

  const handleDeleteConversation = async (conversationId) => {
    try {
      await azureCosmosClient.deleteSession(conversationId);

      // Remove from local state
      setConversations(prev => prev.filter(conv => conv.id !== conversationId));

      // Clear any errors on successful operation
      setError(null);

      // Call parent callback if provided
      if (onDeleteConversation) {
        onDeleteConversation(conversationId);
      }
    } catch (err) {
      console.error("Error deleting conversation:", err);
      setError("Failed to delete conversation");
    }
  };

  const handleRenameConversation = async (conversationId, newTitle) => {
    try {
      await azureCosmosClient.renameSession(conversationId, newTitle);

      // Update local state
      setConversations(prev =>
        prev.map(conv =>
          conv.id === conversationId
            ? { ...conv, title: newTitle, updatedAt: new Date().toISOString() }
            : conv
        )
      );

      // Clear any errors on successful operation
      setError(null);

      // Call parent callback if provided
      if (onRenameConversation) {
        onRenameConversation(conversationId, newTitle);
      }
    } catch (err) {
      console.error("Error renaming conversation:", err);
      setError("Failed to rename conversation");
    }
  };

  const handleRename = (conversation) => {
    setEditingId(conversation.id);
    setEditingTitle(conversation.title);
  };

  const handleSaveRename = (conversationId) => {
    if (editingTitle.trim()) {
      handleRenameConversation(conversationId, editingTitle.trim());
    }
    setEditingId(null);
    setEditingTitle("");
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setEditingTitle("");
  };

  return (
    <>
      {/* Mobile overlay */}
      {isMobile && !isCollapsed && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={onToggleCollapse}
        />
      )}

      <div
        className={cn(
          "flex flex-col h-full bg-gray-900 text-white transition-all duration-300 ease-in-out relative",
          isMobile
            ? cn(
                "fixed left-0 top-0 z-50 lg:relative lg:z-auto",
                isCollapsed ? "-translate-x-full lg:translate-x-0 lg:w-0 lg:overflow-hidden" : "translate-x-0 w-64"
              )
            : isCollapsed ? "w-0 overflow-hidden" : "w-64"
        )}
      >
      {/* Close Button - Only visible when sidebar is open */}
      {!isCollapsed && (
        <Button
          variant="ghost"
          size="sm"
          onClick={onToggleCollapse}
          className={cn(
            "absolute z-50 h-6 w-6 rounded-full bg-gray-700 hover:bg-gray-600 p-1 border border-gray-600",
            "flex items-center justify-center",
            isMobile
              ? "right-3 top-4"
              : "-right-3 top-4"
          )}
        >
          <ChevronLeft className="h-3 w-3" />
        </Button>
      )}

      {/* Sidebar Content */}
      <div className={cn("flex flex-col h-full", isCollapsed && "hidden")}>
        {/* New Chat Button */}
        <div className="p-3 border-b border-gray-700">
          <Button
            onClick={handleNewChat}
            disabled={loading}
            className="w-full justify-start gap-3 bg-gray-800 hover:bg-gray-700 text-white border border-gray-600"
            variant="outline"
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <MessageSquarePlus className="h-4 w-4" />
            )}
            <span>New chat</span>
          </Button>
        </div>

        {/* Error Message */}
        {error && (
          <div className="p-3 text-red-400 text-sm text-center border-b border-gray-700">
            {error}
          </div>
        )}

        {/* Conversations List */}
        <div className="flex-1 overflow-y-auto">
          <div className="p-2 space-y-1">
            {loading ? (
              <div className="flex items-center justify-center p-3">
                <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
                <span className="ml-2 text-gray-400 text-sm">Loading chats...</span>
              </div>
            ) : conversations.length === 0 ? (
              <div className="text-gray-400 text-sm p-3 text-center">
                No conversations yet
              </div>
            ) : (
              conversations.map((conversation) => {
                return (
                <div
                  key={conversation.id}
                  id={conversation.id}
                  className={cn(
                    "group relative rounded-lg transition-colors cursor-pointer",
                    currentConversationId === conversation.id
                      ? "bg-gray-700"
                      : "hover:bg-gray-800"
                  )}
                  onMouseEnter={() => setHoveredConversation(conversation.id)}
                  onMouseLeave={() => setHoveredConversation(null)}
                  onClick={() => onSelectConversation && onSelectConversation(conversation.id)}
                >
                  <div className="flex items-center gap-3 p-3 pr-8">
                    <MessageSquare className="h-4 w-4 text-gray-400 flex-shrink-0" />

                    {editingId === conversation.id ? (
                      <input
                        type="text"
                        value={editingTitle}
                        onChange={(e) => setEditingTitle(e.target.value)}
                        onBlur={() => handleSaveRename(conversation.id)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            handleSaveRename(conversation.id);
                          } else if (e.key === "Escape") {
                            handleCancelEdit();
                          }
                        }}
                        className="flex-1 bg-transparent border-none outline-none text-sm text-white placeholder-gray-400"
                        autoFocus
                        onClick={(e) => e.stopPropagation()}
                      />
                    ) : (
                      <span className="flex-1 truncate text-sm">
                        {conversation.title}
                      </span>
                    )}
                  </div>

                  {/* Action buttons */}
                  {hoveredConversation === conversation.id && editingId !== conversation.id && (
                    <div className="absolute right-2 top-1/2 -translate-y-1/2 flex gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleRename(conversation);
                        }}
                        className="h-6 w-6 p-0 text-gray-400 hover:text-white hover:bg-gray-600"
                      >
                        <Edit3 className="h-3 w-3" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteConversation(conversation.id);
                        }}
                        className="h-6 w-6 p-0 text-gray-400 hover:text-red-400 hover:bg-gray-600"
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </div>
                  )}
                </div>
              )
            })
            )}
          </div>
        </div>

        {/* Footer (optional) */}
        <div className="p-3 border-t border-gray-700">
          <div className="text-xs text-gray-400 text-center">
            Charlotte AI Assistant
          </div>
        </div>
      </div>
    </div>
    </>
  );
}