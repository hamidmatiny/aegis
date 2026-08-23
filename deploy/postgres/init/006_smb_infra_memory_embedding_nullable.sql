-- SMB Copilot: embeddings filled in Phase 3; intake stores rows without vectors
ALTER TABLE infra_memory
    ALTER COLUMN embedding DROP NOT NULL;
