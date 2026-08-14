package store

import (
	"encoding/base64"
	"fmt"
	"strings"
	"time"
)

// encodeCursor and decodeCursor implement an opaque keyset-pagination
// cursor over (created_at, receipt_id) -- the same composite ordering
// Query() sorts by in both PostgresStore and MemoryStore.
//
// The original cursor design encoded only receipt_id, and paginated with
// "receipt_id > cursor". That doesn't work: receipt_id is a random UUID
// (uuid.NewString(), see audit/internal/service/service.go) with no
// relationship to created_at, so "receipt_id > cursor" doesn't express
// "everything after this row in created_at order" -- once a query spans
// more than one page, rows could be silently skipped or duplicated. A
// composite cursor over both columns, matching the ORDER BY exactly,
// fixes this.
//
// Format: base64(RFC3339Nano created_at + "|" + receipt_id). Callers are
// expected to treat cursors as opaque (only ever pass one back verbatim
// from a previous response's next_cursor) -- the internal format isn't a
// compatibility contract. Base64-wrapping it also means a cursor from
// before this fix (a bare receipt_id, no separator) fails to decode
// cleanly rather than being silently misinterpreted as a valid but wrong
// composite cursor, which is the right failure mode here.
func encodeCursor(createdAt time.Time, receiptID string) string {
	raw := createdAt.UTC().Format(time.RFC3339Nano) + "|" + receiptID
	return base64.RawURLEncoding.EncodeToString([]byte(raw))
}

func decodeCursor(cursor string) (time.Time, string, error) {
	raw, err := base64.RawURLEncoding.DecodeString(cursor)
	if err != nil {
		return time.Time{}, "", fmt.Errorf("invalid cursor: %w", err)
	}
	parts := strings.SplitN(string(raw), "|", 2)
	if len(parts) != 2 {
		return time.Time{}, "", fmt.Errorf("invalid cursor: expected created_at|receipt_id")
	}
	createdAt, err := time.Parse(time.RFC3339Nano, parts[0])
	if err != nil {
		return time.Time{}, "", fmt.Errorf("invalid cursor timestamp: %w", err)
	}
	if parts[1] == "" {
		return time.Time{}, "", fmt.Errorf("invalid cursor: empty receipt id")
	}
	return createdAt, parts[1], nil
}
