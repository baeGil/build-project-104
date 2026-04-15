-- Database initialization script for legal documents system
-- Creates the necessary tables for storing legal documents

-- Create legal_documents table
CREATE TABLE IF NOT EXISTS legal_documents (
    id VARCHAR(255) PRIMARY KEY,
    content TEXT NOT NULL,
    title TEXT,
    doc_type VARCHAR(100),
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create index on doc_type for faster filtering
CREATE INDEX IF NOT EXISTS idx_legal_documents_doc_type ON legal_documents(doc_type);

-- Create index on created_at for time-based queries
CREATE INDEX IF NOT EXISTS idx_legal_documents_created_at ON legal_documents(created_at);

-- Create index on metadata for JSON queries
CREATE INDEX IF NOT EXISTS idx_legal_documents_metadata ON legal_documents USING gin(metadata);
