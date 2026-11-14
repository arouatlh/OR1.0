package store

import (
	"context"
	"database/sql"
	"fmt"
	"strings"
	"time"

	"astrovitals/internal/apperr"
	"astrovitals/internal/domain"
)

type AlertRepo struct {
	db *DB
}

func NewAlertRepo(db *DB) *AlertRepo {
	return &AlertRepo{db: db}
}

func (r *AlertRepo) Create(ctx context.Context, a domain.Alert) error {
	const op = "store.alert.create"

	_, err := r.db.SQL.ExecContext(ctx, `
		INSERT INTO alerts (
			id, astronaut_id, rule_id, severity, title, message, metric,
			value, threshold, status, origin, created_at, updated_at
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	`, a.ID, a.AstronautID, a.RuleID, string(a.Severity), a.Title, a.Message, a.Metric,
		a.Value, a.Threshold, string(a.Status), string(a.Origin), a.CreatedAt.UnixMilli(), a.UpdatedAt.UnixMilli())
	if err != nil {
		return translateDBError(op, err)
	}

	return nil
}

func (r *AlertRepo) Update(ctx context.Context, a domain.Alert) error {
	const op = "store.alert.update"

	res, err := r.db.SQL.ExecContext(ctx, `
		UPDATE alerts
		SET severity = ?, title = ?, message = ?, value = ?, threshold = ?, status = ?, updated_at = ?
		WHERE id = ?
	`, string(a.Severity), a.Title, a.Message, a.Value, a.Threshold, string(a.Status), a.UpdatedAt.UnixMilli(), a.ID)
	if err != nil {
		return translateDBError(op, err)
	}

	aff, err := res.RowsAffected()
	if err != nil {
		return translateDBError(op, err)
	}
	if aff == 0 {
		return apperr.NotFound(op, "Alert not found.")
	}

	return nil
}

func (r *AlertRepo) GetByID(ctx context.Context, id string) (*domain.Alert, error) {
	const op = "store.alert.get_by_id"

	row := r.db.SQL.QueryRowContext(ctx, `
		SELECT id, astronaut_id, rule_id, severity, title, message, metric,
		       value, threshold, status, origin, created_at, updated_at
		FROM alerts
		WHERE id = ?
	`, id)

	a, err := scanAlert(row)
	if err != nil {
		return nil, translateDBError(op, err)
	}

	return a, nil
}

func (r *AlertRepo) Acknowledge(ctx context.Context, id string, ackTime time.Time) (*domain.Alert, error) {
	const op = "store.alert.acknowledge"

	alert, err := r.GetByID(ctx, id)
	if err != nil {
		return nil, err
	}

	if alert.Status == domain.AlertStatusResolved {
		return nil, apperr.Conflict(op, "Cannot acknowledge a resolved alert.", nil)
	}

	alert.Status = domain.AlertStatusAcknowledged
	alert.UpdatedAt = ackTime

	if err := r.Update(ctx, *alert); err != nil {
		return nil, err
	}

	return alert, nil
}

func (r *AlertRepo) GetOpenByAstronautID(ctx context.Context, astronautID string) (map[string]domain.Alert, error) {
	const op = "store.alert.get_open_by_astro"

	rows, err := r.db.SQL.QueryContext(ctx, `
		SELECT id, astronaut_id, rule_id, severity, title, message, metric,
		       value, threshold, status, origin, created_at, updated_at
		FROM alerts
		WHERE astronaut_id = ? AND status IN ('open', 'acknowledged')
	`, astronautID)
	if err != nil {
		return nil, translateDBError(op, err)
	}
	defer rows.Close()

	res := make(map[string]domain.Alert)
	for rows.Next() {
		a, err := scanAlert(rows)
		if err != nil {
			return nil, translateDBError(op, err)
		}
		res[a.RuleID] = *a
	}
	if err := rows.Err(); err != nil {
		return nil, translateDBError(op, err)
	}

	return res, nil
}

