"use client";

import { cn } from "@/lib/utils";
import { Loader2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { parseCitations, formatCitations } from "@/lib/format-content";

export default function ChatMessage({ message }) {
  const isUser = message.role === "user";
  
  return (
    <div
      className={cn(
        "flex w-full",
        isUser ? "justify-end" : "justify-start"
      )}
    >
      <div className="flex items-start gap-3 max-w-[85%]">
        {!isUser && (
          <div className="w-8 h-8 bg-primary rounded-full flex items-center justify-center flex-shrink-0 mt-1">
            <span className="text-sm font-bold text-primary-foreground">C</span>
          </div>
        )}

        <div
          className={cn(
            "rounded-2xl px-4 py-3 flex-1",
            isUser
              ? "bg-primary text-primary-foreground ml-auto"
              : "bg-muted/50 text-foreground"
          )}
        >
        {message.isLoading ? (
          <div className="flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span>Thinking...</span>
          </div>
        ) : (
          <>
            {(() => {
              const { cleanText, citations } = parseCitations(message.content);
              return (
                <>
                  <div className="prose prose-sm max-w-none dark:prose-invert">
                    <ReactMarkdown>{cleanText}</ReactMarkdown>
                  </div>
                  {citations.length > 0 && (
                    <div className="mt-2 pt-2 border-t border-border/50 text-xs text-muted-foreground">
                      <div className="font-medium">Citations:</div>
                      <div>{formatCitations(citations)}</div>
                    </div>
                  )}
                </>
              );
            })()}
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

        {isUser && (
          <div className="w-8 h-8 bg-secondary rounded-full flex items-center justify-center flex-shrink-0 mt-1">
            <span className="text-sm font-bold text-secondary-foreground">U</span>
          </div>
        )}
      </div>
    </div>
  );
}