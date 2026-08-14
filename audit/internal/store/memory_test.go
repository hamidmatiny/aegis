package store_test

import (
	"context"
	"fmt"
	"reflect"
	"testing"
	"time"

	"github.com/aegis-platform/aegis/audit/internal/models"
	"github.com/aegis-platform/aegis/audit/internal/store"
)

// TestMemoryQueryPaginationDoesNotDropOrDuplicateAcrossPages is the
// regression test for the cursor bug: Query() sorts by
// (created_at ASC, receipt_id ASC), but receipt_id is a random UUID with
// no relationship to created_at (see audit/internal/service/service.go's
// uuid.NewString()). Receipt ids here are deliberately assigned in the
// REVERSE of created_at order -- the shape that breaks a single-column
// "receipt_id > cursor" filter as soon as a query spans more than one
// page. A correct composite (created_at, receipt_id) cursor must return
// every receipt exactly once, in created_at order, regardless.
func TestMemoryQueryPaginationDoesNotDropOrDuplicateAcrossPages(t *testing.T) {
	st := store.NewMemoryStore()
	ctx := context.Background()

	const n = 25
	base := time.Date(2026, 6, 1, 0, 0, 0, 0, time.UTC)
	want := make([]string, 0, n)
	for i := 0; i < n; i++ {
		id := fmt.Sprintf("id-%03d", n-i) // reverse of insertion/created_at order
		receipt := models.Receipt{
			ReceiptID: id,
			EventType: models.EventInputDefense,
			TenantID:  "default",
			CreatedAt: base.Add(time.Duration(i) * time.Minute),
		}
		if err := st.Insert(ctx, &receipt); err != nil {
			t.Fatalf("insert %d: %v", i, err)
		}
		want = append(want, id)
	}

	var got []string
	cursor := ""
	pages := 0
	for {
		pages++
		if pages > n+2 {
			t.Fatal("too many pages -- pagination is likely looping")
		}
		resp, err := st.Query(ctx, models.QueryRequest{TenantID: "default", Limit: 4, Cursor: cursor})
		if err != nil {
			t.Fatalf("query page %d: %v", pages, err)
		}
		for _, r := range resp.Receipts {
			got = append(got, r.ReceiptID)
		}
		if resp.NextCursor == "" {
			break
		}
		cursor = resp.NextCursor
	}

	if len(got) != n {
		t.Fatalf("expected %d receipts across all pages, got %d: %v", n, len(got), got)
	}
	seen := make(map[string]int, n)
	for _, id := range got {
		seen[id]++
	}
	for _, id := range want {
		if seen[id] != 1 {
			t.Errorf("receipt %q appeared %d times across pages (want exactly 1)", id, seen[id])
		}
	}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("pagination order mismatch:\n got:  %v\n want: %v", got, want)
	}
}

func TestMemoryQueryRejectsMalformedCursor(t *testing.T) {
	st := store.NewMemoryStore()
	_, err := st.Query(context.Background(), models.QueryRequest{Cursor: "not-a-valid-cursor!!!"})
	if err == nil {
		t.Fatal("expected an error for a malformed cursor")
	}
}

func TestMemoryQuerySinglePageMatchesMultiPage(t *testing.T) {
	st := store.NewMemoryStore()
	ctx := context.Background()

	const n = 10
	base := time.Date(2026, 6, 1, 0, 0, 0, 0, time.UTC)
	for i := 0; i < n; i++ {
		receipt := models.Receipt{
			ReceiptID: fmt.Sprintf("id-%03d", n-i),
			EventType: models.EventInputDefense,
			TenantID:  "default",
			CreatedAt: base.Add(time.Duration(i) * time.Minute),
		}
		if err := st.Insert(ctx, &receipt); err != nil {
			t.Fatalf("insert %d: %v", i, err)
		}
	}

	all, err := st.Query(ctx, models.QueryRequest{TenantID: "default", Limit: n})
	if err != nil {
		t.Fatal(err)
	}
	if len(all.Receipts) != n {
		t.Fatalf("expected %d receipts in a single page, got %d", n, len(all.Receipts))
	}
	if all.NextCursor != "" {
		t.Fatalf("expected no next_cursor when everything fit on one page, got %q", all.NextCursor)
	}
}
