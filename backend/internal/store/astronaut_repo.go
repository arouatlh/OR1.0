package store

import (
	"context"
	"time"

	"astrovitals/internal/apperr"
	"astrovitals/internal/domain"
)

type AstronautRepo struct {
	db *DB
}

func NewAstronautRepo(db *DB) *AstronautRepo {
	return &AstronautRepo{db: db}
}

func (r *AstronautRepo) List(ctx context.Context) ([]domain.Astronaut, error) {
	const op = "store.astronaut.list"

	rows, err := r.db.SQL.QueryContext(ctx, `
		SELECT id, display_name, mission, mode, baseline_hr, created_at
		FROM astronauts
		ORDER BY id ASC
	`)
	if err != nil {
		return nil, translateDBError(op, err)
	}
	defer rows.Close()

	var result []domain.Astronaut
	for rows.Next() {
		var a domain.Astronaut
		var createdMs int64
		if err := rows.Scan(&a.ID, &a.DisplayName, &a.Mission, &a.Mode, &a.BaselineHR, &createdMs); err != nil {
			return nil, translateDBError(op, err)
		}
		a.CreatedAt = time.UnixMilli(createdMs).UTC()
		result = append(result, a)
	}
	if err := rows.Err(); err != nil {
		return nil, translateDBError(op, err)
	}

	return result, nil
}

func (r *AstronautRepo) GetByID(ctx context.Context, id string) (*domain.Astronaut, error) {
	const op = "store.astronaut.get_by_id"

	var a domain.Astronaut
	var createdMs int64
	err := r.db.SQL.QueryRowContext(ctx, `
		SELECT id, display_name, mission, mode, baseline_hr, created_at
		FROM astronauts
		WHERE id = ?
	`, id).Scan(&a.ID, &a.DisplayName, &a.Mission, &a.Mode, &a.BaselineHR, &createdMs)
	if err != nil {
		return nil, translateDBError(op, err)
	}
	a.CreatedAt = time.UnixMilli(createdMs).UTC()

	return &a, nil
}

func (r *AstronautRepo) UpdateMode(ctx context.Context, id string, mode domain.Mode) error {
	const op = "store.astronaut.update_mode"

	res, err := r.db.SQL.ExecContext(ctx, `
		UPDATE astronauts
		SET mode = ?
		WHERE id = ?
	`, mode, id)
	if err != nil {
		return translateDBError(op, err)
	}

	affected, err := res.RowsAffected()
	if err != nil {
		return translateDBError(op, err)
	}
	if affected == 0 {
		return apperr.NotFound(op, "Astronaut not found.")
	}

	return nil
}
