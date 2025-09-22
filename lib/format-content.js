// Utility functions for formatting AI response content

/**
 * Parses citation references from text and extracts the main content and citations
 * @param {string} text - The text containing citations like 【4:3†source】
 * @returns {object} - Object with cleanText and citations array
 */
export function parseCitations(text) {
  const citationRegex = /【(\d+):(\d+)†([^】]*)】/g;
  const citations = [];
  let match;
  
  // Extract all citations
  while ((match = citationRegex.exec(text)) !== null) {
    citations.push({
      documentId: match[1],
      sectionId: match[2], 
      source: match[3],
      fullText: match[0]
    });
  }
  
  // Remove citation markers from text
  const cleanText = text.replace(citationRegex, '');
  
  return {
    cleanText: cleanText.trim(),
    citations
  };
}

/**
 * Formats citations for display
 * @param {Array} citations - Array of citation objects
 * @returns {string} - Formatted citation text
 */
export function formatCitations(citations) {
  if (!citations || citations.length === 0) return '';
  
  return citations.map((citation, index) => 
    `[${index + 1}] ${citation.source || 'Source'}`
  ).join(', ');
}