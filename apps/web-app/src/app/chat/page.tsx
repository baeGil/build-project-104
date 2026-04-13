"use client";

import { useState, useRef, useEffect } from "react";
import { streamLegalChat, parseCitations } from "@/lib/api";
import { ChatMessage, Citation } from "@/lib/types";
import { CitationCard } from "@/components/CitationCard";
import { CitationPanel } from "@/components/CitationPanel";
import { getCitation } from "@/lib/api";
import { CitationDetail } from "@/lib/types";
import {
  Send,
  Bot,
  User,
  Sparkles,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  BookOpen,
} from "lucide-react";

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedCitation, setSelectedCitation] = useState<CitationDetail | null>(null);
  const [expandedCitations, setExpandedCitations] = useState<Set<string>>(new Set());
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Auto-resize textarea
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = "auto";
      inputRef.current.style.height = `${Math.min(inputRef.current.scrollHeight, 200)}px`;
    }
  }, [input]);

  const handleSubmit = async () => {
    if (!input.trim() || isStreaming) return;

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: input.trim(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsStreaming(true);
    setError(null);

    const assistantMessageId = `assistant-${Date.now()}`;
    const assistantMessage: ChatMessage = {
      id: assistantMessageId,
      role: "assistant",
      content: "",
      isStreaming: true,
    };

    setMessages((prev) => [...prev, assistantMessage]);

    try {
      const stream = streamLegalChat({
        query: userMessage.content,
        session_id: "demo-session",
      });

      let fullContent = "";
      let citations: Citation[] | null = null;

      for await (const chunk of stream) {
        // Check if this chunk contains citations
        const parsedCitations = parseCitations(chunk);
        if (parsedCitations) {
          citations = parsedCitations;
        } else {
          fullContent += chunk;
        }

        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMessageId
              ? {
                  ...msg,
                  content: fullContent,
                  citations: citations || msg.citations,
                  isStreaming: true,
                }
              : msg
          )
        );
      }

      // Mark streaming as complete
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMessageId
            ? { ...msg, isStreaming: false }
            : msg
        )
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chat failed");
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMessageId
            ? {
                ...msg,
                content: "Sorry, I encountered an error. Please try again.",
                isStreaming: false,
              }
            : msg
        )
      );
    } finally {
      setIsStreaming(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleCitationClick = async (citation: Citation) => {
    try {
      const detail = await getCitation(citation.article_id);
      setSelectedCitation(detail);
    } catch {
      setSelectedCitation({
        ...citation,
        full_text: citation.quote,
      });
    }
  };

  const toggleCitations = (messageId: string) => {
    setExpandedCitations((prev) => {
      const next = new Set(prev);
      if (next.has(messageId)) {
        next.delete(messageId);
      } else {
        next.add(messageId);
      }
      return next;
    });
  };

  const suggestedQuestions = [
    "Điều kiện chấm dứt hợp đồng lao động theo pháp luật Việt Nam?",
    "ThờI hạn bảo hành phần mềm theo quy định pháp luật?",
    "Quyền sở hữu trí tuệ đối với phần mềm được phát triển theo hợp đồng?",
    "Nghĩa vụ bảo mật thông tin trong hợp đồng dịch vụ?",
  ];

  return (
    <div className="h-[calc(100vh-4rem)] flex flex-col">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-slate-900">Legal Chat</h1>
        <p className="text-muted mt-1">
          Ask questions about Vietnamese law and get AI-powered answers with citations
        </p>
      </div>

      {/* Chat Container */}
      <div className="flex-1 bg-white rounded-xl border border-slate-200 shadow-sm flex flex-col overflow-hidden">
        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {messages.length === 0 ? (
            /* Empty State with Suggestions */
            <div className="h-full flex flex-col items-center justify-center text-center px-8">
              <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mb-4">
                <Bot className="w-8 h-8 text-primary" />
              </div>
              <h3 className="text-lg font-semibold text-slate-900 mb-2">
                How can I help you today?
              </h3>
              <p className="text-muted max-w-md mb-6">
                Ask me anything about Vietnamese law, contract terms, or legal
                compliance. I&apos;ll provide answers based on the legal corpus with
                citations.
              </p>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 w-full max-w-2xl">
                {suggestedQuestions.map((question, index) => (
                  <button
                    key={index}
                    onClick={() => {
                      setInput(question);
                      inputRef.current?.focus();
                    }}
                    className="text-left p-4 bg-slate-50 hover:bg-slate-100 rounded-lg border border-slate-200 transition-colors text-sm text-slate-700"
                  >
                    {question}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            /* Messages */
            <>
              {messages.map((message) => (
                <div
                  key={message.id}
                  className={`flex gap-4 ${
                    message.role === "user" ? "flex-row-reverse" : ""
                  }`}
                >
                  {/* Avatar */}
                  <div
                    className={`flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center ${
                      message.role === "user"
                        ? "bg-primary"
                        : "bg-slate-100"
                    }`}
                  >
                    {message.role === "user" ? (
                      <User className="w-5 h-5 text-white" />
                    ) : (
                      <Bot className="w-5 h-5 text-slate-600" />
                    )}
                  </div>

                  {/* Message Content */}
                  <div
                    className={`flex-1 max-w-[80%] ${
                      message.role === "user" ? "text-right" : ""
                    }`}
                  >
                    <div
                      className={`inline-block text-left p-4 rounded-2xl ${
                        message.role === "user"
                          ? "bg-primary text-white"
                          : "bg-slate-100 text-slate-900"
                      }`}
                    >
                      <p className="whitespace-pre-wrap leading-relaxed">
                        {message.content}
                        {message.isStreaming && (
                          <span className="inline-block w-2 h-4 bg-primary/50 ml-1 animate-pulse" />
                        )}
                      </p>
                    </div>

                    {/* Citations for assistant messages */}
                    {message.role === "assistant" &&
                      message.citations &&
                      message.citations.length > 0 && (
                        <div className="mt-3">
                          <button
                            onClick={() => toggleCitations(message.id)}
                            className="flex items-center gap-2 text-sm text-primary hover:text-primary/80 font-medium"
                          >
                            <BookOpen className="w-4 h-4" />
                            {message.citations.length} Citations
                            {expandedCitations.has(message.id) ? (
                              <ChevronUp className="w-4 h-4" />
                            ) : (
                              <ChevronDown className="w-4 h-4" />
                            )}
                          </button>

                          {expandedCitations.has(message.id) && (
                            <div className="mt-2 space-y-2">
                              {message.citations.map((citation, i) => (
                                <CitationCard
                                  key={i}
                                  citation={citation}
                                  onClick={() => handleCitationClick(citation)}
                                  compact
                                />
                              ))}
                            </div>
                          )}
                        </div>
                      )}

                    {/* Confidence indicator */}
                    {message.role === "assistant" &&
                      message.confidence !== undefined && (
                        <div className="mt-2 text-xs text-muted">
                          Confidence: {Math.round(message.confidence * 100)}%
                        </div>
                      )}
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </>
          )}

          {/* Error Message */}
          {error && (
            <div className="flex items-center gap-2 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
              <AlertCircle className="w-5 h-5" />
              <span>{error}</span>
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="border-t border-slate-200 p-4 bg-slate-50">
          <div className="flex items-end gap-2 max-w-4xl mx-auto">
            <div className="flex-1 relative">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask a legal question..."
                disabled={isStreaming}
                rows={1}
                className="w-full px-4 py-3 pr-12 border border-slate-200 rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary disabled:opacity-50 disabled:bg-slate-100"
                style={{ minHeight: "52px", maxHeight: "200px" }}
              />
              <div className="absolute right-3 bottom-3 text-xs text-muted">
                Enter to send
              </div>
            </div>
            <button
              onClick={handleSubmit}
              disabled={!input.trim() || isStreaming}
              className="flex-shrink-0 w-12 h-[52px] bg-primary text-white rounded-xl hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center"
            >
              {isStreaming ? (
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <Send className="w-5 h-5" />
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Citation Panel */}
      <CitationPanel
        citation={selectedCitation}
        onClose={() => setSelectedCitation(null)}
      />
    </div>
  );
}
