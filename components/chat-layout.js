"use client";

import { useState, useRef, useEffect } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { SendIcon, Loader2, Menu } from "lucide-react";
import ChatMessage from "@/components/chat-message";
import ChatSidebar from "@/components/chat-sidebar";
import Header from "@/components/logout";
import { APIClient } from "@/lib/api-client";
import { useAuth } from "@/components/auth-context-msal";
import { azureCosmosClient } from "@/lib/azure-cosmos-client";
import Toggle from "@/components/ui/toggle";

const DEFAULT_MODE = "EDI";


export default function ChatLayout() {
  const { getAuthHeaders, user } = useAuth();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [conversationId, setConversationId] = useState(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [chatStarted, setChatStarted] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const [mode, setMode] = useState(DEFAULT_MODE);
  const [modeLocked, setModeLocked] = useState(false);
  const [conversationModes, setConversationModes] = useState({});

  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  // Create API client instance
  const apiClient = new APIClient(getAuthHeaders);

  const determineModeFromMessages = (chatMessages = []) => {
    if (!Array.isArray(chatMessages) || chatMessages.length === 0) {
      return DEFAULT_MODE;
    }

    for (let idx = chatMessages.length - 1; idx >= 0; idx--) {
      const message = chatMessages[idx];
      if (message?.role !== "assistant") continue;

      if (message?.queryType === "edi_search" || (Array.isArray(message?.transactions) && message.transactions.length > 0)) {
        return "EDI";
      }

      if (message?.queryType === "general_ai") {
        return "PROCEDURE";
      }
    }

    return DEFAULT_MODE;
  };

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
    const newConversationId = newSession?.id || null;
    setMessages([]);
    setConversationId(newConversationId);
    setChatStarted(false);
    setInput("");
    if (newConversationId && conversationModes[newConversationId]) {
      setMode(conversationModes[newConversationId]);
      setModeLocked(Boolean(newSession?.messages?.length));
    } else {
      setMode(DEFAULT_MODE);
      setModeLocked(false);
    }

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
        const sessionMessages = session.messages || [];
        setConversationId(id);
        setMessages(sessionMessages);
        const hasMessages = sessionMessages.length > 0;
        setChatStarted(hasMessages);
        const derivedMode = conversationModes[id] || determineModeFromMessages(sessionMessages);
        setConversationModes((prev) => ({
          ...prev,
          [id]: derivedMode,
        }));
        setMode(derivedMode);
        setModeLocked(hasMessages);

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
    setConversationModes((prev) => {
      if (!(id in prev)) return prev;
      const { [id]: _removed, ...rest } = prev;
      return rest;
    });
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

    const isFirstMessage = !chatStarted;
    const userMessage = input.trim();
    setInput("");

    // Mark chat as started on first message
    if (isFirstMessage) {
      setChatStarted(true);
      setModeLocked(true);
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
        mode: mode,
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
        if (currentConversationId) {
          setConversationModes((prev) => ({
            ...prev,
            [currentConversationId]: mode,
          }));
        }
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
    <>
      <style dangerouslySetInnerHTML={{__html: `
        .chat-messages-scroll::-webkit-scrollbar {
          width: 8px;
        }
        .chat-messages-scroll::-webkit-scrollbar-track {
          background: transparent;
        }
        .chat-messages-scroll::-webkit-scrollbar-thumb {
          background-color: rgba(75, 156, 211, 0.3);
          border-radius: 4px;
        }
        .chat-messages-scroll::-webkit-scrollbar-thumb:hover {
          background-color: rgba(75, 156, 211, 0.5);
        }
        .chat-messages-scroll {
          scrollbar-width: thin;
          scrollbar-color: rgba(75, 156, 211, 0.3) transparent;
        }
      `}} />
      <div className="flex flex-col h-screen bg-gradient-to-br from-background via-[rgba(75,156,211,0.02)] to-background relative overflow-hidden">
        {/* Background decorative elements */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute top-0 right-0 w-[600px] h-[600px] bg-[#4B9CD3]/3 rounded-full blur-3xl"></div>
          <div className="absolute bottom-0 left-0 w-[600px] h-[600px] bg-[#2B6FA6]/3 rounded-full blur-3xl"></div>
        </div>



      <div className="flex flex-1 relative z-10 min-h-0">
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
          "flex-1 flex flex-col transition-all duration-300 relative h-full w-full min-h-0",
          !sidebarCollapsed && !isMobile ? "ml-64" : "ml-0"
        )}
      >
        {/* Sidebar Toggle Button - Always Visible */}
        {sidebarCollapsed && (
          <div className="fixed top-20 left-4 z-30 fade-in-up">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setSidebarCollapsed(false)}
              className="h-12 w-12 p-0 bg-background/90 backdrop-blur-md border-2 border-primary/20 shadow-xl hover:border-primary/40 hover:bg-background transition-all duration-300 hover:scale-110"
            >
              <Menu className="h-5 w-5 text-[#4B9CD3]" />
            </Button>
          </div>
        )}

        {!chatStarted ? (
          // Initial centered view
          <div className="flex-1 flex flex-col items-center justify-center px-4 py-12">
            <div className="max-w-3xl w-full space-y-8 fade-in-up">
              {/* Welcome Header */}
              <div className="text-center space-y-6">
                <div className="w-20 h-20 rounded-3xl bg-gradient-to-br from-[#4B9CD3] to-[#2B6FA6] flex items-center justify-center mx-auto shadow-2xl fade-in-up-delay-1">
                  <span className="text-3xl font-bold text-white">C</span>
                </div>
                <div className="space-y-3 fade-in-up-delay-2">
                  <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold text-foreground tracking-tight">
                    How can I help you{' '}
                    <span className="bg-gradient-to-r from-[#4B9CD3] to-[#2B6FA6] bg-clip-text text-transparent">today</span>?
                  </h1>
                  <p className="text-muted-foreground text-lg md:text-xl max-w-2xl mx-auto">
                    I'm <span className="font-semibold text-[#4B9CD3]">Charlotte</span>, your UNC resources assistant. Ask me anything!
                  </p>
                </div>
              </div>

              {/* Example prompts */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 fade-in-up-delay-3">
                {[
                  "How do I create a claim in ecW?",
                  "Find the trace number for this transaction?",
                  "What is the charge code for Campus Health Pharmacy?",
                  "What should be the accounting date on CashPro deposits?"
                ].map((prompt, index) => (
                  <Button
                    key={index}
                    variant="outline"
                    className="h-auto p-5 text-left justify-start whitespace-normal border-2 border-primary/10 bg-card/60 backdrop-blur-sm hover:border-primary/30 hover:bg-card/80 hover:shadow-lg transition-all duration-300 group"
                    onClick={() => setInput(prompt)}
                  >
                    <span className="text-foreground group-hover:text-[#4B9CD3] transition-colors duration-300">{prompt}</span>
                  </Button>
                ))}
              </div>
            </div>

            {/* Input area - centered */}
            <div className="w-full max-w-3xl mt-12 fade-in-up-delay-4">
              <form onSubmit={handleSubmit} className="space-y-4">
                {/* Toggle switch */}
                {!modeLocked && (
                  <div className="flex justify-center">
                    <Toggle mode={mode} setMode={setMode} disabled={modeLocked} />
                  </div>
                )}
                
                <div className="relative group">
                  <textarea
                    ref={textareaRef}
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Message Charlotte..."
                    className="w-full min-h-[60px] max-h-[200px] px-5 py-4 pr-14 border-2 border-primary/10 rounded-2xl resize-none focus:outline-none focus:ring-2 focus:ring-[#4B9CD3]/20 focus:border-[#4B9CD3]/40 bg-card/60 backdrop-blur-sm text-foreground placeholder-muted-foreground transition-all duration-300 hover:border-primary/20"
                    disabled={isSubmitting}
                    rows={1}
                  />
                  <Button 
                    type="submit"
                    size="sm"
                    disabled={isSubmitting || !input.trim()}
                    className="absolute right-3 top-1/2 -translate-y-1/2 h-10 w-10 p-0 rounded-xl bg-gradient-to-br from-[#4B9CD3] to-[#2B6FA6] hover:from-[#2B6FA6] hover:to-[#0F3D63] text-white shadow-lg hover:shadow-xl transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed hover:scale-110"
                  >
                    {isSubmitting ? (
                      <Loader2 className="h-5 w-5 animate-spin" />
                    ) : (
                      <SendIcon className="h-5 w-5" />
                    )}
                  </Button>
                </div>
              </form>
            </div>
          </div>
        ) : (
          // Full chat view
          <div className="flex flex-col h-full min-h-0">
            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto min-h-0 chat-messages-scroll">
              <div className="max-w-3xl mx-auto px-4 md:px-6 py-8 space-y-6">
                {messages.map((message, index) => (
                  <div key={index} className="fade-in-up">
                    <ChatMessage message={message} />
                  </div>
                ))}
                <div ref={messagesEndRef} />
              </div>
            </div>

            {/* Input area - fixed at bottom */}
            <div className="flex-shrink-0 border-t-2 border-primary/10 bg-background/95 backdrop-blur-md shadow-2xl">
              <div className="max-w-3xl mx-auto px-4 md:px-6 py-5">
                <form onSubmit={handleSubmit} className="space-y-4">
                  {/* Toggle switch */}
                  {!modeLocked ? (
                    <div className="flex justify-center">
                      <Toggle mode={mode} setMode={setMode} disabled={modeLocked} />
                    </div>
                  ) : (
                    <div className="flex justify-center">
                      <div className="px-4 py-2 rounded-full bg-[#4B9CD3]/10 border border-[#4B9CD3]/20">
                        <span className="text-xs font-semibold text-[#4B9CD3]">
                          Mode locked to {mode === "EDI" ? "EDI" : "Procedure"}
                        </span>
                      </div>
                    </div>
                  )}
                  
                  <div className="relative group">
                    <textarea
                      ref={textareaRef}
                      value={input}
                      onChange={(e) => setInput(e.target.value)}
                      onKeyDown={handleKeyDown}
                      placeholder="Message Charlotte..."
                      className="w-full min-h-[60px] max-h-[200px] px-5 py-4 pr-14 border-2 border-primary/10 rounded-2xl resize-none focus:outline-none focus:ring-2 focus:ring-[#4B9CD3]/20 focus:border-[#4B9CD3]/40 bg-card/60 backdrop-blur-sm text-foreground placeholder-muted-foreground transition-all duration-300 hover:border-primary/20"
                      disabled={isSubmitting}
                      rows={1}
                    />
                    <Button
                      type="submit"
                      size="sm"
                      disabled={isSubmitting || !input.trim()}
                      className="absolute right-3 top-1/2 -translate-y-1/2 h-10 w-10 p-0 rounded-xl bg-gradient-to-br from-[#4B9CD3] to-[#2B6FA6] hover:from-[#2B6FA6] hover:to-[#0F3D63] text-white shadow-lg hover:shadow-xl transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed hover:scale-110"
                    >
                      {isSubmitting ? (
                        <Loader2 className="h-5 w-5 animate-spin" />
                      ) : (
                        <SendIcon className="h-5 w-5" />
                      )}
                    </Button>
                  </div>
                </form>
              </div>
            </div>
          </div>
        )}
        </div>
      </div>
    </div>
    </>
  );
}