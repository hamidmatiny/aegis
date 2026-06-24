package store

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/aegis-platform/aegis/audit/internal/models"
	_ "github.com/jackc/pgx/v5/stdlib"
)

type PostgresStore struct {
	db *sql.DB
}

func NewPostgresStore(databaseURL string) (*PostgresStore, error) {
	db, err := sql.Open("pgx", databaseURL)
	if err != nil {
		return nil, fmt.Errorf("open postgres: %w", err)
	}
	db.SetMaxOpenConns(10)
	db.SetConnMaxLifetime(5 * time.Minute)
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := db.PingContext(ctx); err != nil {
		_ = db.Close()
		return nil, fmt.Errorf("ping postgres: %w", err)
	}
	return &PostgresStore{db: db}, nil
}

func (s *PostgresStore) Close() error {
	return s.db.Close()
}

func (s *PostgresStore) Insert(ctx context.Context, receipt *models.Receipt) error {
	if err := validateReceipt(receipt); err != nil {
		return err
	}
	payload, err := payloadJSON(receipt)
	if err != nil {
		return err
	}
	traceID, requestID := traceIDs(receipt)
	_, err = s.db.ExecContext(ctx, `
		INSERT INTO audit_receipts (
			receipt_id, tenant_id, event_type, trace_id, request_id,
			policy_pack_id, policy_pack_version, payload,
			payload_hash, signer_key_id, signature, created_at
		) VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9,$10,$11,$12)
	`, receipt.ReceiptID, receipt.TenantID, receipt.EventType, nullText(traceID), nullText(requestID),
		nullText(receipt.PolicyPackID), nullText(receipt.PolicyPackVersion), payload,
		receipt.PayloadHash, receipt.SignerKeyID, receipt.Signature, receipt.CreatedAt.UTC())
	return err
}

func (s *PostgresStore) Get(ctx context.Context, receiptID string) (*models.Receipt, error) {
	row := s.db.QueryRowContext(ctx, `
		SELECT receipt_id, tenant_id, event_type, trace_id, request_id,
			policy_pack_id, policy_pack_version, payload,
			payload_hash, signer_key_id, signature, created_at
		FROM audit_receipts WHERE receipt_id = $1
	`, receiptID)
	receipt, err := scanReceipt(row)
	if err == sql.ErrNoRows {
		return nil, ErrNotFound
	}
	return receipt, err
}

func (s *PostgresStore) Query(ctx context.Context, req models.QueryRequest) (models.QueryResponse, error) {
	limit := req.Limit
	if limit <= 0 {
		limit = 50
	}

	var b strings.Builder
	args := make([]any, 0, 8)
	b.WriteString(`
		SELECT receipt_id, tenant_id, event_type, trace_id, request_id,
			policy_pack_id, policy_pack_version, payload,
			payload_hash, signer_key_id, signature, created_at
		FROM audit_receipts WHERE 1=1`)

	if req.TenantID != "" {
		args = append(args, req.TenantID)
		fmt.Fprintf(&b, " AND tenant_id = $%d", len(args))
	}
	if req.EventType != "" {
		args = append(args, req.EventType)
		fmt.Fprintf(&b, " AND event_type = $%d", len(args))
	}
	if req.TraceID != "" {
		args = append(args, req.TraceID)
		fmt.Fprintf(&b, " AND trace_id = $%d", len(args))
	}
	if req.StartTime != nil {
		args = append(args, *req.StartTime)
		fmt.Fprintf(&b, " AND created_at >= $%d", len(args))
	}
	if req.EndTime != nil {
		args = append(args, *req.EndTime)
		fmt.Fprintf(&b, " AND created_at <= $%d", len(args))
	}
	if req.Cursor != "" {
		args = append(args, req.Cursor)
		fmt.Fprintf(&b, " AND receipt_id > $%d", len(args))
	}
	args = append(args, limit+1)
	fmt.Fprintf(&b, " ORDER BY created_at ASC, receipt_id ASC LIMIT $%d", len(args))

	rows, err := s.db.QueryContext(ctx, b.String(), args...)
	if err != nil {
		return models.QueryResponse{}, err
	}
	defer rows.Close()

	receipts := make([]models.Receipt, 0, limit)
	for rows.Next() {
		receipt, err := scanReceipt(rows)
		if err != nil {
			return models.QueryResponse{}, err
		}
		receipts = append(receipts, *receipt)
	}
	if err := rows.Err(); err != nil {
		return models.QueryResponse{}, err
	}

	var nextCursor string
	if len(receipts) > limit {
		nextCursor = receipts[limit].ReceiptID
		receipts = receipts[:limit]
	}
	return models.QueryResponse{Receipts: receipts, NextCursor: nextCursor}, nil
}

type rowScanner interface {
	Scan(dest ...any) error
}

func scanReceipt(row rowScanner) (*models.Receipt, error) {
	var receipt models.Receipt
	var payload []byte
	var traceID, requestID sql.NullString
	var policyPackID, policyPackVersion sql.NullString
	err := row.Scan(
		&receipt.ReceiptID, &receipt.TenantID, &receipt.EventType,
		&traceID, &requestID, &policyPackID, &policyPackVersion,
		&payload, &receipt.PayloadHash, &receipt.SignerKeyID, &receipt.Signature, &receipt.CreatedAt,
	)
	if err != nil {
		return nil, err
	}

	type payloadShape struct {
		Trace             *models.TraceContext `json:"trace,omitempty"`
		InputVerdict      json.RawMessage      `json:"input_verdict,omitempty"`
		PolicyDecision    json.RawMessage      `json:"policy_decision,omitempty"`
		OutputVerdict     json.RawMessage      `json:"output_verdict,omitempty"`
		ToolDecision      json.RawMessage      `json:"tool_decision,omitempty"`
		PolicyPackID      string               `json:"policy_pack_id,omitempty"`
		PolicyPackVersion string               `json:"policy_pack_version,omitempty"`
		Metadata          json.RawMessage      `json:"metadata,omitempty"`
	}
	var p payloadShape
	if err := json.Unmarshal(payload, &p); err != nil {
		return nil, err
	}

	if traceID.Valid || requestID.Valid {
		receipt.Trace = &models.TraceContext{}
		if traceID.Valid {
			receipt.Trace.TraceID = traceID.String
		}
		if requestID.Valid {
			receipt.Trace.RequestID = requestID.String
		}
	}
	if p.Trace != nil {
		receipt.Trace = p.Trace
	}
	receipt.InputVerdict = normalizeRawJSON(p.InputVerdict)
	receipt.PolicyDecision = normalizeRawJSON(p.PolicyDecision)
	receipt.OutputVerdict = normalizeRawJSON(p.OutputVerdict)
	receipt.ToolDecision = normalizeRawJSON(p.ToolDecision)
	if policyPackID.Valid {
		receipt.PolicyPackID = policyPackID.String
	} else {
		receipt.PolicyPackID = p.PolicyPackID
	}
	if policyPackVersion.Valid {
		receipt.PolicyPackVersion = policyPackVersion.String
	} else {
		receipt.PolicyPackVersion = p.PolicyPackVersion
	}
	receipt.Metadata = normalizeRawJSON(p.Metadata)
	receipt.CreatedAt = receipt.CreatedAt.UTC().Truncate(time.Microsecond)
	return &receipt, nil
}

func nullText(v string) any {
	if v == "" {
		return nil
	}
	return v
}
