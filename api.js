// api.js

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "https://charlotte-backend-app.azurewebsites.net";

const apiUrl = {
  Production: `${API_BASE_URL}/api/chat`,
  Development: "http://localhost:8000/api/chat",
};

export async function sendChatQuery({ query, conversation_id, messages }) {
  try {
    const response = await fetch(apiUrl.Production, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        query,
        conversation_id,
        messages,
      }),
    });
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    console.error("API call failed:", error);
    throw error;
  }
} 