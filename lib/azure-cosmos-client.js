//This is the frontend session client that calls the backend API

export class AzureCosmosClient {
    constructor() {
        this.apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
    }

    async _makeAuthenticatedRequest(url, options = {}) {
        // This will be called from components that have access to auth headers
        const response = await fetch(url, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers,
            },
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`API request failed: ${response.status} ${response.statusText} - ${errorText}`);
        }

        return response.json();
    }

    async createNewSession(sessionId, userId, title = "New Chat") {
        try {
            const response = await this._makeAuthenticatedRequest(`${this.apiBaseUrl}/api/session`, {
                method: 'POST',
                body: JSON.stringify({
                    session_id: sessionId,
                    user_id: userId,
                    title: title
                })
            });
            return response.session;
        } catch (error) {
            console.error("Error creating new session:", error);
            throw error;
        }
    }

    async getSession(sessionId) {
        try {
            const response = await this._makeAuthenticatedRequest(`${this.apiBaseUrl}/api/session/${sessionId}`);
            return response.session;
        } catch (error) {
            console.error("Error getting session:", error);
            throw error;
        }
    }

    async updateSession(sessionId, userId, messages, title = null) {
        try {
            const updateData = {
                user_id: userId,
                messages: messages
            };

            if (title) {
                updateData.title = title;
            }

            const response = await this._makeAuthenticatedRequest(`${this.apiBaseUrl}/api/session/${sessionId}`, {
                method: 'PUT',
                body: JSON.stringify(updateData)
            });
            return response.session;
        } catch (error) {
            console.error("Error updating session:", error);
            throw error;
        }
    }

    async getSessionsForUserId(userId) {
        try {
            const response = await this._makeAuthenticatedRequest(`${this.apiBaseUrl}/api/sessions/${userId}`);
            return response.sessions;
        } catch (error) {
            console.error("Error getting sessions for user:", error);
            throw error;
        }
    }

    async deleteSession(sessionId) {
        try {
            await this._makeAuthenticatedRequest(`${this.apiBaseUrl}/api/session/${sessionId}`, {
                method: 'DELETE'
            });
            return true;
        } catch (error) {
            console.error("Error deleting session:", error);
            throw error;
        }
    }

    async renameSession(sessionId, newTitle) {
        try {
            // First get the current session to preserve other data
            const currentSession = await this.getSession(sessionId);

            const response = await this._makeAuthenticatedRequest(`${this.apiBaseUrl}/api/session/${sessionId}`, {
                method: 'PUT',
                body: JSON.stringify({
                    user_id: currentSession.user_id,
                    messages: currentSession.messages,
                    title: newTitle
                })
            });
            return response.session;
        } catch (error) {
            console.error("Error renaming session:", error);
            throw error;
        }
    }

    async getSessionMessages(sessionId) {
        try {
            const session = await this.getSession(sessionId);
            return session?.messages || [];
        } catch (error) {
            console.error("Error getting session messages:", error);
            throw error;
        }
    }

    async addMessageToSession(sessionId, message) {
        try {
            const session = await this.getSession(sessionId);
            if (!session) {
                throw new Error("Session not found");
            }

            const updatedMessages = [...(session.messages || []), message];
            const updatedSession = await this.updateSession(
                sessionId,
                session.user_id,
                updatedMessages
            );

            return updatedSession;
        } catch (error) {
            console.error("Error adding message to session:", error);
            throw error;
        }
    }

    // Method to inject auth headers from components that have access to them
    setAuthHeaders(getAuthHeaders) {
        this._getAuthHeaders = getAuthHeaders;

        // Override the request method to include auth headers
        this._makeAuthenticatedRequest = async (url, options = {}) => {
            const authHeaders = await getAuthHeaders();

            const response = await fetch(url, {
                ...options,
                headers: {
                    'Content-Type': 'application/json',
                    ...authHeaders,
                    ...options.headers,
                },
            });

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`API request failed: ${response.status} ${response.statusText} - ${errorText}`);
            }

            return response.json();
        };
    }
}

// Create a singleton instance
export const azureCosmosClient = new AzureCosmosClient();