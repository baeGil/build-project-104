"use client";

import { useState, useRef, useEffect } from "react";
import { usePersistedState } from "@/lib/hooks";
import { streamLegalChat, parseCitations } from "@/lib/api";
import { ChatMessage, Citation, InlineCitationInfo, Reference } from "@/lib/types";
import { CitationPanel } from "@/components/CitationPanel";
import { InlineCitation } from "@/components/InlineCitation";
import { SourceBlockCompact } from "@/components/SourceBlock";
import { getCitation } from "@/lib/api";
import { CitationDetail } from "@/lib/types";
import {
  Send,
  Bot,
  User,
  AlertCircle,
  Trash2,
  Search,
  Brain,
  MessageCircle,
} from "lucide-react";

// Helper to strip isStreaming for persistence
function stripStreamingFlag(messages: ChatMessage[]): ChatMessage[] {
  return messages.map((msg) => ({
    ...msg,
    isStreaming: false,
  }));
}

type ChatPhase = "searching" | "analyzing" | "responding";

interface StreamingPhaseState {
  phase: ChatPhase;
  startTime: number;
}

export default function ChatPage() {
  const [messages, setMessages] = usePersistedState<ChatMessage[]>("chat_messages", []);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedCitation, setSelectedCitation] = useState<CitationDetail | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  
  // Streaming phase state
  const [streamingPhase, setStreamingPhase] = useState<StreamingPhaseState>({
    phase: "searching",
    startTime: 0,
  });
  const [hasReceivedTokens, setHasReceivedTokens] = useState(false);

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
  
  // Phase transition: searching -> analyzing after 1.5s
  useEffect(() => {
    if (isStreaming && streamingPhase.phase === "searching") {
      const timer = setTimeout(() => {
        if (!hasReceivedTokens) {
          setStreamingPhase({
            phase: "analyzing",
            startTime: Date.now(),
          });
        }
      }, 1500);
      
      return () => clearTimeout(timer);
    }
  }, [isStreaming, streamingPhase.phase, hasReceivedTokens]);

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
    setHasReceivedTokens(false);
    
    // Start with searching phase
    const streamStartTime = Date.now();
    setStreamingPhase({
      phase: "searching",
      startTime: streamStartTime,
    });

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
        // Check for error messages from backend
        if (chunk.startsWith("[ERROR]")) {
          const errorMsg = chunk.slice(8).trim();
          throw new Error(errorMsg || "Đã xảy ra lỗi");
        }

        // Check if this chunk contains citations
        const parsedCitations = parseCitations(chunk);
        if (parsedCitations) {
          citations = parsedCitations;
        } else {
          fullContent += chunk;
          
          // Update phase based on content received
          if (!hasReceivedTokens && fullContent.length > 0) {
            setHasReceivedTokens(true);
            setStreamingPhase({
              phase: "responding",
              startTime: Date.now(),
            });
          }
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
      if (err instanceof DOMException && err.name === 'AbortError') {
        setError("Yêu cầu đã hết thờI gian chờ. Vui lòng thử lại.");
      } else {
        setError(err instanceof Error ? err.message : "Chat failed");
      }
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMessageId
            ? {
                ...msg,
                content: "Xin lỗi, đã có lỗi xảy ra. Vui lòng thử lại.",
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

  const handleInlineCitationClick = (citationInfo: InlineCitationInfo, _num: number) => {
    // Convert InlineCitationInfo to CitationDetail for the panel
    setSelectedCitation({
      article_id: citationInfo.doc_id,
      law_id: (citationInfo.metadata?.law_id as string) || "",
      quote: citationInfo.content,
      document_title: citationInfo.title,
      full_text: citationInfo.content,
    });
  };

  const handleReferenceClick = async (ref: Reference) => {
    try {
      const detail = await getCitation(ref.article_id);
      setSelectedCitation(detail);
    } catch {
      setSelectedCitation({
        article_id: ref.article_id,
        law_id: ref.law_id,
        quote: ref.quote,
        document_title: ref.document_title,
        full_text: ref.quote,
      });
    }
  };

  const clearHistory = () => {
    setMessages([]);
  };
  
  // Phase indicator component
  const PhaseIndicator = () => {
    const getPhaseDisplay = () => {
      switch (streamingPhase.phase) {
        case "searching":
          return {
            icon: <Search className="w-4 h-4 animate-pulse" />,
            text: "Đang tìm kiếm tài liệu",
            dots: true,
          };
        case "analyzing":
          return {
            icon: <Brain className="w-4 h-4 animate-pulse" />,
            text: "Đang phân tích",
            dots: true,
          };
        case "responding":
          return {
            icon: <MessageCircle className="w-4 h-4" />,
            text: "Đang trả lờI",
            dots: false,
          };
        default:
          return {
            icon: <Search className="w-4 h-4 animate-pulse" />,
            text: "Đang xử lý",
            dots: true,
          };
      }
    };
    
    const display = getPhaseDisplay();
    
    return (
      <div className="flex items-center gap-2 text-sm text-muted animate-pulse">
        {display.icon}
        <span>
          {display.text}
          {display.dots && (
            <span className="inline-flex">
              <span className="animate-bounce" style={{ animationDelay: "0ms" }}>.</span>
              <span className="animate-bounce" style={{ animationDelay: "150ms" }}>.</span>
              <span className="animate-bounce" style={{ animationDelay: "300ms" }}>.</span>
            </span>
          )}
        </span>
      </div>
    );
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
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Tư vấn Pháp lý</h1>
          <p className="text-muted mt-1">
            Đặt câu hỏi về pháp luật Việt Nam và nhận câu trả lời từ AI với trích dẫn
          </p>
        </div>
        {messages.length > 0 && (
          <button
            onClick={clearHistory}
            className="flex items-center gap-2 px-4 py-2 text-sm text-red-600 hover:bg-red-50 rounded-lg transition-colors"
          >
            <Trash2 className="w-4 h-4" />
            Xóa lịch sử
          </button>
        )}
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
                Tôi có thể giúp gì cho bạn hôm nay?
              </h3>
              <p className="text-muted max-w-md mb-6">
                Hỏi tôi bất cứ điều gì về pháp luật Việt Nam, điều khoản hợp đồng, hoặc
                tuân thủ pháp lý. Tôi sẽ cung cấp câu trả lời dựa trên hệ thống pháp luật với
                trích dẫn.
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
                        {message.role === "assistant" ? (
                          <InlineCitation
                            text={message.content}
                            onCitationClick={handleInlineCitationClick}
                          />
                        ) : (
                          message.content
                        )}
                        {message.isStreaming && (
                          <span className="inline-block w-2 h-4 bg-primary/50 ml-1 animate-pulse" />
                        )}
                      </p>
                    </div>
                    
                    {/* Phase indicator for streaming assistant messages */}
                    {message.role === "assistant" && message.isStreaming && (
                      <div className="mt-2">
                        <PhaseIndicator />
                      </div>
                    )}

                    {/* Citations for assistant messages */}
                    {message.role === "assistant" &&
                      message.citations &&
                      message.citations.length > 0 && (
                        <SourceBlockCompact
                          references={message.citations.map((c) => ({
                            article_id: c.article_id,
                            law_id: c.law_id,
                            document_title: c.document_title,
                            quote: c.quote,
                          }))}
                          onCitationClick={(ref) => handleReferenceClick(ref)}
                        />
                      )}

                    {/* Confidence indicator */}
                    {message.role === "assistant" &&
                      message.confidence !== undefined && (
                        <div className="mt-2 text-xs text-muted">
                          Độ tin cậy: {Math.round(message.confidence * 100)}%
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
                placeholder="Hỏi về pháp luật Việt Nam..."
                disabled={isStreaming}
                rows={1}
                className="w-full px-4 py-3 pr-12 border border-slate-200 rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary disabled:opacity-50 disabled:bg-slate-100"
                style={{ minHeight: "52px", maxHeight: "200px" }}
              />
              <div className="absolute right-3 bottom-3 text-xs text-muted">
                Enter để gửi
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
