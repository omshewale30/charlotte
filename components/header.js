import { Database } from "lucide-react";

export default function Header() {
  return (
    <header className="border-b border-border bg-card">
      <div className="container mx-auto px-4 py-4 flex items-center justify-between max-w-4xl">
        <div className="flex items-center gap-2">
          <Database className="h-6 w-6 text-[#4B9CD3]" />
          <h1 className="text-xl font-semibold">UNC Chatbot Demo</h1>
        </div>
        <div className="text-sm text-muted-foreground">Cashier Office Documents</div>
      </div>
    </header>
  );
}