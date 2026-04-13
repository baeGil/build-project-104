/*
 * API client functions for all backend endpoints
 */

import {
  ContractReviewRequest,
  ContractReviewResult,
  ChatRequest,
  ChatAnswer,
  HealthResponse,
  Citation,
  CitationDetail,
} from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Helper for fetch with error handling
async function fetchWithError<T>(
  url: string,
  options?: RequestInit
): Promise<T> {
  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`API Error ${response.status}: ${errorText}`);
    }

    return await response.json();
  } catch (error) {
    console.error("API request failed:", error);
    throw error;
  }
}

// Health check
export async function getHealth(): Promise<HealthResponse> {
  return fetchWithError<HealthResponse>(`${API_BASE_URL}/api/v1/health`);
}

// Contract review
export async function reviewContract(
  request: ContractReviewRequest
): Promise<ContractReviewResult> {
  return fetchWithError<ContractReviewResult>(
    `${API_BASE_URL}/api/v1/review/contracts`,
    {
      method: "POST",
      body: JSON.stringify(request),
    }
  );
}

// Legal chat (non-streaming)
export async function legalChat(request: ChatRequest): Promise<ChatAnswer> {
  return fetchWithError<ChatAnswer>(`${API_BASE_URL}/api/v1/chat/legal`, {
    method: "POST",
    body: JSON.stringify(request),
  });
}

// Legal chat streaming using fetch + ReadableStream
export async function* streamLegalChat(
  request: ChatRequest
): AsyncGenerator<string, void, unknown> {
  const response = await fetch(`${API_BASE_URL}/api/v1/chat/legal/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`API Error ${response.status}: ${errorText}`);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error("No response body");
  }

  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Process SSE events
      const lines = buffer.split("\n");
      buffer = lines.pop() || ""; // Keep incomplete line in buffer

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const data = line.slice(6).trim();
          if (data && data !== "[DONE]") {
            yield data;
          }
        }
      }
    }

    // Process any remaining data
    if (buffer.startsWith("data: ")) {
      const data = buffer.slice(6).trim();
      if (data && data !== "[DONE]") {
        yield data;
      }
    }
  } finally {
    reader.releaseLock();
  }
}

// Get citation details
export async function getCitation(nodeId: string): Promise<CitationDetail> {
  return fetchWithError<CitationDetail>(
    `${API_BASE_URL}/api/v1/citations/${nodeId}`
  );
}

// Parse citations from SSE data
export function parseCitations(data: string): Citation[] | null {
  if (data.startsWith("[CITATIONS] ")) {
    try {
      const jsonStr = data.slice(11);
      const citations = JSON.parse(jsonStr.replace(/'/g, '"'));
      return citations.map((c: Record<string, string>) => ({
        article_id: c.article_id,
        law_id: c.law_id,
        quote: c.quote,
        document_title: c.document_title,
      }));
    } catch {
      return null;
    }
  }
  return null;
}
