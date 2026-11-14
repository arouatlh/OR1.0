package store

import (
	"context"
	"database/sql"
	"embed"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"astrovitals/internal/apperr"

	_ "modernc.org/sqlite"
)

//go:embed migrations/*.sql
var migrationsFS embed.FS

type DB struct {
	SQL *sql.DB
}

// Open creates/connects to a SQLite database, configures pragmas, runs migrations, and seeds default data.
func Open(ctx context.Context, dbPath string) (*DB, error) {
	const op = "store.db.open"

	if dbPath != ":memory:" && !strings.Contains(dbPath, "mode=memory") {
		dir := filepath.Dir(dbPath)
		if dir != "" && dir != "." {
			if err := os.MkdirAll(dir, 0755); err != nil {
				return nil, apperr.Internal(op, fmt.Errorf("failed to create db directory: %w", err))
			}
		}
	}

	dsn := dbPath
	if !strings.Contains(dsn, "?") {
		dsn += "?_pragma=busy_timeout(5000)&_pragma=journal_mode(WAL)&_pragma=synchronous(NORMAL)&_pragma=foreign_keys(ON)&_pragma=temp_store(MEMORY)"
	}

	db, err := sql.Open("sqlite", dsn)
	if err != nil {
		return nil, apperr.Internal(op, err)
	}

	db.SetMaxOpenConns(1) // Single writer model for reliability and zero SQLITE_BUSY lock races
	db.SetMaxIdleConns(1)
	db.SetConnMaxLifetime(0)

	// Execute pragmas directly to ensure they are active
	pragmas := []string{
		"PRAGMA journal_mode=WAL;",
		"PRAGMA synchronous=NORMAL;",
		"PRAGMA foreign_keys=ON;",
		"PRAGMA busy_timeout=5000;",
		"PRAGMA temp_store=MEMORY;",
	}
	for _, pragma := range pragmas {
		if _, err := db.ExecContext(ctx, pragma); err != nil {
			db.Close()
			return nil, apperr.Internal(op, fmt.Errorf("pragma error %s: %w", pragma, err))
		}
	}

	sdb := &DB{SQL: db}
	if err := sdb.migrate(ctx); err != nil {
		db.Close()
		return nil, apperr.Internal("store.db.migrate", err)
	}

	if err := sdb.seedAstronauts(ctx); err != nil {
		db.Close()
		return nil, apperr.Internal("store.db.seed", err)
	}

	return sdb, nil
}

func (db *DB) Close() error {
	return db.SQL.Close()
}

func (db *DB) Ping(ctx context.Context) error {
	const op = "store.db.ping"
	if err := db.SQL.PingContext(ctx); err != nil {
		return translateDBError(op, err)
	}
	return nil
}

func (db *DB) migrate(ctx context.Context) error {
	entries, err := migrationsFS.ReadDir("migrations")
	if err != nil {
		return err
	}

	var files []string
	for _, e := range entries {
		if !e.IsDir() && strings.HasSuffix(e.Name(), ".sql") {
			files = append(files, e.Name())
		}
	}
	sort.Strings(files)

	// Ensure schema_migrations table exists
	_, err = db.SQL.ExecContext(ctx, `
		CREATE TABLE IF NOT EXISTS schema_migrations (
			version TEXT PRIMARY KEY,
			applied_at INTEGER NOT NULL
		);
	`)
	if err != nil {
		return err
	}

	for _, file := range files {
		var exists int
		err := db.SQL.QueryRowContext(ctx, `SELECT COUNT(1) FROM schema_migrations WHERE version = ?`, file).Scan(&exists)
		if err != nil {
			return err
		}
		if exists > 0 {
			continue
		}

		content, err := migrationsFS.ReadFile("migrations/" + file)
		if err != nil {
			return err
		}

		tx, err := db.SQL.BeginTx(ctx, nil)
		if err != nil {
			return err
		}

		if _, err := tx.ExecContext(ctx, string(content)); err != nil {
			tx.Rollback()
			return fmt.Errorf("migration %s failed: %w", file, err)
		}

		nowMs := time.Now().UTC().UnixMilli()
		if _, err := tx.ExecContext(ctx, `INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)`, file, nowMs); err != nil {
			tx.Rollback()
			return err
		}

		if err := tx.Commit(); err != nil {
			return err
		}
	}

	return nil
}

func (db *DB) seedAstronauts(ctx context.Context) error {
	var count int
	err := db.SQL.QueryRowContext(ctx, `SELECT COUNT(1) FROM astronauts`).Scan(&count)
	if err != nil {
		return err
	}
	if count > 0 {
		return nil
	}

	nowMs := time.Now().UTC().UnixMilli()
	astronauts := []struct {
		id          string
		displayName string
		mission     string
		mode        string
		baselineHR  int
	}{
		{"astro-a", "Dr. Alex Rivera", "EVA-01", "normal", 70},
		{"astro-b", "Capt. Samantha Vance", "EVA-02", "normal", 68},
		{"astro-c", "Lt. David Chen", "EVA-03", "normal", 72},
	}

	tx, err := db.SQL.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer tx.Rollback()

	stmt, err := tx.PrepareContext(ctx, `
		INSERT INTO astronauts (id, display_name, mission, mode, baseline_hr, created_at)
		VALUES (?, ?, ?, ?, ?, ?)
	`)
	if err != nil {
		return err
	}
	defer stmt.Close()

	for _, a := range astronauts {
		if _, err := stmt.ExecContext(ctx, a.id, a.displayName, a.mission, a.mode, a.baselineHR, nowMs); err != nil {
			return err
		}
	}

	return tx.Commit()
}

// translateDBError maps standard and SQLite driver errors to opaque apperr.Error
func translateDBError(op string, err error) error {
	if err == nil {
		return nil
	}
	if err == sql.ErrNoRows {
		return apperr.NotFound(op, "Record not found.")
	}
	msg := err.Error()
	if strings.Contains(msg, "locked") || strings.Contains(msg, "busy") || strings.Contains(msg, "SQLITE_BUSY") {
		return apperr.Unavailable(op, err)
	}
	if strings.Contains(msg, "UNIQUE constraint failed") {
		return apperr.Conflict(op, "Unique constraint violation.", err)
	}
	return apperr.Internal(op, err)
}
