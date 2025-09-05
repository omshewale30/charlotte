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
            {message.queryType === "edi_search" && message.transactions && message.transactions.length > 0 && (
              <div className="mt-2 pt-2 border-t border-border/50 text-sm">
                <div className="font-medium text-muted-foreground mb-2">
                  Found {message.transactionsFound} transaction{message.transactionsFound !== 1 ? 's' : ''}:
                </div>
                <div className="space-y-2">
                  {message.transactions.slice(0, 3).map((transaction, index) => (
                    <div key={index} className="bg-muted/50 rounded p-2 text-xs">
                      <div><strong>Trace:</strong> {transaction.trace_number}</div>
                      <div><strong>Amount:</strong> ${transaction.amount}</div>
                      <div><strong>Date:</strong> {transaction.effective_date}</div>
                      <div><strong>From:</strong> {transaction.originator} <strong>To:</strong> {transaction.receiver}</div>
                    </div>
                  ))}
                  {message.transactions.length > 3 && (
                    <div className="text-xs text-muted-foreground">
                      ...and {message.transactions.length - 3} more transactions
                    </div>
                  )}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}