func (r *AlertRepo) List(ctx context.Context, status, severity, astronautID string, offset, limit int) ([]domain.Alert, int, error) {
	const op = "store.alert.list"

	if limit <= 0 {
		limit = 20
	}
	if limit > 500 {
		limit = 500
	}
	if offset < 0 {
		offset = 0
	}

	var conditions []string
	var args []any

	if status != "" {
		conditions = append(conditions, "status = ?")
		args = append(args, status)
	}
	if severity != "" {
		conditions = append(conditions, "severity = ?")
		args = append(args, severity)
	}
	if astronautID != "" {
		conditions = append(conditions, "astronaut_id = ?")
		args = append(args, astronautID)
	}

	whereClause := "1=1"
	if len(conditions) > 0 {
		whereClause = strings.Join(conditions, " AND ")
	}

	countQuery := fmt.Sprintf("SELECT COUNT(1) FROM alerts WHERE %s", whereClause)
	var total int
	if err := r.db.SQL.QueryRowContext(ctx, countQuery, args...).Scan(&total); err != nil {
		return nil, 0, translateDBError(op, err)
	}

	dataQuery := fmt.Sprintf(`
		SELECT id, astronaut_id, rule_id, severity, title, message, metric,
		       value, threshold, status, origin, created_at, updated_at
		FROM alerts
		WHERE %s
		ORDER BY created_at DESC
		LIMIT ? OFFSET ?
	`, whereClause)

	argsWithPaging := append(args, limit, offset)
	rows, err := r.db.SQL.QueryContext(ctx, dataQuery, argsWithPaging...)
	if err != nil {
		return nil, 0, translateDBError(op, err)
	}
	defer rows.Close()

	var result []domain.Alert
	for rows.Next() {
		a, err := scanAlert(rows)
		if err != nil {
			return nil, 0, translateDBError(op, err)
		}
		result = append(result, *a)
	}
	if err := rows.Err(); err != nil {
		return nil, 0, translateDBError(op, err)
	}

	return result, total, nil
}

func (r *AlertRepo) CountOpenByAstronaut(ctx context.Context) (map[string]int, error) {
	const op = "store.alert.count_open"

	rows, err := r.db.SQL.QueryContext(ctx, `
		SELECT astronaut_id, COUNT(1)
		FROM alerts
		WHERE status IN ('open', 'acknowledged')
		GROUP BY astronaut_id
	`)
	if err != nil {
		return nil, translateDBError(op, err)
	}
	defer rows.Close()

	res := make(map[string]int)
	for rows.Next() {
		var aid string
		var count int
		if err := rows.Scan(&aid, &count); err != nil {
			return nil, translateDBError(op, err)
		}
		res[aid] = count
	}
	if err := rows.Err(); err != nil {
		return nil, translateDBError(op, err)
	}

	return res, nil
}

func (r *AlertRepo) CreateAssessment(ctx context.Context, a domain.Assessment) error {
	const op = "store.alert.create_assessment"

	_, err := r.db.SQL.ExecContext(ctx, `
		INSERT INTO assessments (id, astronaut_id, model_version, risk_score, label, explanation, created_at)
		VALUES (?, ?, ?, ?, ?, ?, ?)
	`, a.ID, a.AstronautID, a.ModelVersion, a.RiskScore, a.Label, a.Explanation, a.CreatedAt.UnixMilli())
	if err != nil {
		return translateDBError(op, err)
	}

	return nil
}

func scanAlert(s rowScanner) (*domain.Alert, error) {
	var a domain.Alert
	var crMs, upMs int64

	err := s.Scan(
		&a.ID,
		&a.AstronautID,
		&a.RuleID,
		&a.Severity,
		&a.Title,
		&a.Message,
		&a.Metric,
		&a.Value,
		&a.Threshold,
		&a.Status,
		&a.Origin,
		&crMs,
		&upMs,
	)
	if err != nil {
		if err == sql.ErrNoRows {
			return nil, apperr.NotFound("scanAlert", "Alert not found.")
		}
		return nil, err
	}

	a.CreatedAt = time.UnixMilli(crMs).UTC()
	a.UpdatedAt = time.UnixMilli(upMs).UTC()

	return &a, nil
}
