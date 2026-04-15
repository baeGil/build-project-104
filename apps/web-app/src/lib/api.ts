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
  ReviewStreamEvent,
} from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function extractSsePayloads(buffer: string): {
  payloads: string[];
  remaining: string;
} {
  const normalized = buffer.replace(/\r\n/g, "\n");
  const events = normalized.split("\n\n");

  if (events.length === 1) {
    return { payloads: [], remaining: normalized };
  }

  const remaining = events.pop() ?? "";
  const payloads = events
    .map((event) =>
      event
        .split("\n")
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trimStart())
        .join("\n")
        .trim()
    )
    .filter(Boolean);

  return { payloads, remaining };
}

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
  request: ChatRequest,
  signal?: AbortSignal
): AsyncGenerator<string, void, unknown> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 60000); // 60s timeout

  // Link external signal if provided
  if (signal) {
    signal.addEventListener('abort', () => controller.abort());
  }

  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/chat/legal/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
      signal: controller.signal,
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

        const { payloads, remaining } = extractSsePayloads(buffer);
        buffer = remaining;

        for (const data of payloads) {
          if (data !== "[DONE]") {
            yield data;
          }
        }
      }

      const { payloads } = extractSsePayloads(`${buffer}\n\n`);
      for (const data of payloads) {
        if (data !== "[DONE]") {
          yield data;
        }
      }
    } finally {
      reader.releaseLock();
    }
  } finally {
    clearTimeout(timeoutId);
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
      const jsonStr = data.slice(12);
      const citations = JSON.parse(jsonStr);
      return citations.map((c: Record<string, string>) => ({
        article_id: c.article_id,
        law_id: c.law_id,
        quote: c.quote,
        document_title: c.document_title,
      }));
    } catch {
      try {
        const fallback = JSON.parse(data.slice(12).replace(/'/g, '"'));
        return fallback.map((c: Record<string, string>) => ({
          article_id: c.article_id,
          law_id: c.law_id,
          quote: c.quote,
          document_title: c.document_title,
        }));
      } catch {
        return null;
      }
    }
  }
  return null;
}

// Streaming contract review using fetch + ReadableStream
export async function* streamContractReview(
  request: ContractReviewRequest,
  signal?: AbortSignal
): AsyncGenerator<ReviewStreamEvent, void, unknown> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 120000); // 120s timeout

  // Link external signal if provided
  if (signal) {
    signal.addEventListener('abort', () => controller.abort());
  }

  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/review/contracts/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
      signal: controller.signal,
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

        const { payloads, remaining } = extractSsePayloads(buffer);
        buffer = remaining;

        for (const data of payloads) {
          if (data && data !== "[DONE]") {
            try {
              const event: ReviewStreamEvent = JSON.parse(data);
              yield event;
            } catch {
              continue;
            }
          }
        }
      }

      const { payloads } = extractSsePayloads(`${buffer}\n\n`);
      for (const data of payloads) {
        if (data && data !== "[DONE]") {
          try {
            const event: ReviewStreamEvent = JSON.parse(data);
            yield event;
          } catch {
            // Skip invalid JSON
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  } finally {
    clearTimeout(timeoutId);
  }
}

// Dataset Ingestion API
export const ingestionApi = {
  // Start ingestion
  async startIngestion(limit: number = 50) {
    return fetchWithError<any>(
      `${API_BASE_URL}/api/v1/ingest/dataset/start?limit=${limit}`,
      { method: 'POST' }
    );
  },

  // Get task status
  async getTaskStatus(taskId: string) {
    return fetchWithError<any>(
      `${API_BASE_URL}/api/v1/ingest/dataset/status/${taskId}`
    );
  },

  // List tasks
  async listTasks(limit: number = 20) {
    return fetchWithError<any[]>(
      `${API_BASE_URL}/api/v1/ingest/dataset/tasks?limit=${limit}`
    );
  },

  // Cancel task
  async cancelTask(taskId: string) {
    return fetchWithError<any>(
      `${API_BASE_URL}/api/v1/ingest/dataset/cancel/${taskId}`,
      { method: 'POST' }
    );
  },
};
