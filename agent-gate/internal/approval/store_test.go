package approval_test

import (
	"testing"
	"time"

	"github.com/aegis-platform/aegis/agent-gate/internal/approval"
	"github.com/aegis-platform/aegis/agent-gate/internal/models"
)

func TestCreateGeneratesUnpredictableIDs(t *testing.T) {
	s := approval.NewStore(time.Hour)
	seen := map[string]bool{}
	for i := 0; i < 50; i++ {
		req, err := s.Create(models.ToolCallRequest{ToolName: "delete_database"}, "default")
		if err != nil {
			t.Fatalf("Create: %v", err)
		}
		if seen[req.ApprovalID] {
			t.Fatalf("duplicate approval id generated: %s", req.ApprovalID)
		}
		seen[req.ApprovalID] = true
		if len(req.ApprovalID) < len("appr-")+16 {
			t.Fatalf("approval id looks too short to be random: %s", req.ApprovalID)
		}
	}
}

func TestDecideRejectsAlreadyDecided(t *testing.T) {
	s := approval.NewStore(time.Hour)
	req, err := s.Create(models.ToolCallRequest{ToolName: "delete_database"}, "default")
	if err != nil {
		t.Fatalf("Create: %v", err)
	}

	if _, err := s.Decide(req.ApprovalID, models.ApprovalAction{Approved: true, ReviewerID: "r1"}); err != nil {
		t.Fatalf("first Decide: %v", err)
	}
	// A second decide on the same id (replay) must fail, not silently
	// re-apply — otherwise a denied action could be flipped to approved
	// by resubmitting.
	if _, err := s.Decide(req.ApprovalID, models.ApprovalAction{Approved: true, ReviewerID: "r2"}); err == nil {
		t.Fatal("expected error deciding an already-decided approval")
	}
}
