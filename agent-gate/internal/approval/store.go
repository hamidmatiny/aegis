package approval

import (
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"sync"
	"time"

	"github.com/aegis-platform/aegis/agent-gate/internal/models"
)

// Store holds pending human approval requests (in-memory; Postgres planned).
type Store struct {
	mu        sync.RWMutex
	approvals map[string]*models.ApprovalRequest
	ttl       time.Duration
}

func NewStore(ttl time.Duration) *Store {
	if ttl <= 0 {
		ttl = 24 * time.Hour
	}
	return &Store{
		approvals: make(map[string]*models.ApprovalRequest),
		ttl:       ttl,
	}
}

func (s *Store) Create(call models.ToolCallRequest, tenantID string) (*models.ApprovalRequest, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	now := time.Now().UTC()
	id, err := newApprovalID()
	if err != nil {
		return nil, err
	}
	req := &models.ApprovalRequest{
		ApprovalID: id,
		ToolCall:   call,
		TenantID:   tenantID,
		CreatedAt:  now,
		ExpiresAt:  now.Add(s.ttl),
		Status:     models.StatusAwaitingHumanApproval,
	}
	s.approvals[req.ApprovalID] = req
	return req, nil
}

// newApprovalID returns a cryptographically random approval ID. A
// predictable ID (e.g. a timestamp) would let an attacker who knows
// roughly when a call was submitted guess or enumerate pending approval
// IDs; that matters far less now that /decide is reviewer-key-gated, but
// there is no reason to keep a guessable identifier for something a
// human approval decision hinges on.
func newApprovalID() (string, error) {
	b := make([]byte, 16)
	if _, err := rand.Read(b); err != nil {
		return "", fmt.Errorf("generate approval id: %w", err)
	}
	return "appr-" + hex.EncodeToString(b), nil
}

func (s *Store) Get(id string) (*models.ApprovalRequest, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	req, ok := s.approvals[id]
	if !ok {
		return nil, fmt.Errorf("approval %q not found", id)
	}
	if time.Now().UTC().After(req.ExpiresAt) {
		return nil, fmt.Errorf("approval %q expired", id)
	}
	return req, nil
}

// List returns approval requests, optionally filtered to pending only.
func (s *Store) List(pendingOnly bool) []*models.ApprovalRequest {
	s.mu.RLock()
	defer s.mu.RUnlock()

	now := time.Now().UTC()
	out := make([]*models.ApprovalRequest, 0, len(s.approvals))
	for _, req := range s.approvals {
		if now.After(req.ExpiresAt) {
			continue
		}
		if pendingOnly && req.Status != models.StatusAwaitingHumanApproval {
			continue
		}
		out = append(out, req)
	}
	return out
}

func (s *Store) Decide(id string, action models.ApprovalAction) (*models.ApprovalRequest, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	req, ok := s.approvals[id]
	if !ok {
		return nil, fmt.Errorf("approval %q not found", id)
	}
	if time.Now().UTC().After(req.ExpiresAt) {
		return nil, fmt.Errorf("approval %q expired", id)
	}
	if req.Status != models.StatusAwaitingHumanApproval {
		return nil, fmt.Errorf("approval %q is not pending (status=%s)", id, req.Status)
	}

	req.ReviewerID = action.ReviewerID
	req.ReviewComment = action.Comment
	if action.Approved {
		req.Status = models.StatusApproved
	} else {
		req.Status = models.StatusDenied
	}
	return req, nil
}
