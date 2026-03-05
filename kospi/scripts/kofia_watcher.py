#!/usr/bin/env python3
"""
KOFIA 엑셀 폴더 모니터링 데몬 — kofia_excel/ 감시 → 자동 파싱 + timeseries 머지.

감시 폴더: kospi/data/kofia_excel/
처리 흐름:
  1. .xlsx 파일 감지 → parse_kofia_excel()
  2. timeseries.json 머지 (None 필드만 채움)
  3. 처리 완료 파일 → kofia_excel_archive/ 이동

Usage:
    python -m scripts.kofia_watcher              # 폴더 감시 (foreground)
    python -m scripts.kofia_watcher --once file.xlsx  # 단발 처리
"""
import argparse
import json
import shutil
import time
from datetime import datetime
from pathlib import Path

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    Observer = None
    FileSystemEventHandler = object

from scripts.kofia_excel_parser import parse_kofia_excel

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
INBOX_DIR = DATA_DIR / "kofia_excel"
PROCESSED_DIR = DATA_DIR / "kofia_excel_archive"
TS_PATH = DATA_DIR / "timeseries.json"


def merge_to_timeseries(parsed: dict[str, dict], force: bool = False) -> int:
    """파싱 결과를 timeseries.json에 머지.

    - force=False: None인 필드만 채움 (기존 API 데이터 보존)
    - force=True: 모든 필드 덮어씀
    Returns: 업데이트된 필드 수
    """
    if not parsed:
        return 0

    if TS_PATH.exists():
        with open(TS_PATH, "r", encoding="utf-8") as f:
            ts = json.load(f)
    else:
        ts = []

    ts_map = {r["date"]: r for r in ts}
    updated = 0

    for date, fields in parsed.items():
        if date in ts_map:
            rec = ts_map[date]
            for k, v in fields.items():
                if force or rec.get(k) is None:
                    rec[k] = v
                    updated += 1
        else:
            rec = {"date": date, **fields}
            ts.append(rec)
            ts_map[date] = rec
            updated += len(fields)

    ts.sort(key=lambda r: r["date"])
    with open(TS_PATH, "w", encoding="utf-8") as f:
        json.dump(ts, f, ensure_ascii=False, indent=2, default=str)

    return updated


def process_file(path: Path, move: bool = True) -> bool:
    """단일 엑셀 파일 처리: 파싱 → 머지 → (이동)."""
    print(f"\n{'='*50}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 처리: {path.name}")
    print(f"{'='*50}")

    try:
        parsed = parse_kofia_excel(path)
    except Exception as e:
        print(f"  [ERROR] 파싱 실패: {e}")
        return False

    if not parsed:
        print("  [WARN] 매칭 데이터 없음")
        return False

    updated = merge_to_timeseries(parsed)
    print(f"  [MERGE] {updated}개 필드 업데이트")

    for date, fields in sorted(parsed.items()):
        field_str = ", ".join(f"{k}={v}" for k, v in fields.items())
        print(f"    {date}: {field_str}")

    if move:
        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        dest = PROCESSED_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{path.name}"
        shutil.move(str(path), str(dest))
        print(f"  [MOVE] → {dest.name}")

    return True


class ExcelHandler(FileSystemEventHandler):
    """kofia_excel/ 폴더의 .xlsx 파일 생성 감지."""

    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() == ".xlsx" and not path.name.startswith("~$"):
            # 파일 쓰기 완료 대기
            time.sleep(1)
            process_file(path)


def watch():
    """kofia_excel/ 폴더 감시 시작."""
    if Observer is None:
        print("[ERROR] watchdog 필요: pip install watchdog")
        print("  대안: python -m scripts.kofia_watcher --once <file.xlsx>")
        return

    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[WATCHER] 감시 시작: {INBOX_DIR}")
    print(f"  .xlsx 파일을 kofia_excel/에 복사하면 자동 처리됩니다.")
    print(f"  Ctrl+C로 종료\n")

    handler = ExcelHandler()
    observer = Observer()
    observer.schedule(handler, str(INBOX_DIR), recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\n[WATCHER] 종료")
    observer.join()


def main():
    parser = argparse.ArgumentParser(description="KOFIA 엑셀 폴더 모니터링")
    parser.add_argument("--once", type=str, metavar="FILE",
                        help="단발 처리 (폴더 감시 없이)")
    args = parser.parse_args()

    if args.once:
        path = Path(args.once)
        process_file(path, move=False)
    else:
        watch()


if __name__ == "__main__":
    main()
