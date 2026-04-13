"use client";

import { useState } from "react";
import {
  Upload,
  Database,
  FileText,
  CheckCircle,
  AlertCircle,
  Loader2,
  Plus,
  Trash2,
} from "lucide-react";

interface DocumentForm {
  id: string;
  title: string;
  content: string;
  docType: string;
  lawId: string;
}

export default function IngestPage() {
  const [documents, setDocuments] = useState<DocumentForm[]>([
    { id: "1", title: "", content: "", docType: "luat", lawId: "" },
  ]);
  const [source, setSource] = useState("manual");
  const [batchSize, setBatchSize] = useState(100);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{
    success: boolean;
    message: string;
  } | null>(null);

  const addDocument = () => {
    setDocuments((prev) => [
      ...prev,
      {
        id: Date.now().toString(),
        title: "",
        content: "",
        docType: "luat",
        lawId: "",
      },
    ]);
  };

  const removeDocument = (id: string) => {
    setDocuments((prev) => prev.filter((d) => d.id !== id));
  };

  const updateDocument = (id: string, field: keyof DocumentForm, value: string) => {
    setDocuments((prev) =>
      prev.map((d) => (d.id === id ? { ...d, [field]: value } : d))
    );
  };

  const handleSubmit = async () => {
    const validDocs = documents.filter((d) => d.title && d.content);
    if (validDocs.length === 0) {
      setResult({
        success: false,
        message: "Please add at least one valid document with title and content",
      });
      return;
    }

    setLoading(true);
    setResult(null);

    // Simulate API call
    setTimeout(() => {
      setResult({
        success: true,
        message: `Successfully queued ${validDocs.length} documents for ingestion. Task ID: task-${Date.now()}`,
      });
      setLoading(false);
      setDocuments([{ id: "1", title: "", content: "", docType: "luat", lawId: "" }]);
    }, 1500);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-slate-900">Ingest Documents</h1>
        <p className="text-muted mt-1">
          Add new legal documents to the corpus for retrieval and analysis
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
              <Database className="w-6 h-6 text-blue-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-slate-900">12,458</p>
              <p className="text-sm text-muted">Total Documents</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
              <CheckCircle className="w-6 h-6 text-green-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-slate-900">12,400</p>
              <p className="text-sm text-muted">Indexed</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-yellow-100 rounded-lg flex items-center justify-center">
              <Loader2 className="w-6 h-6 text-yellow-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-slate-900">58</p>
              <p className="text-sm text-muted">Pending</p>
            </div>
          </div>
        </div>
      </div>

      {/* Configuration */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
        <h2 className="text-lg font-semibold text-slate-900 mb-4">
          Ingestion Settings
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              Source
            </label>
            <input
              type="text"
              value={source}
              onChange={(e) => setSource(e.target.value)}
              className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
              placeholder="e.g., manual, import, api"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              Batch Size
            </label>
            <input
              type="number"
              value={batchSize}
              onChange={(e) => setBatchSize(parseInt(e.target.value) || 100)}
              min={1}
              max={1000}
              className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
            />
          </div>
        </div>
      </div>

      {/* Documents */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900">
            Documents ({documents.length})
          </h2>
          <button
            onClick={addDocument}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors"
          >
            <Plus className="w-4 h-4" />
            Add Document
          </button>
        </div>

        {documents.map((doc, index) => (
          <div
            key={doc.id}
            className="bg-white rounded-xl border border-slate-200 shadow-sm p-6"
          >
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <FileText className="w-5 h-5 text-primary" />
                <span className="font-medium text-slate-900">
                  Document {index + 1}
                </span>
              </div>
              {documents.length > 1 && (
                <button
                  onClick={() => removeDocument(doc.id)}
                  className="p-2 text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              )}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  Title
                </label>
                <input
                  type="text"
                  value={doc.title}
                  onChange={(e) => updateDocument(doc.id, "title", e.target.value)}
                  className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
                  placeholder="Document title"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  Law ID
                </label>
                <input
                  type="text"
                  value={doc.lawId}
                  onChange={(e) => updateDocument(doc.id, "lawId", e.target.value)}
                  className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
                  placeholder="e.g., luat-2023-01"
                />
              </div>
            </div>

            <div className="mb-4">
              <label className="block text-sm font-medium text-slate-700 mb-2">
                Document Type
              </label>
              <select
                value={doc.docType}
                onChange={(e) => updateDocument(doc.id, "docType", e.target.value)}
                className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
              >
                <option value="luat">Luật (Law)</option>
                <option value="nghi_dinh">Nghị định (Decree)</option>
                <option value="thong_tu">Thông tư (Circular)</option>
                <option value="quyet_dinh">Quyết định (Decision)</option>
                <option value="nghi_quyet">Nghị quyết (Resolution)</option>
                <option value="other">Other</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                Content
              </label>
              <textarea
                value={doc.content}
                onChange={(e) => updateDocument(doc.id, "content", e.target.value)}
                rows={6}
                className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary font-mono text-sm"
                placeholder="Paste document content here..."
              />
            </div>
          </div>
        ))}
      </div>

      {/* Result */}
      {result && (
        <div
          className={`flex items-center gap-3 p-4 rounded-lg ${
            result.success
              ? "bg-green-50 border border-green-200 text-green-700"
              : "bg-red-50 border border-red-200 text-red-700"
          }`}
        >
          {result.success ? (
            <CheckCircle className="w-5 h-5" />
          ) : (
            <AlertCircle className="w-5 h-5" />
          )}
          <span>{result.message}</span>
        </div>
      )}

      {/* Submit */}
      <div className="flex justify-end">
        <button
          onClick={handleSubmit}
          disabled={loading}
          className="flex items-center gap-2 px-6 py-3 bg-primary text-white font-semibold rounded-xl hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              Processing...
            </>
          ) : (
            <>
              <Upload className="w-5 h-5" />
              Ingest Documents
            </>
          )}
        </button>
      </div>
    </div>
  );
}
