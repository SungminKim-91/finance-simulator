#!/usr/bin/env python3
"""Export v2.0 pipeline results to web/src/data_v2.js for React dashboard."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
WEB_SRC = ROOT / "web" / "src"


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_dual_band(z: pd.DataFrame):
    """Build structural (full 4-var PCA) and tactical (-HY) bands.

    Structural: PCA(NL, GM2, HY, CME) with Option H clip → full liquidity index
    Tactical:   -HY_z normalized → fast credit risk overlay (realtime)

    Model D: base = 4-var PCA (r=0.49, MDA=64.7%) shifted by lag
             tactical = -HY at realtime for gap-fill
    """
    struct_cols = ["NL_level", "GM2_resid", "HY_level", "CME_basis"]
    mask = z[struct_cols].notna().all(axis=1)

    # Option H variable-specific clip (same as runner_v2)
    clip_map = {"NL_level": 3.0, "GM2_resid": 2.0, "HY_level": 2.5, "CME_basis": 2.0}
    Xclip = z.loc[mask, struct_cols].copy()
    for col, val in clip_map.items():
        Xclip[col] = Xclip[col].clip(-val, val)

    pca = PCA(n_components=1, random_state=42)
    struct_raw = pca.fit_transform(Xclip.values).flatten()

    # Sign correction: enforce positive corr with BTC
    btc_vals = z.loc[mask, "log_btc"].values
    if np.corrcoef(struct_raw, btc_vals)[0, 1] < 0:
        struct_raw = -struct_raw

    struct_norm = (struct_raw - struct_raw.mean()) / struct_raw.std()

    # Tactical: -HY (inverted HY spread = risk-on signal)
    hy_vals = z.loc[mask, "HY_level"].values
    tact_raw = -hy_vals
    tact_norm = (tact_raw - tact_raw.mean()) / tact_raw.std()

    # Map back to full index
    structural = pd.Series(np.nan, index=z.index)
    tactical = pd.Series(np.nan, index=z.index)
    structural.loc[mask] = struct_norm
    tactical.loc[mask] = tact_norm

    return structural, tactical


def build_index_data():
    """Merge PCA index + dual-band with z_matrix dates and log_btc."""
    z = pd.read_csv(DATA_DIR / "processed" / "z_matrix.csv")
    idx_json = load_json(DATA_DIR / "indices" / "index_pca_2026-03-01.json")

    index_values = idx_json["index"]
    n_obs = idx_json["n_observations"]

    # Index starts from the end of z_matrix (where all variables have data)
    start_row = len(z) - n_obs

    # Compute dual-band indices
    structural, tactical = build_dual_band(z)

    records = []
    for i, row in z.iterrows():
        rec = {
            "date": row["date"],
            "log_btc": round(row["log_btc"], 4) if pd.notna(row["log_btc"]) else None,
        }
        idx_pos = i - start_row
        if 0 <= idx_pos < len(index_values):
            rec["pca_index"] = round(index_values[idx_pos], 4)
        else:
            rec["pca_index"] = None

        # Dual-band indices
        rec["structural"] = round(structural.iloc[i], 4) if pd.notna(structural.iloc[i]) else None
        rec["tactical"] = round(tactical.iloc[i], 4) if pd.notna(tactical.iloc[i]) else None

        # Include z-scored variables
        for col in ["NL_level", "GM2_resid", "HY_level", "CME_basis"]:
            if col in row and pd.notna(row[col]):
                rec[col] = round(row[col], 4)
            else:
                rec[col] = None

        records.append(rec)

    return records


def build_methods():
    """Build method comparison data from compare output."""
    # We need to re-run compare or parse its output
    # For now, parse from the pipeline results
    idx_json = load_json(DATA_DIR / "indices" / "index_pca_2026-03-01.json")
    s2_json = load_json(DATA_DIR / "validation" / "stage2_validation_2026-03-01.json")

    methods = [
        {
            "method": "PCA",
            "loadings": idx_json["loadings"],
            "explained_variance": round(idx_json["explained_variance"], 4),
            "optimal_lag": s2_json["optimal_lag"],
            "best_cws": round(s2_json["best_cws"], 4),
        }
    ]
    return methods


def build_xcorr_v2(s2_json: dict):
    """CWS profile with all sub-metrics."""
    return [
        {
            "lag": p["lag"],
            "pearson_r": round(p.get("pearson_r", 0), 4),
            "mda": round(p.get("mda", 0), 4),
            "sbd": round(p.get("sbd", 0), 4),
            "cosine_sim": round(p.get("cosine_sim", 0), 4),
            "kendall_tau": round(p.get("kendall_tau", 0), 4),
        }
        for p in s2_json.get("xcorr_profile", [])
    ]


def build_cws_profile(s2_json: dict):
    """CWS composite score by lag."""
    return [
        {
            "lag": p["lag"],
            "cws": round(p["cws"], 4),
            "mda_contrib": round(p["mda"] * 0.4, 4),
            "sbd_contrib": round((1 - p["sbd"]) * 0.3, 4),
            "cos_contrib": round(p["cosine_sim"] * 0.2, 4),
            "tau_contrib": round(p["kendall_tau"] * 0.1, 4),
        }
        for p in s2_json.get("cws_profile", [])
    ]


def build_bootstrap(s3_json: dict):
    """Bootstrap loading stability."""
    bl = s3_json.get("bootstrap_loadings", {})
    variables = list(bl.get("mean_loadings", {}).keys())

    loading_data = []
    for var in variables:
        loading_data.append({
            "variable": var,
            "mean": round(bl["mean_loadings"][var], 4),
            "ci_lower": round(bl["ci_lower"][var], 4),
            "ci_upper": round(bl["ci_upper"][var], 4),
            "excludes_zero": bl["ci_excludes_zero"].get(var, False),
        })

    lags = s3_json.get("bootstrap_lags", {})

    return {
        "loadings": loading_data,
        "nl_always_max": bl.get("nl_always_max", False),
        "nl_max_rate": round(bl.get("nl_max_rate", 0), 4),
        "n_valid": bl.get("n_valid", 0),
        "lag_distribution": {
            "mean": round(lags.get("mean_lag", 0), 2),
            "median": round(lags.get("median_lag", 0), 1),
            "mode": lags.get("mode_lag", 0),
            "ci_lower": lags.get("ci_lower", 0),
            "ci_upper": lags.get("ci_upper", 0),
            "n_samples": lags.get("n_samples", 0),
        },
    }


def build_cpcv(s3_json: dict):
    """CPCV validation results."""
    cpcv = s3_json.get("cpcv", {})
    if "error" in cpcv:
        return {"error": cpcv["error"]}

    return {
        "n_paths": cpcv.get("n_paths", 0),
        "cws_mean": round(cpcv.get("cws_mean", 0), 4),
        "cws_std": round(cpcv.get("cws_std", 0), 4),
        "mda_mean": round(cpcv.get("mda_mean", 0), 4),
        "all_positive_rate": round(cpcv.get("all_positive_rate", 0), 4),
        "pearson_r_mean": round(cpcv.get("pearson_r_mean", 0), 4),
        "worst_path": cpcv.get("worst_path", {}),
        "best_path": cpcv.get("best_path", {}),
        "cws_all": [round(c, 4) for c in cpcv.get("cws_all", [])],
    }


def build_success(s2_json: dict, s3_json: dict):
    """Success criteria check."""
    cws_profile = s2_json.get("cws_profile", [])
    optimal = max(cws_profile, key=lambda x: x["cws"]) if cws_profile else {}

    return {
        "min_mda": {
            "target": 0.6,
            "actual": round(optimal.get("mda", 0), 4),
            "pass": optimal.get("mda", 0) >= 0.6,
        },
        "all_lag_positive": {
            "target": True,
            "actual": s2_json.get("all_positive", False),
            "pass": s2_json.get("all_positive", False),
        },
        "bootstrap_ci": {
            "target": True,
            "actual": s3_json.get("bootstrap_loadings", {}).get("nl_always_max", False),
            "pass": s3_json.get("bootstrap_loadings", {}).get("nl_always_max", False),
        },
        "granger_unidirectional": {
            "target": True,
            "actual": s2_json.get("granger", {}).get("unidirectional", False),
            "pass": str(s2_json.get("granger", {}).get("unidirectional", False)).lower() == "true",
        },
        "cpcv_mean": {
            "target": 0.15,
            "actual": round(s3_json.get("cpcv", {}).get("cws_mean", 0), 4),
            "pass": s3_json.get("cpcv", {}).get("cws_mean", 0) >= 0.15,
        },
    }


def build_meta(idx_json: dict, s2_json: dict):
    """Meta information."""
    return {
        "method": idx_json.get("method", "PCA"),
        "n_observations": idx_json.get("n_observations", 0),
        "explained_variance": round(idx_json.get("explained_variance", 0), 4),
        "optimal_lag": s2_json.get("optimal_lag", 0),
        "best_cws": round(s2_json.get("best_cws", 0), 4),
        "all_positive": s2_json.get("all_positive", False),
        "loadings": {k: round(v, 4) for k, v in idx_json.get("loadings", {}).items()},
        "granger": s2_json.get("granger", {}),
    }


def to_js_export(name: str, data) -> str:
    """Convert Python data to JS export string."""
    json_str = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"export const {name} = {json_str};\n"


def main():
    print("Loading pipeline results...")

    idx_json = load_json(DATA_DIR / "indices" / "index_pca_2026-03-01.json")
    s2_json = load_json(DATA_DIR / "validation" / "stage2_validation_2026-03-01.json")
    s3_json = load_json(DATA_DIR / "validation" / "stage3_robustness_2026-03-01.json")

    print("Building web data...")

    index_data = build_index_data()
    methods = build_methods()
    xcorr_v2 = build_xcorr_v2(s2_json)
    cws_profile = build_cws_profile(s2_json)
    bootstrap = build_bootstrap(s3_json)
    cpcv = build_cpcv(s3_json)
    success = build_success(s2_json, s3_json)
    meta = build_meta(idx_json, s2_json)

    # Write to JS file
    out_path = WEB_SRC / "data_v2.js"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("// Auto-generated from v2.0 pipeline results — BTC Liquidity Model v2.0.0\n")
        f.write(to_js_export("INDEX_DATA", index_data))
        f.write(to_js_export("METHODS", methods))
        f.write(to_js_export("XCORR_V2", xcorr_v2))
        f.write(to_js_export("CWS_PROFILE", cws_profile))
        f.write(to_js_export("BOOTSTRAP", bootstrap))
        f.write(to_js_export("CPCV", cpcv))
        f.write(to_js_export("SUCCESS", success))
        f.write(to_js_export("META_V2", meta))

    print(f"Written to {out_path}")
    print(f"  INDEX_DATA: {len(index_data)} records")
    print(f"  XCORR_V2: {len(xcorr_v2)} lags")
    print(f"  CWS_PROFILE: {len(cws_profile)} lags")
    print(f"  BOOTSTRAP: {len(bootstrap['loadings'])} variables")
    print(f"  CPCV: {cpcv.get('n_paths', 0)} paths")
    print(f"  META_V2: method={meta['method']}, lag={meta['optimal_lag']}, cws={meta['best_cws']}")


if __name__ == "__main__":
    main()
