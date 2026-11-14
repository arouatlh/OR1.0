package store

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"astrovitals/internal/apperr"
	"astrovitals/internal/domain"
)

type TelemetryRepo struct {
	db *DB
}

func NewTelemetryRepo(db *DB) *TelemetryRepo {
	return &TelemetryRepo{db: db}
}

type Stats5Min struct {
	Count       int
	MeanHR      float64
	MinHR       int
	MaxHR       int
	MeanSpO2    float64
	MinSpO2     int
	MaxSpO2     int
	MeanSystolic float64
	MeanRespRate float64
}

// IngestBatch inserts telemetry samples and corresponding outbox records in a single transaction.
func (r *TelemetryRepo) IngestBatch(ctx context.Context, astronautID string, samples []domain.Telemetry) (int, int, []domain.Telemetry, error) {
	const op = "store.telemetry.ingest_batch"

	tx, err := r.db.SQL.BeginTx(ctx, nil)
	if err != nil {
		return 0, 0, nil, translateDBError(op, err)
	}
	defer tx.Rollback()

	// Verify astronaut exists
	var exists int
	err = tx.QueryRowContext(ctx, `SELECT COUNT(1) FROM astronauts WHERE id = ?`, astronautID).Scan(&exists)
	if err != nil {
		return 0, 0, nil, translateDBError(op, err)
	}
	if exists == 0 {
		return 0, 0, nil, apperr.NotFound(op, fmt.Sprintf("Astronaut %q not found.", astronautID))
	}

	insertTelemetryStmt, err := tx.PrepareContext(ctx, `
		INSERT OR IGNORE INTO telemetry (
			astronaut_id, client_id, recorded_at, received_at, source,
			heart_rate, spo2, systolic, diastolic, resp_rate, ecg_summary, stress_index
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	`)
	if err != nil {
		return 0, 0, nil, translateDBError(op, err)
	}
	defer insertTelemetryStmt.Close()

	insertOutboxStmt, err := tx.PrepareContext(ctx, `
		INSERT INTO outbox (entity, entity_id, payload, created_at)
		VALUES (?, ?, ?, ?)
	`)
	if err != nil {
		return 0, 0, nil, translateDBError(op, err)
	}
	defer insertOutboxStmt.Close()

	var accepted int
	var duplicates int
	var acceptedSamples []domain.Telemetry
	nowMs := time.Now().UTC().UnixMilli()

	for _, s := range samples {
		res, err := insertTelemetryStmt.ExecContext(ctx,
			astronautID,
			s.ClientID,
			s.RecordedAt.UnixMilli(),
			nowMs,
			string(s.Source),
			s.HeartRate,
			s.SpO2,
			s.Systolic,
			s.Diastolic,
			s.RespRate,
			s.ECGSummary,
			s.StressIndex,
		)
		if err != nil {
			return 0, 0, nil, translateDBError(op, err)
		}

		rowsAff, err := res.RowsAffected()
		if err != nil {
			return 0, 0, nil, translateDBError(op, err)
		}

		if rowsAff == 0 {
			duplicates++
		} else {
			accepted++
			lastID, _ := res.LastInsertId()
			sCopy := s
			sCopy.ID = lastID
			sCopy.AstronautID = astronautID
			sCopy.ReceivedAt = time.UnixMilli(nowMs).UTC()
			acceptedSamples = append(acceptedSamples, sCopy)

			// Add to outbox in same transaction
			payloadBytes, err := json.Marshal(sCopy)
			if err != nil {
				return 0, 0, nil, apperr.Internal(op, err)
			}
			_, err = insertOutboxStmt.ExecContext(ctx, "telemetry", fmt.Sprintf("%d", lastID), string(payloadBytes), nowMs)
			if err != nil {
				return 0, 0, nil, translateDBError(op, err)
			}
		}
	}

	if err := tx.Commit(); err != nil {
		return 0, 0, nil, translateDBError(op, err)
	}

	return accepted, duplicates, acceptedSamples, nil
}

func (r *TelemetryRepo) GetLatestByAstronautID(ctx context.Context, astronautID string) (*domain.Telemetry, error) {
	const op = "store.telemetry.get_latest"

	row := r.db.SQL.QueryRowContext(ctx, `
		SELECT id, astronaut_id, client_id, recorded_at, received_at, source,
		       heart_rate, spo2, systolic, diastolic, resp_rate, ecg_summary, stress_index
		FROM telemetry
		WHERE astronaut_id = ?
		ORDER BY recorded_at DESC, id DESC
		LIMIT 1
	`, astronautID)

	t, err := scanTelemetry(row)
	if err != nil {
		if apperr.KindOf(err) == apperr.KindNotFound {
			return nil, nil // No telemetry yet, return nil without error
		}
		return nil, translateDBError(op, err)
	}

	return t, nil
}

// GetRecentWindow returns the last N samples ordered chronologically (oldest first).
func (r *TelemetryRepo) GetRecentWindow(ctx context.Context, astronautID string, limit int) ([]domain.Telemetry, error) {
	const op = "store.telemetry.get_window"

	if limit <= 0 {
		limit = 20
	}

	// Subquery to get latest N samples, then order ascending
	query := `
		SELECT id, astronaut_id, client_id, recorded_at, received_at, source,
		       heart_rate, spo2, systolic, diastolic, resp_rate, ecg_summary, stress_index
		FROM (
			SELECT * FROM telemetry
			WHERE astronaut_id = ?
			ORDER BY recorded_at DESC, id DESC
			LIMIT ?
		)
		ORDER BY recorded_at ASC, id ASC
	`

	rows, err := r.db.SQL.QueryContext(ctx, query, astronautID, limit)
	if err != nil {
		return nil, translateDBError(op, err)
	}
	defer rows.Close()

	var result []domain.Telemetry
	for rows.Next() {
		t, err := scanTelemetry(rows)
		if err != nil {
			return nil, translateDBError(op, err)
		}
		result = append(result, *t)
	}
	if err := rows.Err(); err != nil {
		return nil, translateDBError(op, err)
	}

	return result, nil
}

