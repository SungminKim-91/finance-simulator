#!/usr/bin/env python3
"""
KOFIA FreeSIS 엑셀 자동 다운로드 — Playwright headless 브라우저.

"한눈에 보는 자본시장통계" 페이지에서 EXCEL 다운로드 → kofia_excel/ 저장.
다운로드 후 --auto 옵션 시 fetch_daily --import-excel 자동 실행.

Usage:
    python -m scripts.kofia_downloader              # 다운로드만
    python -m scripts.kofia_downloader --auto       # 다운로드 + import + export_web
    python -m scripts.kofia_downloader --headful    # 브라우저 표시 (디버깅)
"""
import argparse
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

FREESIS_URL = "https://freesis.kofia.or.kr/stat/FreeSIS.do?parentDivId=MSIS10000000000000&serviceId=STATSCU0100000070"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOWNLOAD_DIR = PROJECT_ROOT / "data" / "kofia_excel"
ARCHIVE_DIR = PROJECT_ROOT / "data" / "kofia_excel_archive"
TIMEOUT_MS = 30_000


def download_excel(headless: bool = True) -> Path | None:
    """Playwright로 FreeSIS 접속 → 한눈에 보는 자본시장통계 EXCEL 다운로드."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[ERROR] playwright 필요: uv pip install playwright && python -m playwright install chromium")
        return None

    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        print(f"[1/4] FreeSIS 접속 중...")
        page.goto(FREESIS_URL, wait_until="networkidle", timeout=TIMEOUT_MS)

        # 좌측 메뉴에서 "한눈에 보는 자본시장통계" 클릭
        print(f"[2/4] '한눈에 보는 자본시장통계' 메뉴 클릭...")
        menu_item = page.get_by_role("treeitem", name="한눈에 보는 자본시장통계", exact=True).first
        menu_item.click()
        page.wait_for_timeout(3000)  # SPA 콘텐츠 로드 대기

        # EXCEL저장 버튼 클릭 + 다운로드 대기
        print(f"[3/4] EXCEL 다운로드 중...")
        with page.expect_download(timeout=TIMEOUT_MS) as download_info:
            page.get_by_role("button", name="EXCEL저장").click()
        download = download_info.value

        # 파일명: 한눈에_보는_자본시장통계_YYYYMMDD.xlsx
        today = datetime.now().strftime("%Y%m%d")
        filename = f"한눈에_보는_자본시장통계_{today}.xlsx"
        save_path = DOWNLOAD_DIR / filename
        download.save_as(str(save_path))

        print(f"[4/4] 저장 완료: {save_path}")
        browser.close()
        return save_path


def archive_file(excel_path: Path):
    """처리 완료 엑셀을 archive 폴더로 이동."""
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = ARCHIVE_DIR / f"{ts}_{excel_path.name}"
    shutil.move(str(excel_path), str(dest))
    print(f"[ARCHIVE] {excel_path.name} → {dest.name}")


def auto_import(excel_path: Path):
    """fetch_daily --import-excel 호출로 파싱 + timeseries 머지 + export_web + archive."""
    print(f"\n[AUTO] import-excel 실행: {excel_path.name}")
    result = subprocess.run(
        [sys.executable, "-m", "scripts.fetch_daily", "--import-excel", str(excel_path)],
        cwd=str(PROJECT_ROOT),
        capture_output=True, text=True,
    )
    if result.stdout:
        print(result.stdout)
    if result.returncode != 0:
        print(f"[ERROR] import-excel 실패:\n{result.stderr}")
        return
    print("[AUTO] 완료: timeseries + web export 갱신됨")
    archive_file(excel_path)


def main():
    parser = argparse.ArgumentParser(description="KOFIA FreeSIS 엑셀 자동 다운로드")
    parser.add_argument("--auto", action="store_true", help="다운로드 후 자동 import + export_web")
    parser.add_argument("--headful", action="store_true", help="브라우저 화면 표시 (디버깅)")
    args = parser.parse_args()

    excel_path = download_excel(headless=not args.headful)
    if excel_path is None:
        sys.exit(1)

    if args.auto:
        auto_import(excel_path)


if __name__ == "__main__":
    main()
