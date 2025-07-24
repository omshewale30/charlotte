"use client";

import { cn } from "@/lib/utils";
import { Loader2 } from "lucide-react";

export default function ChatMessage({ message }) {
  const isUser = message.role === "user";
  
  return (
    <div
      className={cn(
        "flex w-full",
        isUser ? "justify-end" : "justify-start"
      )}
    >
      <div
        className={cn(
          "rounded-lg px-4 py-2 max-w-[80%]",
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-card border border-border"
        )}
      >
        {message.isLoading ? (
          <div className="flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span>Thinking...</span>
          </div>
        ) : (
          <>
            <div className="whitespace-pre-wrap">{message.content}</div>
            {message.sources && message.sources.length > 0 && (
              <div className="mt-2 pt-2 border-t border-border/50 text-sm text-muted-foreground">
                <div className="font-medium">Sources:</div>
                <ul className="list-disc list-inside">
                  {message.sources.map((source, index) => (
                    <li key={index} className="truncate">
                      {source.document_name}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}