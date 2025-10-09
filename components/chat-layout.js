"use client";

import { useState, useRef, useEffect } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { SendIcon, Loader2, Menu } from "lucide-react";
import ChatMessage from "@/components/chat-message";
import ChatSidebar from "@/components/chat-sidebar";
import Header from "@/components/header";
import { APIClient } from "@/lib/api-client";
import { useAuth } from "@/components/auth-context-msal";
import { azureCosmosClient } from "@/lib/azure-cosmos-client";

export default function ChatLayout() {
  const { getAuthHeaders, user } = useAuth();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [conversationId, setConversationId] = useState(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [chatStarted, setChatStarted] = useState(false);
  const [isMobile, setIsMobile] = useState(false);

  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  // Create API client instance
  const apiClient = new APIClient(getAuthHeaders);

  // Set up auth headers for Azure Cosmos client
  useEffect(() => {
    if (getAuthHeaders) {
      azureCosmosClient.setAuthHeaders(getAuthHeaders);
    }
  }, [getAuthHeaders]);

  // Check for mobile on mount and resize
  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 1024);
      // Auto-collapse sidebar on mobile
      if (window.innerWidth < 1024) {
        setSidebarCollapsed(true);
      }
    };

    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 200) + 'px';
    }
  }, [input]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const generateConversationTitle = (message) => {
    // Generate a title from the first message (limit to 50 characters)
    return message.length > 50 ? message.substring(0, 50) + "..." : message;
  };

  const handleNewChat = (newSession = null) => {
    setMessages([]);
    setConversationId(newSession?.id || null);
    setChatStarted(false);
    setInput("");

    // Auto-collapse sidebar on mobile after creating new chat
    if (isMobile) {
      setSidebarCollapsed(true);
    }
  };

  const handleSelectConversation = async (id) => {
    try {
      // Load conversation from Azure Cosmos DB
      const session = await azureCosmosClient.getSession(id);
      if (session) {
        setConversationId(id);
        setMessages(session.messages || []);
        setChatStarted(session.messages && session.messages.length > 0);

        // Auto-collapse sidebar on mobile after selection
        if (isMobile) {
          setSidebarCollapsed(true);
        }
      }
    } catch (error) {
      console.error("Error loading conversation:", error);
      // Fallback to new chat if loading fails
      handleNewChat();
      setConversationId(id);
    }
  };

  const handleDeleteConversation = (id) => {
    if (conversationId === id) {
      handleNewChat();
    }
  };

  const handleRenameConversation = (id, newTitle) => {
    // Sidebar handles the rename, we just need to update title if it's current conversation
    // This callback is mainly for keeping the UI consistent
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!input.trim() || isSubmitting) return;

    const userMessage = input.trim();
    setInput("");

    // Mark chat as started on first message
    if (!chatStarted) {
      setChatStarted(true);
    }

    // Add user message to chat
    setMessages((prev) => [
      ...prev,
      { role: "user", content: userMessage },
      { role: "assistant", content: "", isLoading: true },
    ]);

    setIsSubmitting(true);

    try {
      const data = await apiClient.sendChatQuery({
        query: userMessage,
        conversation_id: conversationId,
        messages: messages.map(msg => ({
          role: msg.role,
          content: msg.content
        }))
      });

      // Set conversation ID if this is the first message
      if (!conversationId && data.conversation_id) {
        const newConversationId = data.conversation_id;
        setConversationId(newConversationId);
      }

      // Update assistant message with response
      const updatedMessages = messages.concat([
        { role: "user", content: userMessage },
        {
          role: "assistant",
          content: data.response || data.answer,
          sources: data.sources,
          transactions: data.data,
          queryType: data.type,
          transactionsFound: data.transactions_found,
        }
      ]);

      setMessages((prev) =>
        prev.map((msg, i) => {
          if (i === prev.length - 1 && msg.isLoading) {
            return {
              role: "assistant",
              content: data.response || data.answer,
              sources: data.sources,
              transactions: data.data,
              queryType: data.type,
              transactionsFound: data.transactions_found,
              isLoading: false,
            };
          }
          return msg;
        })
      );

      // Persist messages to Azure Cosmos DB
      try {
        const currentConversationId = conversationId || data.conversation_id;
        if (currentConversationId && user?.email) {
          if (!conversationId) {
            // Create new session for first message
            await azureCosmosClient.createNewSession(
              currentConversationId,
              user.email,
              generateConversationTitle(userMessage)
            );
          }

          await azureCosmosClient.updateSession(
            currentConversationId,
            user.email,
            updatedMessages
          );
        }
      } catch (dbError) {
        console.error("Error persisting messages to database:", dbError);
        // Don't block the UI if database save fails
      }
    } catch (error) {
      console.error("Error querying API:", error);

      // Update loading message with error
      setMessages((prev) =>
        prev.map((msg, i) => {
          if (i === prev.length - 1 && msg.isLoading) {
            return {
              role: "assistant",
              content: "I'm sorry, I encountered an error while processing your request. Please try again later.",
              isLoading: false,
            };
          }
          return msg;
        })
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-background">
      {/* Header */}
      <Header />

      <div className="flex flex-1">
        {/* Sidebar */}
        <ChatSidebar
          currentConversationId={conversationId}
          onNewChat={handleNewChat}
          onSelectConversation={handleSelectConversation}
          onDeleteConversation={handleDeleteConversation}
          onRenameConversation={handleRenameConversation}
          isCollapsed={sidebarCollapsed}
          onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
          isMobile={isMobile}
          user={user}
          getAuthHeaders={getAuthHeaders}
        />

      {/* Main Chat Area */}
      <div
        className={cn(
          "flex-1 flex flex-col transition-all duration-300",
          sidebarCollapsed ? "ml-0" : "ml-0"
        )}
      >
        {/* Sidebar Toggle Button - Always Visible */}
        {sidebarCollapsed && (
          <div className="fixed top-4 left-4 z-30">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setSidebarCollapsed(false)}
              className="h-10 w-10 p-0 bg-background/80 backdrop-blur-sm border-border shadow-lg"
            >
              <Menu className="h-4 w-4" />
            </Button>
          </div>
        )}

        {!chatStarted ? (
          // Initial centered view
          <div className="flex-1 flex flex-col items-center justify-center px-4">
            <div className="max-w-2xl w-full space-y-6">
              {/* Welcome Header */}
              <div className="text-center space-y-4">
                <div className="w-16 h-16 bg-primary rounded-full flex items-center justify-center mx-auto">
                  <span className="text-2xl font-bold text-primary-foreground">C</span>
                </div>
                <h1 className="text-4xl font-bold text-foreground">
                  How can I help you today?
                </h1>
                <p className="text-muted-foreground text-lg">
                  I'm Charlotte, your UNC resources assistant. Ask me anything!
                </p>
              </div>

              {/* Example prompts */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {[
                  "How do I create a claim in ecW?",
                  "Find the trace number for this transaction?",
                  "What is the charge code for Campus Health Pharmacy?",
                  "What should be the accounting date on CashPro deposits?"
                ].map((prompt, index) => (
                  <Button
                    key={index}
                    variant="outline"
                    className="h-auto p-4 text-left justify-start whitespace-normal"
                    onClick={() => setInput(prompt)}
                  >
                    {prompt}
                  </Button>
                ))}
              </div>
            </div>

            {/* Input area - centered */}
            <div className="w-full max-w-3xl mt-8">
              <form onSubmit={handleSubmit} className="relative">
                <div className="relative">
                  <textarea
                    ref={textareaRef}
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Message Charlotte..."
                    className="w-full min-h-[52px] max-h-[200px] px-4 py-3 pr-12 border border-input rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent bg-background text-foreground placeholder-muted-foreground"
                    disabled={isSubmitting}
                    rows={1}
                  />
                  <Button
                    type="submit"
                    size="sm"
                    disabled={isSubmitting || !input.trim()}
                    className="absolute right-2 top-1/2 -translate-y-1/2 h-8 w-8 p-0 rounded-lg"
                  >
                    {isSubmitting ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <SendIcon className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              </form>
            </div>
          </div>
        ) : (
          // Full chat view
          <>

            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto">
              <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
                {messages.map((message, index) => (
                  <ChatMessage key={index} message={message} />
                ))}
                <div ref={messagesEndRef} />
              </div>
            </div>

            {/* Input area - fixed at bottom */}
            <div className="border-t border-border bg-background/95 backdrop-blur-sm">
              <div className="max-w-3xl mx-auto px-4 py-4">
                <form onSubmit={handleSubmit} className="relative">
                  <div className="relative">
                    <textarea
                      ref={textareaRef}
                      value={input}
                      onChange={(e) => setInput(e.target.value)}
                      onKeyDown={handleKeyDown}
                      placeholder="Message Charlotte..."
                      className="w-full min-h-[52px] max-h-[200px] px-4 py-3 pr-12 border border-input rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent bg-background text-foreground placeholder-muted-foreground"
                      disabled={isSubmitting}
                      rows={1}
                    />
                    <Button
                      type="submit"
                      size="sm"
                      disabled={isSubmitting || !input.trim()}
                      className="absolute right-2 top-1/2 -translate-y-1/2 h-8 w-8 p-0 rounded-lg"
                    >
                      {isSubmitting ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <SendIcon className="h-4 w-4" />
                      )}
                    </Button>
                  </div>
                </form>
              </div>
            </div>
          </>
        )}
        </div>
      </div>
    </div>
  );
}