// GetHistory returns paginated telemetry history with optional time filtering.
func (r *TelemetryRepo) GetHistory(ctx context.Context, astronautID string, from, to *time.Time, offset, limit int, order string) ([]domain.Telemetry, int, error) {
	const op = "store.telemetry.get_history"

	if limit <= 0 {
		limit = 20
	}
	if limit > 500 {
		limit = 500
	}
	if offset < 0 {
		offset = 0
	}

	sortOrder := "DESC"
	if strings.ToUpper(order) == "ASC" {
		sortOrder = "ASC"
	}

	var conditions []string
	var args []any

	conditions = append(conditions, "astronaut_id = ?")
	args = append(args, astronautID)

	if from != nil {
		conditions = append(conditions, "recorded_at >= ?")
		args = append(args, from.UnixMilli())
	}
	if to != nil {
		conditions = append(conditions, "recorded_at <= ?")
		args = append(args, to.UnixMilli())
	}

	whereClause := strings.Join(conditions, " AND ")

	// Count total
	countQuery := fmt.Sprintf("SELECT COUNT(1) FROM telemetry WHERE %s", whereClause)
	var total int
	if err := r.db.SQL.QueryRowContext(ctx, countQuery, args...).Scan(&total); err != nil {
		return nil, 0, translateDBError(op, err)
	}

	// Select rows
	dataQuery := fmt.Sprintf(`
		SELECT id, astronaut_id, client_id, recorded_at, received_at, source,
		       heart_rate, spo2, systolic, diastolic, resp_rate, ecg_summary, stress_index
		FROM telemetry
		WHERE %s
		ORDER BY recorded_at %s, id %s
		LIMIT ? OFFSET ?
	`, whereClause, sortOrder, sortOrder)

	argsWithPaging := append(args, limit, offset)
	rows, err := r.db.SQL.QueryContext(ctx, dataQuery, argsWithPaging...)
	if err != nil {
		return nil, 0, translateDBError(op, err)
	}
	defer rows.Close()

	var result []domain.Telemetry
	for rows.Next() {
		t, err := scanTelemetry(rows)
		if err != nil {
			return nil, 0, translateDBError(op, err)
		}
		result = append(result, *t)
	}
	if err := rows.Err(); err != nil {
		return nil, 0, translateDBError(op, err)
	}

	return result, total, nil
}

// GetStats5Min calculates rolling window metrics for the last 5 minutes.
func (r *TelemetryRepo) GetStats5Min(ctx context.Context, astronautID string, now time.Time) (*Stats5Min, error) {
	const op = "store.telemetry.get_stats_5min"

	fiveMinAgoMs := now.Add(-5 * time.Minute).UnixMilli()
	row := r.db.SQL.QueryRowContext(ctx, `
		SELECT COUNT(1),
		       COALESCE(AVG(heart_rate), 0),
		       COALESCE(MIN(heart_rate), 0),
		       COALESCE(MAX(heart_rate), 0),
		       COALESCE(AVG(spo2), 0),
		       COALESCE(MIN(spo2), 0),
		       COALESCE(MAX(spo2), 0),
		       COALESCE(AVG(systolic), 0),
		       COALESCE(AVG(resp_rate), 0)
		FROM telemetry
		WHERE astronaut_id = ? AND recorded_at >= ?
	`, astronautID, fiveMinAgoMs)

	var s Stats5Min
	err := row.Scan(&s.Count, &s.MeanHR, &s.MinHR, &s.MaxHR, &s.MeanSpO2, &s.MinSpO2, &s.MaxSpO2, &s.MeanSystolic, &s.MeanRespRate)
	if err != nil {
		return nil, translateDBError(op, err)
	}

	return &s, nil
}

type rowScanner interface {
	Scan(dest ...any) error
}

func scanTelemetry(s rowScanner) (*domain.Telemetry, error) {
	var t domain.Telemetry
	var recMs, rcvMs int64
	var hr, spo2, sys, dia, rr sql.NullInt64
	var ecg sql.NullString
	var stress sql.NullFloat64

	err := s.Scan(
		&t.ID,
		&t.AstronautID,
		&t.ClientID,
		&recMs,
		&rcvMs,
		&t.Source,
		&hr,
		&spo2,
		&sys,
		&dia,
		&rr,
		&ecg,
		&stress,
	)
	if err != nil {
		if err == sql.ErrNoRows {
			return nil, apperr.NotFound("scanTelemetry", "No telemetry record found.")
		}
		return nil, err
	}

	t.RecordedAt = time.UnixMilli(recMs).UTC()
	t.ReceivedAt = time.UnixMilli(rcvMs).UTC()

	if hr.Valid {
		v := int(hr.Int64)
		t.HeartRate = &v
	}
	if spo2.Valid {
		v := int(spo2.Int64)
		t.SpO2 = &v
	}
	if sys.Valid {
		v := int(sys.Int64)
		t.Systolic = &v
	}
	if dia.Valid {
		v := int(dia.Int64)
		t.Diastolic = &v
	}
	if rr.Valid {
		v := int(rr.Int64)
		t.RespRate = &v
	}
	if ecg.Valid {
		v := ecg.String
		t.ECGSummary = &v
	}
	if stress.Valid {
		v := stress.Float64
		t.StressIndex = &v
	}

	return &t, nil
}
