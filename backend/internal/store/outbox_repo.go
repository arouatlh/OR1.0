package store

import (
	"context"
	"database/sql"
	"fmt"
	"strings"
	"time"

	"astrovitals/internal/domain"
)

type OutboxRepo struct {
	db *DB
}

func NewOutboxRepo(db *DB) *OutboxRepo {
	return &OutboxRepo{db: db}
}

func (r *OutboxRepo) Insert(ctx context.Context, item domain.OutboxItem) error {
	const op = "store.outbox.insert"

	_, err := r.db.SQL.ExecContext(ctx, `
		INSERT INTO outbox (entity, entity_id, payload, created_at)
		VALUES (?, ?, ?, ?)
	`, item.Entity, item.EntityID, item.Payload, item.CreatedAt.UnixMilli())
	if err != nil {
		return translateDBError(op, err)
	}

	return nil
}

func (r *OutboxRepo) GetPendingCount(ctx context.Context) (int, error) {
	const op = "store.outbox.get_pending_count"

	var count int
	err := r.db.SQL.QueryRowContext(ctx, `
		SELECT COUNT(1) FROM outbox WHERE synced_at IS NULL
	`).Scan(&count)
	if err != nil {
		return 0, translateDBError(op, err)
	}

	return count, nil
}

func (r *OutboxRepo) GetLastSyncTime(ctx context.Context) (*time.Time, error) {
	const op = "store.outbox.get_last_sync_time"

	var syncedMs sql.NullInt64
	err := r.db.SQL.QueryRowContext(ctx, `
		SELECT MAX(synced_at) FROM outbox WHERE synced_at IS NOT NULL
	`).Scan(&syncedMs)
	if err != nil {
		return nil, translateDBError(op, err)
	}

	if !syncedMs.Valid {
		return nil, nil
	}

	t := time.UnixMilli(syncedMs.Int64).UTC()
	return &t, nil
}

func (r *OutboxRepo) GetPendingItems(ctx context.Context, limit int) ([]domain.OutboxItem, error) {
	const op = "store.outbox.get_pending_items"

	if limit <= 0 {
		limit = 100
	}

	rows, err := r.db.SQL.QueryContext(ctx, `
		SELECT id, entity, entity_id, payload, created_at
		FROM outbox
		WHERE synced_at IS NULL
		ORDER BY id ASC
		LIMIT ?
	`, limit)
	if err != nil {
		return nil, translateDBError(op, err)
	}
	defer rows.Close()

	var result []domain.OutboxItem
	for rows.Next() {
		var item domain.OutboxItem
		var crMs int64
		if err := rows.Scan(&item.ID, &item.Entity, &item.EntityID, &item.Payload, &crMs); err != nil {
			return nil, translateDBError(op, err)
		}
		item.CreatedAt = time.UnixMilli(crMs).UTC()
		result = append(result, item)
	}
	if err := rows.Err(); err != nil {
		return nil, translateDBError(op, err)
	}

	return result, nil
}

func (r *OutboxRepo) MarkSynced(ctx context.Context, ids []int64, syncedAt time.Time) error {
	const op = "store.outbox.mark_synced"

	if len(ids) == 0 {
		return nil
	}

	placeholders := make([]string, len(ids))
	args := make([]any, 0, len(ids)+1)
	args = append(args, syncedAt.UnixMilli())
	for i, id := range ids {
		placeholders[i] = "?"
		args = append(args, id)
	}

	query := fmt.Sprintf(`
		UPDATE outbox
		SET synced_at = ?
		WHERE id IN (%s)
	`, strings.Join(placeholders, ","))

	_, err := r.db.SQL.ExecContext(ctx, query, args...)
	if err != nil {
		return translateDBError(op, err)
	}

	return nil
}
