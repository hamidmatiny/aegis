package approval

import (
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
	req := &models.ApprovalRequest{
		ApprovalID: fmt.Sprintf("appr-%d", now.UnixNano()),
		ToolCall:   call,
		TenantID:   tenantID,
		CreatedAt:  now,
		ExpiresAt:  now.Add(s.ttl),
		Status:     models.StatusAwaitingHumanApproval,
	}
	s.approvals[req.ApprovalID] = req
	return req, nil
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
