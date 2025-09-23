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

export async function uploadEDIReport(file, onProgress) {
  try {
    const formData = new FormData();
    formData.append('file', file);

    const sessionId = typeof window !== 'undefined' ? localStorage.getItem('session_id') : null;
    if (!sessionId) {
      throw new Error('Authentication required');
    }

    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();

      // Track upload progress
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable && onProgress) {
          const percentComplete = (event.loaded / event.total) * 100;
          onProgress(Math.round(percentComplete));
        }
      };

      // Handle completion
      xhr.onload = () => {
        if (xhr.status === 200) {
          try {
            const response = JSON.parse(xhr.responseText);
            resolve(response);
          } catch (e) {
            reject(new Error('Invalid response format'));
          }
        } else if (xhr.status === 409) {
          // Handle duplicate file conflict
          try {
            const errorResponse = JSON.parse(xhr.responseText);
            reject(new Error(`Duplicate: ${errorResponse.detail || 'File already exists'}`));
          } catch (e) {
            reject(new Error('Duplicate: File already exists'));
          }
        } else {
          try {
            const errorResponse = JSON.parse(xhr.responseText);
            reject(new Error(errorResponse.detail || `Upload failed with status ${xhr.status}`));
          } catch (e) {
            reject(new Error(`Upload failed with status ${xhr.status}`));
          }
        }
      };

      // Handle errors
      xhr.onerror = () => {
        reject(new Error('Network error occurred during upload'));
      };

      // Start upload
      const uploadUrl = 'http://localhost:8000/api/upload-edi-report';
      xhr.open('POST', uploadUrl);
      xhr.setRequestHeader('Authorization', `Bearer ${sessionId}`);
      xhr.send(formData);
    });

  } catch (error) {
    console.error("Upload error:", error);
    throw error;
  }
}

export async function uploadMultipleEDIReports(files, onProgress, onFileComplete) {
  const results = [];
  let totalFiles = files.length;
  let completedFiles = 0;

  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    try {
      const result = await uploadEDIReport(file, (progress) => {
        // Calculate overall progress
        const overallProgress = ((completedFiles * 100) + progress) / totalFiles;
        onProgress(Math.round(overallProgress), i, file.name);
      });

      results.push({ file: file.name, success: true, result });
      completedFiles++;

      if (onFileComplete) {
        onFileComplete(file.name, true, result);
      }
    } catch (error) {
      results.push({ file: file.name, success: false, error: error.message });
      completedFiles++;

      if (onFileComplete) {
        onFileComplete(file.name, false, error.message);
      }
    }
  }

  return results;
}