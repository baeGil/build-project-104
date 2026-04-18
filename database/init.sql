-- Database initialization script for legal documents system
-- Creates the necessary tables for storing legal documents

-- Create legal_documents table
CREATE TABLE IF NOT EXISTS legal_documents (
    id VARCHAR(255) PRIMARY KEY,
    content TEXT NOT NULL,
    title TEXT,
    doc_type VARCHAR(100),
    law_id VARCHAR(255),          -- Legal document identifier e.g. '36/1999/NĐ-CP' (from so_ky_hieu)
    metadata JSONB,               -- Extra fields: publish_date, effective_date, issuing_body, etc.
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Migrate existing tables: add law_id column if not present (idempotent)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'legal_documents' AND column_name = 'law_id'
    ) THEN
        ALTER TABLE legal_documents ADD COLUMN law_id VARCHAR(255);
    END IF;
END;
$$;

-- Create index on doc_type for faster filtering
CREATE INDEX IF NOT EXISTS idx_legal_documents_doc_type ON legal_documents(doc_type);

-- Create index on law_id for fast citation lookups
CREATE INDEX IF NOT EXISTS idx_legal_documents_law_id ON legal_documents(law_id);

-- Create index on created_at for time-based queries
CREATE INDEX IF NOT EXISTS idx_legal_documents_created_at ON legal_documents(created_at);

-- Create index on title for text search
CREATE INDEX IF NOT EXISTS idx_legal_documents_title ON legal_documents(title);

-- Create index on metadata for JSON queries (GIN for JSONB)
CREATE INDEX IF NOT EXISTS idx_legal_documents_metadata ON legal_documents USING gin(metadata);

-- Create document_relationships table for storing document-to-document links
CREATE TABLE IF NOT EXISTS document_relationships (
    id SERIAL PRIMARY KEY,
    source_doc_id VARCHAR(255) NOT NULL,
    target_doc_id VARCHAR(255) NOT NULL,
    relationship_type VARCHAR(255) NOT NULL,  -- Vietnamese type e.g. 'Văn bản căn cứ'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_doc_id, target_doc_id, relationship_type)
);

-- Create indexes for efficient relationship lookups
CREATE INDEX IF NOT EXISTS idx_rel_source ON document_relationships(source_doc_id);
CREATE INDEX IF NOT EXISTS idx_rel_target ON document_relationships(target_doc_id);
CREATE INDEX IF NOT EXISTS idx_rel_type ON document_relationships(relationship_type);
