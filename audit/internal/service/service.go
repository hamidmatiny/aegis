package service

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/aegis-platform/aegis/audit/internal/models"
	"github.com/aegis-platform/aegis/audit/internal/signer"
	"github.com/aegis-platform/aegis/audit/internal/store"
	"github.com/google/uuid"
)

type Service struct {
	store  store.Store
	signer *signer.Signer
}

func New(st store.Store, sg *signer.Signer) *Service {
	return &Service{store: st, signer: sg}
}

func (s *Service) Write(ctx context.Context, req models.WriteReceiptRequest) (models.WriteReceiptResponse, error) {
	if req.TenantID == "" {
		req.TenantID = "default"
	}
	if _, ok := models.ValidEventTypes[req.EventType]; !ok {
		return models.WriteReceiptResponse{}, fmt.Errorf("invalid event_type %q", req.EventType)
	}

	receipt := models.Receipt{
		ReceiptID:         uuid.NewString(),
		EventType:         req.EventType,
		TenantID:          req.TenantID,
		Trace:             req.Trace,
		InputVerdict:      normalizeJSON(req.InputVerdict),
		PolicyDecision:    normalizeJSON(req.PolicyDecision),
		OutputVerdict:     normalizeJSON(req.OutputVerdict),
		ToolDecision:      normalizeJSON(req.ToolDecision),
		PolicyPackID:      req.PolicyPackID,
		PolicyPackVersion: req.PolicyPackVersion,
		Metadata:          normalizeJSON(req.Metadata),
		CreatedAt:         time.Now().UTC().Truncate(time.Microsecond),
	}
	if err := s.signer.SignReceipt(&receipt); err != nil {
		return models.WriteReceiptResponse{}, err
	}
	if err := s.store.Insert(ctx, &receipt); err != nil {
		return models.WriteReceiptResponse{}, err
	}
	return models.WriteReceiptResponse{
		ReceiptID: receipt.ReceiptID,
		Persisted: true,
		Receipt:   receipt,
	}, nil
}

func (s *Service) Get(ctx context.Context, receiptID string) (*models.Receipt, error) {
	return s.store.Get(ctx, receiptID)
}

func (s *Service) Query(ctx context.Context, req models.QueryRequest) (models.QueryResponse, error) {
	return s.store.Query(ctx, req)
}

func (s *Service) Verify(ctx context.Context, receiptID string) (models.VerifyResponse, error) {
	receipt, err := s.store.Get(ctx, receiptID)
	if err != nil {
		return models.VerifyResponse{}, err
	}
	valid, reason := s.signer.VerifyReceipt(receipt)
	return models.VerifyResponse{
		ReceiptID: receiptID,
		Valid:     valid,
		Reason:    reason,
	}, nil
}

func (s *Service) Export(ctx context.Context, req models.ExportRequest) ([]byte, string, string, error) {
	query := models.QueryRequest{
		TenantID:  req.TenantID,
		StartTime: req.StartTime,
		EndTime:   req.EndTime,
		Limit:     1000,
	}
	var all []models.Receipt
	for {
		resp, err := s.store.Query(ctx, query)
		if err != nil {
			return nil, "", "", err
		}
		all = append(all, resp.Receipts...)
		if resp.NextCursor == "" {
			break
		}
		query.Cursor = resp.NextCursor
	}

	format := req.Format
	if format == "" {
		format = "json"
	}
	switch format {
	case "json":
		data, err := json.Marshal(all)
		if err != nil {
			return nil, "", "", err
		}
		return data, "application/json", "audit-export.json", nil
	case "ndjson":
		var b []byte
		for _, receipt := range all {
			line, err := json.Marshal(receipt)
			if err != nil {
				return nil, "", "", err
			}
			b = append(b, line...)
			b = append(b, '\n')
		}
		return b, "application/x-ndjson", "audit-export.ndjson", nil
	default:
		return nil, "", "", fmt.Errorf("unsupported format %q", format)
	}
}

func normalizeJSON(raw json.RawMessage) json.RawMessage {
	if len(raw) == 0 {
		return nil
	}
	var value any
	if err := json.Unmarshal(raw, &value); err != nil {
		return raw
	}
	out, err := json.Marshal(value)
	if err != nil {
		return raw
	}
	return out
}
