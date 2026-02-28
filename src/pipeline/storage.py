"""결과 저장 (JSON + SQLite)"""
import json
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

from config.settings import SCORES_DIR, DATA_DIR
from src.utils.logger import setup_logger

logger = setup_logger("storage")


class StorageManager:
    """JSON + SQLite 이중 저장"""

    def __init__(self, base_dir: str | Path | None = None):
        self.scores_dir = Path(base_dir or SCORES_DIR)
        self.scores_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = Path(base_dir or DATA_DIR) / "finance_simulator.db"

    # ── JSON 저장 ──

    def save_score(self, result: dict) -> str:
        """data/scores/score_{YYYY-MM-DD}.json 저장"""
        date_str = result.get("date", datetime.now().strftime("%Y-%m-%d"))
        path = self.scores_dir / f"score_{date_str}.json"

        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, default=str, ensure_ascii=False)

        logger.info(f"Score saved → {path}")
        return str(path)

    def save_optimization_result(self, result: dict) -> str:
        """data/scores/optimization_{YYYY-MM-DD}.json 저장"""
        date_str = datetime.now().strftime("%Y-%m-%d")
        path = self.scores_dir / f"optimization_{date_str}.json"

        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, default=str, ensure_ascii=False)

        logger.info(f"Optimization result saved → {path}")
        return str(path)

    def load_latest_weights(self) -> dict | None:
        """가장 최근 optimization 결과에서 weights 로드"""
        opt_files = sorted(self.scores_dir.glob("optimization_*.json"), reverse=True)
        if not opt_files:
            return None

        with open(opt_files[0], "r") as f:
            data = json.load(f)

        return data.get("weights")

    def load_latest_optimization(self) -> dict | None:
        """가장 최근 optimization 전체 결과 로드"""
        opt_files = sorted(self.scores_dir.glob("optimization_*.json"), reverse=True)
        if not opt_files:
            return None

        with open(opt_files[0], "r") as f:
            return json.load(f)

    # ── SQLite 저장 ──

    def init_db(self) -> None:
        """데이터베이스 테이블 생성"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                score REAL NOT NULL,
                signal TEXT NOT NULL,
                lag INTEGER,
                weights_json TEXT,
                correlation REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS variables (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                nl_level REAL,
                gm2_resid REAL,
                sofr_binary REAL,
                hy_level REAL,
                cme_basis REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS optimizations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                weights_json TEXT,
                lag INTEGER,
                correlation REAL,
                oos_mean_corr REAL,
                walk_forward_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()
        logger.info(f"Database initialized: {self.db_path}")

    def insert_score(self, result: dict) -> None:
        """Score 레코드 삽입 (NaN 방어)"""
        import math
        score = result.get("score", 0.0)
        if score is None or (isinstance(score, float) and math.isnan(score)):
            logger.warning("Score is NaN, defaulting to 0.0")
            score = 0.0

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO scores (date, score, signal, lag, weights_json, correlation) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                result.get("date", datetime.now().strftime("%Y-%m-%d")),
                score,
                result.get("signal", "NEUTRAL"),
                result.get("lag"),
                json.dumps(result.get("weights", {})),
                result.get("correlation"),
            ),
        )
        conn.commit()
        conn.close()

    def insert_variables(self, date: str, variables: dict) -> None:
        """변수 값 레코드 삽입"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO variables (date, nl_level, gm2_resid, sofr_binary, hy_level, cme_basis) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                date,
                variables.get("NL_level"),
                variables.get("GM2_resid"),
                variables.get("SOFR_binary"),
                variables.get("HY_level"),
                variables.get("CME_basis"),
            ),
        )
        conn.commit()
        conn.close()

    def get_score_history(self, n: int = 12) -> list[dict]:
        """최근 n개 Score 이력"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT date, score, signal, lag, correlation "
            "FROM scores ORDER BY date DESC LIMIT ?",
            (n,),
        )
        rows = cursor.fetchall()
        conn.close()

        return [
            {"date": r[0], "score": r[1], "signal": r[2], "lag": r[3], "corr": r[4]}
            for r in rows
        ]

    # ── CSV 저장 (processed 데이터) ──

    def save_processed(self, name: str, df: pd.DataFrame) -> str:
        """data/processed/{name}.csv 저장"""
        from config.settings import PROCESSED_DIR
        path = PROCESSED_DIR / f"{name}.csv"
        df.to_csv(path, index=False)
        return str(path)

    def load_processed(self, name: str) -> pd.DataFrame | None:
        """data/processed/{name}.csv 로드"""
        from config.settings import PROCESSED_DIR
        path = PROCESSED_DIR / f"{name}.csv"
        if not path.exists():
            return None
        return pd.read_csv(path, parse_dates=["date"])

    # ── v2.0 추가: Index/Validation 저장 ──

    def save_index(self, method: str, result: dict) -> str:
        """data/indices/{method}_{date}.json 저장"""
        from config.settings import INDICES_DIR
        date_str = datetime.now().strftime("%Y-%m-%d")
        path = Path(INDICES_DIR) / f"index_{method}_{date_str}.json"
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, default=str, ensure_ascii=False)

        logger.info(f"Index saved -> {path}")
        return str(path)

    def save_validation(self, result: dict) -> str:
        """data/validation/validation_{date}.json 저장"""
        from config.settings import VALIDATION_DIR
        date_str = datetime.now().strftime("%Y-%m-%d")
        path = Path(VALIDATION_DIR) / f"validation_{date_str}.json"
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, default=str, ensure_ascii=False)

        logger.info(f"Validation saved -> {path}")
        return str(path)
