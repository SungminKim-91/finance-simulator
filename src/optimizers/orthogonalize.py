"""변수 간 직교화 모듈"""
import numpy as np
import pandas as pd

from config.constants import ORTHO_CORR_THRESHOLD
from src.utils.logger import setup_logger

logger = setup_logger("orthogonalize")


def ols_residual(
    y: pd.Series,
    x: pd.Series,
) -> tuple[pd.Series, float, float]:
    """
    y = β*x + α + ε → return ε (잔차)

    Args:
        y: 종속 변수 (직교화 대상)
        x: 독립 변수 (보호 대상)
    Returns:
        (residual, beta, alpha)
    """
    valid = y.notna() & x.notna()
    y_clean = y[valid].values
    x_clean = x[valid].values

    X = np.column_stack([x_clean, np.ones(len(x_clean))])
    params, _, _, _ = np.linalg.lstsq(X, y_clean, rcond=None)
    beta, alpha = params[0], params[1]

    residual = y - (beta * x + alpha)
    return residual, float(beta), float(alpha)


def check_and_orthogonalize(
    variables: dict[str, pd.Series],
    threshold: float = ORTHO_CORR_THRESHOLD,
    protected: list[str] | None = None,
) -> tuple[dict[str, pd.Series], list[dict]]:
    """
    모든 변수 쌍의 상관 확인.
    |corr| > threshold인 쌍 → OLS residual로 직교화.

    Args:
        variables: {"NL_level": series, "GM2_level": series, ...}
        threshold: 직교화 기준 상관 계수
        protected: 직교화하지 않을 변수 목록 (default: ["NL_level"])
    Returns:
        - orthogonalized variables dict
        - log: [{"pair": ("GM2", "NL"), "corr_before": 0.53, ...}]

    직교화 우선순위:
    1. protected 변수는 절대 직교화하지 않음
    2. 다른 변수가 protected와 상관 높으면 → 해당 변수에서 protected 제거
    3. protected 외 변수끼리 상관 높으면 → 알파벳 순 후자를 직교화
    """
    if protected is None:
        protected = ["NL_level"]

    result = {k: v.copy() for k, v in variables.items()}
    logs = []
    names = list(variables.keys())

    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            name_i, name_j = names[i], names[j]
            s_i = result[name_i]
            s_j = result[name_j]

            # 공통 유효 인덱스
            valid = s_i.notna() & s_j.notna()
            if valid.sum() < 10:
                continue

            corr = float(np.corrcoef(
                s_i[valid].values, s_j[valid].values
            )[0, 1])

            if abs(corr) > threshold:
                # 누구를 직교화할지 결정
                if name_i in protected and name_j in protected:
                    logger.warning(
                        f"Both {name_i} and {name_j} are protected "
                        f"(corr={corr:.3f}). Skipping."
                    )
                    continue
                elif name_i in protected:
                    target, reference = name_j, name_i
                elif name_j in protected:
                    target, reference = name_i, name_j
                else:
                    # 둘 다 비보호 → 알파벳 순 후자를 직교화
                    target = max(name_i, name_j)
                    reference = min(name_i, name_j)

                # 직교화 수행
                residual, beta, alpha = ols_residual(
                    result[target], result[reference]
                )
                result[target] = residual

                # 검증
                valid2 = residual.notna() & result[reference].notna()
                corr_after = float(np.corrcoef(
                    residual[valid2].values,
                    result[reference][valid2].values,
                )[0, 1]) if valid2.sum() > 2 else 0.0

                log_entry = {
                    "pair": (target, reference),
                    "target": target,
                    "reference": reference,
                    "corr_before": round(corr, 4),
                    "corr_after": round(corr_after, 4),
                    "beta": round(beta, 4),
                    "alpha": round(alpha, 4),
                }
                logs.append(log_entry)

                logger.info(
                    f"Orthogonalized {target} vs {reference}: "
                    f"corr {corr:.3f} → {corr_after:.3f} "
                    f"(β={beta:.4f}, α={alpha:.4f})"
                )

    if not logs:
        logger.info("No orthogonalization needed (all |corr| < threshold)")

    return result, logs
