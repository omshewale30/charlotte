"use client";

import { useState, useRef, useEffect } from "react";
import { SendIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import ChatMessage from "@/components/chat-message";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { sendChatQuery } from "../api";

export default function ChatInterface() {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content: "Hello! I'm Charlotte. I can answer questions about transactions or processes. How can I help you today?",
    },
  ]);
  const [input, setInput] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [conversationId, setConversationId] = useState(null);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!input.trim() || isSubmitting) return;
    
    const userMessage = input.trim();
    setInput("");
    
    // Add user message to chat
    setMessages((prev) => [
      ...prev,
      { role: "user", content: userMessage },
      { role: "assistant", content: "", isLoading: true },
    ]);
    
    setIsSubmitting(true);
    
    try {
      const data = await sendChatQuery({
        query: userMessage,
        conversation_id: conversationId,
        messages: messages.map(msg => ({
          role: msg.role,
          content: msg.content
        }))
      });
      
      // Set conversation ID if this is the first message
      if (!conversationId && data.conversation_id) {
        setConversationId(data.conversation_id);
      }
      
      // Update assistant message with response
      setMessages((prev) => 
        prev.map((msg, i) => {
          if (i === prev.length - 1 && msg.isLoading) {
            return {
              role: "assistant",
              content: data.response || data.answer, // Handle both response formats
              sources: data.sources,
              transactions: data.data, // EDI transaction data
              queryType: data.type, // "edi_search" or "general_ai"
              transactionsFound: data.transactions_found,
              isLoading: false,
            };
          }
          return msg;
        })
      );
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

  return (
    <Card className="w-full">

      <CardContent>
        <div className="space-y-4 h-[500px] overflow-y-auto p-4 rounded-md bg-muted/30">
          {messages.map((message, index) => (
            <ChatMessage key={index} message={message} />
          ))}
          <div ref={messagesEndRef} />
        </div>
      </CardContent>
      <CardFooter>
        <form onSubmit={handleSubmit} className="w-full flex gap-2">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question..."
            className="flex-1"
            disabled={isSubmitting}
          />
          <Button type="submit" disabled={isSubmitting || !input.trim()}>
            <SendIcon className="h-4 w-4" />
            <span className="sr-only">Send</span>
          </Button>
        </form>
      </CardFooter>
    </Card>
  );
}