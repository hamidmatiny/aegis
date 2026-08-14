package store

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"sort"
	"sync"
	"time"

	"github.com/google/uuid"

	"github.com/aegis-platform/aegis/audit/internal/models"
)

var ErrNotFound = errors.New("receipt not found")

type Store interface {
	Insert(ctx context.Context, receipt *models.Receipt) error
	Get(ctx context.Context, receiptID string) (*models.Receipt, error)
	Query(ctx context.Context, req models.QueryRequest) (models.QueryResponse, error)
}

type MemoryStore struct {
	mu       sync.RWMutex
	receipts map[string]models.Receipt
}

func NewMemoryStore() *MemoryStore {
	return &MemoryStore{receipts: make(map[string]models.Receipt)}
}

func (s *MemoryStore) Insert(_ context.Context, receipt *models.Receipt) error {
	if err := validateReceipt(receipt); err != nil {
		return err
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	if receipt.ReceiptID == "" {
		receipt.ReceiptID = uuid.NewString()
	}
	s.receipts[receipt.ReceiptID] = *receipt
	return nil
}

func (s *MemoryStore) Get(_ context.Context, receiptID string) (*models.Receipt, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	receipt, ok := s.receipts[receiptID]
	if !ok {
		return nil, ErrNotFound
	}
	copy := receipt
	return &copy, nil
}

func (s *MemoryStore) Query(_ context.Context, req models.QueryRequest) (models.QueryResponse, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	limit := req.Limit
	if limit <= 0 {
		limit = 50
	}

	// Decode once, up front, so a malformed cursor fails clearly instead
	// of silently comparing against a zero-value time.Time for every row.
	var cursorCreatedAt time.Time
	var cursorReceiptID string
	if req.Cursor != "" {
		var err error
		cursorCreatedAt, cursorReceiptID, err = decodeCursor(req.Cursor)
		if err != nil {
			return models.QueryResponse{}, fmt.Errorf("query: %w", err)
		}
	}

	type item struct {
		id        string
		createdAt time.Time
		receipt   models.Receipt
	}
	items := make([]item, 0, len(s.receipts))
	for id, receipt := range s.receipts {
		if req.TenantID != "" && receipt.TenantID != req.TenantID {
			continue
		}
		if req.EventType != "" && receipt.EventType != req.EventType {
			continue
		}
		if req.TraceID != "" {
			traceID := ""
			if receipt.Trace != nil {
				traceID = receipt.Trace.TraceID
			}
			if traceID != req.TraceID {
				continue
			}
		}
		if req.StartTime != nil && receipt.CreatedAt.Before(*req.StartTime) {
			continue
		}
		if req.EndTime != nil && receipt.CreatedAt.After(*req.EndTime) {
			continue
		}
		if req.Cursor != "" {
			// Composite keyset comparison matching the (createdAt, id)
			// sort below: skip anything not strictly after the cursor.
			if receipt.CreatedAt.Before(cursorCreatedAt) {
				continue
			}
			if receipt.CreatedAt.Equal(cursorCreatedAt) && id <= cursorReceiptID {
				continue
			}
		}
		items = append(items, item{id: id, createdAt: receipt.CreatedAt, receipt: receipt})
	}

	sort.Slice(items, func(i, j int) bool {
		if items[i].createdAt.Equal(items[j].createdAt) {
			return items[i].id < items[j].id
		}
		return items[i].createdAt.Before(items[j].createdAt)
	})

	// The cursor must be the LAST item actually being returned in this
	// page, not the first item of the next page -- using the latter was a
	// real, separate off-by-one bug that silently dropped exactly one item
	// at every page boundary (see postgres.go's Query() for the full
	// explanation; verified with a 25-item/limit-4 simulation).
	out := make([]models.Receipt, 0, limit)
	for i, it := range items {
		if i >= limit {
			break
		}
		out = append(out, it.receipt)
	}
	var nextCursor string
	if len(items) > limit {
		last := out[len(out)-1]
		nextCursor = encodeCursor(last.CreatedAt, last.ReceiptID)
	}

	return models.QueryResponse{Receipts: out, NextCursor: nextCursor}, nil
}

func payloadJSON(receipt *models.Receipt) ([]byte, error) {
	type payload struct {
		Trace             *models.TraceContext `json:"trace,omitempty"`
		InputVerdict      json.RawMessage      `json:"input_verdict,omitempty"`
		PolicyDecision    json.RawMessage      `json:"policy_decision,omitempty"`
		OutputVerdict     json.RawMessage      `json:"output_verdict,omitempty"`
		ToolDecision      json.RawMessage      `json:"tool_decision,omitempty"`
		PolicyPackID      string               `json:"policy_pack_id,omitempty"`
		PolicyPackVersion string               `json:"policy_pack_version,omitempty"`
		Metadata          json.RawMessage      `json:"metadata,omitempty"`
	}
	return json.Marshal(payload{
		Trace:             receipt.Trace,
		InputVerdict:      receipt.InputVerdict,
		PolicyDecision:    receipt.PolicyDecision,
		OutputVerdict:     receipt.OutputVerdict,
		ToolDecision:      receipt.ToolDecision,
		PolicyPackID:      receipt.PolicyPackID,
		PolicyPackVersion: receipt.PolicyPackVersion,
		Metadata:          receipt.Metadata,
	})
}

func traceIDs(receipt *models.Receipt) (traceID, requestID string) {
	if receipt.Trace == nil {
		return "", ""
	}
	return receipt.Trace.TraceID, receipt.Trace.RequestID
}

func validateReceipt(receipt *models.Receipt) error {
	if receipt.EventType == "" {
		return fmt.Errorf("event_type required")
	}
	if _, ok := models.ValidEventTypes[receipt.EventType]; !ok {
		return fmt.Errorf("invalid event_type %q", receipt.EventType)
	}
	if receipt.TenantID == "" {
		return fmt.Errorf("tenant_id required")
	}
	return nil
}
