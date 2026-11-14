import argparse
import asyncio
import csv
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Ensure backend root is on PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.connection import Database
from app.db.telemetry import insert_telemetry_batch
from app.domain.models import Sample

COLUMN_MAP = {
    "hr": "heart_rate",
    "heart_rate": "heart_rate",
    "heartrate": "heart_rate",
    "spo2": "spo2",
    "o2": "spo2",
    "systolic": "systolic",
    "sys": "systolic",
    "diastolic": "diastolic",
    "dia": "diastolic",
    "resp_rate": "resp_rate",
    "respiration": "resp_rate",
    "rr": "resp_rate",
    "ecg": "ecg_summary",
    "stress": "stress_index",
}


async def main():
    parser = argparse.ArgumentParser(description="Import NASA Flight Crew Physiological dataset")
    parser.add_argument("--csv", required=True, help="Path to dataset CSV file")
    parser.add_argument("--astro", default="astro-a", help="Astronaut ID")
    parser.add_argument("--db", default="./data/astrovitals.db", help="SQLite database path")
    parser.add_argument("--jsonl", default="", help="Optional JSONL replay output file")
    parser.add_argument("--limit", type=int, default=1000, help="Max records to process")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"Error: CSV file not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    with open(csv_path, encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if not header:
            print("Error: empty CSV file", file=sys.stderr)
            sys.exit(1)

        idx_map: dict[str, int] = {}
        for i, col in enumerate(header):
            cleaned = col.strip().lower()
            if cleaned in COLUMN_MAP:
                idx_map[COLUMN_MAP[cleaned]] = i

        jsonl_f = open(args.jsonl, "w", encoding="utf-8") if args.jsonl else None
        db = Database(args.db) if not jsonl_f else None
        if db:
            await db.open()

        count = 0
        samples_batch: list[Sample] = []
        base_time = datetime.now(UTC) - timedelta(seconds=args.limit)

        try:
            for row in reader:
                if not row:
                    continue
                count += 1
                if args.limit > 0 and count > args.limit:
                    break

                rec_time = base_time + timedelta(seconds=count)
                client_id = f"dataset-{count}"

                def get_int(field: str) -> int | None:
                    if field in idx_map and idx_map[field] < len(row):
                        try:
                            return int(float(row[idx_map[field]]))
                        except ValueError:
                            return None
                    return None

                def get_float(field: str) -> float | None:
                    if field in idx_map and idx_map[field] < len(row):
                        try:
                            return float(row[idx_map[field]])
                        except ValueError:
                            return None
                    return None

                sample = Sample(
                    astronaut_id=args.astro,
                    client_id=client_id,
                    recorded_at=rec_time,
                    source="dataset",
                    heart_rate=get_int("heart_rate"),
                    spo2=get_int("spo2"),
                    systolic=get_int("systolic"),
                    diastolic=get_int("diastolic"),
                    resp_rate=get_int("resp_rate"),
                    ecg_summary="sinus",
                    stress_index=get_float("stress_index") or 0.2,
                )

                if jsonl_f:
                    data = {
                        "astronaut_id": sample.astronaut_id,
                        "client_id": sample.client_id,
                        "recorded_at": sample.recorded_at.isoformat(),
                        "source": sample.source,
                        "heart_rate": sample.heart_rate,
                        "spo2": sample.spo2,
                        "systolic": sample.systolic,
                        "diastolic": sample.diastolic,
                        "resp_rate": sample.resp_rate,
                        "ecg_summary": sample.ecg_summary,
                        "stress_index": sample.stress_index,
                    }
                    jsonl_f.write(json.dumps(data) + "\n")
                elif db:
                    samples_batch.append(sample)
                    if len(samples_batch) >= 100:
                        async with db.write_tx() as conn:
                            await insert_telemetry_batch(conn, args.astro, samples_batch)
                        samples_batch.clear()

            if db and samples_batch:
                async with db.write_tx() as conn:
                    await insert_telemetry_batch(conn, args.astro, samples_batch)

            print(f"Processed {count} rows successfully.")
        finally:
            if jsonl_f:
                jsonl_f.close()
            if db:
                await db.close()


if __name__ == "__main__":
    asyncio.run(main())
