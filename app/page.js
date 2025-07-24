import ChatInterface from "@/components/chat-interface";
import Header from "@/components/header";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col bg-background">
      <Header />
      <div className="flex-1 container mx-auto px-4 py-6 max-w-4xl">
        <ChatInterface />
      </div>
    </main>
  );
}