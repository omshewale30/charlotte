// api.js

const apiUrl = {
  "Production": "https://charlotte-backend-dtexg4awara4adfb.eastus-01.azurewebsites.net/api/query",
  "Development": "http://localhost:8000/api/query",
}

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