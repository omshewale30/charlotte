// api.js

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "https://charlotte-backend-app.azurewebsites.net";

const apiUrl = {
  Production: `${API_BASE_URL}/api/chat`,
  Development: "http://localhost:8000/api/chat",
};

function getAuthHeaders() {
  const sessionId = typeof window !== 'undefined' ? localStorage.getItem('session_id') : null;
  return sessionId ? { 'Authorization': `Bearer ${sessionId}` } : {};
}

export async function sendChatQuery({ query, conversation_id, messages }) {
  try {
    const response = await fetch(apiUrl.Development, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...getAuthHeaders(),
      },
      body: JSON.stringify({
        query,
        conversation_id,
        messages,
      }),
    });
    
    if (response.status === 401) {
      // Redirect to login if unauthorized
      if (typeof window !== 'undefined') {
        localStorage.removeItem('session_id');
        window.location.href = '/';
      }
      throw new Error('Authentication required');
    }
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `API error: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error("API call failed:", error);
    throw error;
  }
} 