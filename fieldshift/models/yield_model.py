"""
Climate → yield model. SECONDARY DIAGNOSTIC: used for historical comparison and the what-if tab only;
it does not enter the rotation scores (the NASA daily water balance does).

Question: how strongly do summer heat and drought (NASA POWER / GPM IMERG)
reduce crop yields in this county (USDA NASS), and which crops suffer least?

Design
------
1. Target: yield as % of normal = yield / each crop's linear trend
   (removes the steady technology gain so only weather effects remain).
2. Summer crops (corn, soybean, sorghum) are pooled with crop indicators and
   crop × climate interactions, giving 40+ crop-years.
3. Models compared with leave-one-YEAR-out cross-validation. The yield TREND used to
   normalise yields is re-fitted inside every fold on the training years only, so a
   held-out year's yield never enters preprocessing or training (audit item 13).
   The Random Forest is the pre-specified model of record (not picked by CV score).
4. Per-crop sensitivities (Theil–Sen slope per 10 heat days / 100 mm deficit).
5. Scenarios: a 2012-like summer, and +ΔT / ±rain what-if used by the app.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import RidgeCV
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from scipy import stats

from .. import config as C

NASS_ITEMS = {"corn": "CORN, GRAIN", "soybean": "SOYBEANS", "sorghum": "SORGHUM, GRAIN", "wheat": "WHEAT, WINTER"}
SUMMER_CROPS = ["corn", "soybean", "sorghum"]
FEATURES = ["jja_heat_days", "gs_water_balance_mm", "ja_rain_mm", "ja_root_wetness"]
FEATURE_LABELS = {"jja_heat_days": "Jun–Aug heat-stress days (≥35 °C)",
                  "gs_water_balance_mm": "May–Sep water balance (rain − ET0)",
                  "ja_rain_mm": "Jul–Aug rain",
                  "ja_root_wetness": "Jul–Aug root-zone soil wetness"}
RF_PARAMS = dict(n_estimators=500, min_samples_leaf=3, random_state=0)


def climate_by_year() -> pd.DataFrame:
    m = pd.read_csv(C.OUT["power_monthly"])
    agg = lambda months, col, f: m[m.month.isin(months)].groupby("year")[col].agg(f)
    return pd.DataFrame({
        "jja_heat_days": agg([6, 7, 8], "heat_stress_days", "sum"),
        "jja_temp_c": agg([6, 7, 8], "temp_mean_c", "mean"),
        "gs_water_balance_mm": agg(C.GROWING_SEASON, "water_balance_mm", "sum"),
        "gs_rain_mm": agg(C.GROWING_SEASON, "rain_gpm_imerg_mm", "sum"),
        "gs_et0_mm": agg(C.GROWING_SEASON, "et0_hargreaves_mm", "sum"),
        "ja_rain_mm": agg([7, 8], "rain_gpm_imerg_mm", "sum"),
        "ja_root_wetness": agg([7, 8], "soil_wetness_root_0_1", "mean"),
    }).reset_index()


def build_dataset() -> tuple[pd.DataFrame, dict]:
    t = pd.read_csv(C.OUT["nass_tidy"])
    parts = []
    for crop, item in NASS_ITEMS.items():
        s = t[(t.crop_detail == item) & (t.metric == "yield") & (t.year >= C.PERIOD[0])][["year", "value"]].copy()
        s["crop"] = crop
        parts.append(s)
    d = pd.concat(parts).rename(columns={"value": "yield"}).merge(climate_by_year(), on="year")
    trend = {c: np.polyfit(g.year, g["yield"], 1) for c, g in d.groupby("crop")}
    d["trend_yield"] = [np.polyval(trend[c], y) for c, y in zip(d.crop, d.year)]
    d["yield_pct_of_normal"] = 100 * d["yield"] / d.trend_yield
    return d.sort_values(["crop", "year"]).reset_index(drop=True), trend


def design(d: pd.DataFrame) -> pd.DataFrame:
    X = d[FEATURES].copy()
    for c in SUMMER_CROPS[1:]:                       # corn is the reference crop
        X[f"is_{c}"] = (d.crop == c).astype(int)
        for f in ["jja_heat_days", "gs_water_balance_mm"]:
            X[f"{c}_x_{f}"] = X[f"is_{c}"] * X[f]
    return X


def models() -> dict:
    return {
        "Baseline (always 100% of normal)": None,
        "Ridge regression": make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 3, 30))),
        "Random Forest": RandomForestRegressor(**RF_PARAMS),       # random_state fixed (SEED)
    }


SEED = 0
MODEL_OF_RECORD = "Random Forest"


def fit_trends(train: pd.DataFrame) -> dict:
    """Linear yield trend per crop (bu/ac vs year) fitted ONLY on the rows given."""
    return {c: np.polyfit(g.year, g["yield"], 1) for c, g in train.groupby("crop")}


def normalise(df: pd.DataFrame, trends: dict) -> pd.DataFrame:
    out = df.copy()
    out["trend_yield"] = [np.polyval(trends[c], y) for c, y in zip(out.crop, out.year)]
    out["yield_pct_of_normal"] = 100 * out["yield"] / out.trend_yield
    return out


def fold_data(raw: pd.DataFrame, test_year: int):
    """Training rows (all other years) and test rows, both normalised with a trend fitted on training years only."""
    train, test = raw[raw.year != test_year], raw[raw.year == test_year]
    trends = fit_trends(train)
    return normalise(train, trends), normalise(test, trends), trends


def _metrics(obs, pred):
    obs, pred = np.asarray(obs, float), np.asarray(pred, float)
    return {"MAE_pct_points": round(float(mean_absolute_error(obs, pred)), 2),
            "R2": round(float(r2_score(obs, pred)), 3) if len(obs) > 2 else None, "n": int(len(obs))}


def _predict_fold(name, train, test):
    if name.startswith("Baseline"):
        return np.full(len(test), 100.0)
    mdl = models()[name]
    mdl.fit(design(train), train.yield_pct_of_normal)
    return mdl.predict(design(test))


def evaluate_loyo(raw: pd.DataFrame) -> pd.DataFrame:
    """Leakage-free leave-one-year-out: one row per held-out crop-year with every model's prediction."""
    s = raw[raw.crop.isin(SUMMER_CROPS)]
    rows = []
    for yr in sorted(s.year.unique()):
        train, test, trends = fold_data(s, yr)
        if test.empty:
            continue
        out = test[["year", "crop", "yield"] + FEATURES].copy()
        out["trend_yield_fold"] = test.trend_yield.values
        out["observed_pct_of_normal"] = test.yield_pct_of_normal.values
        for name in models():
            out[f"pred_{name}"] = _predict_fold(name, train, test)
        rows.append(out)
    return pd.concat(rows, ignore_index=True)


def evaluate_forward(raw: pd.DataFrame, first_test_year: int = 2015) -> pd.DataFrame:
    """Train only on earlier years (trend too), predict the next year — closest to real forecasting."""
    s = raw[raw.crop.isin(SUMMER_CROPS)]
    rows = []
    for yr in range(first_test_year, C.PERIOD[1] + 1):
        past, test = s[s.year < yr], s[s.year == yr]
        if test.empty or past.year.nunique() < 8:
            continue
        trends = fit_trends(past)
        tr, te = normalise(past, trends), normalise(test, trends)
        out = te[["year", "crop", "yield", "yield_pct_of_normal"]].rename(columns={"yield_pct_of_normal": "observed_pct_of_normal"})
        out[f"pred_{MODEL_OF_RECORD}"] = _predict_fold(MODEL_OF_RECORD, tr, te)
        out["pred_Baseline"] = 100.0
        rows.append(out)
    return pd.concat(rows, ignore_index=True)


def summarise_errors(p: pd.DataFrame) -> dict:
    obs = p.observed_pct_of_normal
    res = {"overall": {n: _metrics(obs, p[f"pred_{n}"]) for n in models()}}
    res["by_crop"] = {c: {n: _metrics(g.observed_pct_of_normal, g[f"pred_{n}"]) for n in models()}
                      for c, g in p.groupby("crop")}
    # bu/ac error for the model of record (trend from the fold × predicted %)
    pred_bu = p.trend_yield_fold * p[f"pred_{MODEL_OF_RECORD}"] / 100
    res["mae_bu_per_acre_by_crop"] = {c: round(float((pred_bu[g.index] - g["yield"]).abs().mean()), 1)
                                      for c, g in p.groupby("crop")}
    # climate severity: terciles of Jun–Aug heat days and of May–Sep water balance
    sev = {}
    for f, lab in [("jja_heat_days", ["fewest heat days", "middle", "most heat days"]),
                   ("gs_water_balance_mm", ["driest", "middle", "wettest"])]:
        q = pd.qcut(p[f].rank(method="first"), 3, labels=lab)
        sev[f] = {str(k): {"model": _metrics(g.observed_pct_of_normal, g[f"pred_{MODEL_OF_RECORD}"]),
                           "baseline": _metrics(g.observed_pct_of_normal, g["pred_Baseline (always 100% of normal)"]),
                           "mean_bias_pct_points": round(float((g[f"pred_{MODEL_OF_RECORD}"] - g.observed_pct_of_normal).mean()), 1)}
                  for k, g in p.groupby(q, observed=True)}
    res["by_climate_severity"] = sev
    for lab, m in [("poor_years_obs_below_85pct", obs < 85), ("good_years_obs_above_110pct", obs > 110)]:
        g = p[m]
        res[lab] = {"n": int(m.sum()),
                    "MAE_model": round(float((g[f"pred_{MODEL_OF_RECORD}"] - g.observed_pct_of_normal).abs().mean()), 1),
                    "mean_bias_model": round(float((g[f"pred_{MODEL_OF_RECORD}"] - g.observed_pct_of_normal).mean()), 1)}
    return res


def bootstrap_skill(p: pd.DataFrame, n_boot: int = 2000, seed: int = SEED) -> dict:
    """EXPLORATORY: resample whole years; spread of (baseline MAE − model MAE). Not a prediction interval."""
    rng = np.random.default_rng(seed)
    yrs = p.year.unique()
    e_m = (p[f"pred_{MODEL_OF_RECORD}"] - p.observed_pct_of_normal).abs()
    e_b = (p["pred_Baseline (always 100% of normal)"] - p.observed_pct_of_normal).abs()
    by_year = {y: np.where(p.year == y)[0] for y in yrs}
    gains = []
    for _ in range(n_boot):
        idx = np.concatenate([by_year[y] for y in rng.choice(yrs, len(yrs))])
        gains.append(e_b.iloc[idx].mean() - e_m.iloc[idx].mean())
    lo, med, hi = np.percentile(gains, [2.5, 50, 97.5])
    return {"mae_gain_vs_baseline_median": round(float(med), 2), "range_2p5_97p5": [round(float(lo), 2), round(float(hi), 2)],
            "share_of_resamples_with_gain": round(float(np.mean(np.array(gains) > 0)), 3),
            "n_years": int(len(yrs)), "note": "Year-bootstrap of held-out errors; exploratory spread of skill, "
            "NOT a calibrated prediction interval (~20 independent seasons)."}


def residual_spread(p: pd.DataFrame) -> dict:
    r = p.observed_pct_of_normal - p[f"pred_{MODEL_OF_RECORD}"]
    return {"held_out_residual_p10_p90_pct_points": [round(float(r.quantile(0.1)), 1), round(float(r.quantile(0.9)), 1)],
            "note": "Empirical spread of held-out errors; coverage for future years is not validated."}


def importance_of(final, X) -> dict | None:
    if not hasattr(final, "feature_importances_"):
        return None
    imp = pd.Series(final.feature_importances_, index=X.columns)
    return {FEATURE_LABELS.get(f, f): round(float(imp[[c for c in X.columns if f in c]].sum()), 3) for f in FEATURES}


def sensitivity(d: pd.DataFrame) -> dict:
    res = {}
    for crop, g in d.groupby("crop"):
        r = {"years_of_data": int(len(g))}
        for f, step, label in [("jja_heat_days", 10, "per_10_extra_heat_days"),
                               ("gs_water_balance_mm", -100, "per_100mm_more_deficit")]:
            ts = stats.theilslopes(g.yield_pct_of_normal, g[f])
            r[f"yield_change_pct_{label}"] = round(float(ts.slope * step), 1)
            r[f"correlation_{f}"] = round(float(np.corrcoef(g[f], g.yield_pct_of_normal)[0, 1]), 2)
        hot = g[g.jja_heat_days >= g.jja_heat_days.quantile(0.75)]
        r["avg_yield_pct_in_hottest_quarter_of_years"] = round(float(hot.yield_pct_of_normal.mean()), 1)
        r["worst_year"] = int(g.loc[g.yield_pct_of_normal.idxmin(), "year"])
        r["worst_year_pct_of_normal"] = round(float(g.yield_pct_of_normal.min()), 1)
        res[crop] = r
    return res


_FINAL: dict = {}


def fit_final_model():
    if "m" not in _FINAL:
        d, _ = build_dataset()
        s = d[d.crop.isin(SUMMER_CROPS)].reset_index(drop=True)
        _FINAL["m"] = RandomForestRegressor(**RF_PARAMS).fit(design(s), s.yield_pct_of_normal)
        _FINAL["clim"] = climate_by_year()
    return _FINAL["m"], _FINAL["clim"]


def _scenario_rows(model, base_row, new_row):
    rows = pd.DataFrame([base_row] * 3 + [new_row] * 3)
    rows["crop"] = SUMMER_CROPS * 2
    p = model.predict(design(rows))
    return {c: round(float(100 * (p[i + 3] / p[i] - 1)), 1) for i, c in enumerate(SUMMER_CROPS)}


def scenario_features(delta_temp_c: float = 0.0, rain_change_pct: float = 0.0):
    _, clim = fit_final_model()
    normal = clim[FEATURES].median()
    k = np.polyfit(clim.jja_temp_c, clim.jja_heat_days, 1)[0]           # observed heat days per °C
    gs_rain, gs_et0 = clim.gs_rain_mm.median(), clim.gs_et0_mm.median()
    x = normal.copy()
    x["jja_heat_days"] = max(0.0, normal.jja_heat_days + delta_temp_c * k)
    x["ja_rain_mm"] = normal.ja_rain_mm * (1 + rain_change_pct / 100)
    x["gs_water_balance_mm"] = gs_rain * (1 + rain_change_pct / 100) - gs_et0 * (1 + 0.05 * delta_temp_c)
    x["ja_root_wetness"] = float(np.clip(normal.ja_root_wetness * (1 + rain_change_pct / 300 - 0.02 * delta_temp_c), 0, 1))
    return normal, x, clim


def what_if(delta_temp_c: float = 0.0, rain_change_pct: float = 0.0) -> dict:
    """Yield change (% vs a normal summer) for warmer and/or drier summers.
    FULL-SAMPLE Random Forest estimate (in-sample): read the direction and rough size only."""
    model, _ = fit_final_model()
    normal, x, clim = scenario_features(delta_temp_c, rain_change_pct)
    out = _scenario_rows(model, normal, x)
    lo, hi = clim[FEATURES].min(), clim[FEATURES].max()
    outside = [FEATURE_LABELS[f] for f in FEATURES if x[f] < lo[f] or x[f] > hi[f]]
    warnings = ["Full-sample Random Forest estimate, not a validated forecast. Held-out tests show it "
                "under-predicts losses in extreme years (2012 held out: see reports/yield_model_results.json)."]
    if outside:
        warnings.append("Outside the 2005–2025 training range for: " + ", ".join(outside)
                        + ". A Random Forest cannot extrapolate: the true loss is probably larger.")
    out.update({"provenance": "rf_full_sample_estimate", "out_of_training_range": bool(outside), "warnings": warnings})
    return out


def heat_days_per_degree() -> float:
    _, clim = fit_final_model()
    return float(np.polyfit(clim.jja_temp_c, clim.jja_heat_days, 1)[0])


def run() -> dict:
    raw, full_trend = build_dataset()        # full-sample normalisation: descriptive statistics and final model only
    raw_cols = ["year", "crop", "yield"] + FEATURES
    loyo = evaluate_loyo(raw[raw_cols])
    fwd = evaluate_forward(raw[raw_cols])
    errors = summarise_errors(loyo)
    s = raw[raw.crop.isin(SUMMER_CROPS)].reset_index(drop=True)
    final = RandomForestRegressor(**RF_PARAMS).fit(design(s), s.yield_pct_of_normal)
    clim = climate_by_year()
    _FINAL["m"], _FINAL["clim"] = final, clim
    normal = clim[FEATURES].median()
    hot_dry = clim.set_index("year").loc[2012, FEATURES]

    # 2012: observed vs held-out vs full-sample (in-sample)
    obs12 = loyo[loyo.year == 2012].set_index("crop")
    full12 = _scenario_rows(final, normal, hot_dry)
    y2012 = {c: {"observed_pct_change_vs_trend": round(float(obs12.loc[c, "observed_pct_of_normal"] - 100), 1),
                 "held_out_rf_prediction_pct_change": round(float(obs12.loc[c, f"pred_{MODEL_OF_RECORD}"] - 100), 1),
                 "full_sample_rf_estimate_pct_change_vs_median_summer": full12[c]}
             for c in SUMMER_CROPS if c in obs12.index}
    fwd_m = {"model": _metrics(fwd.observed_pct_of_normal, fwd[f"pred_{MODEL_OF_RECORD}"]),
             "baseline": _metrics(fwd.observed_pct_of_normal, fwd.pred_Baseline)}
    comp = {n: {k: v for k, v in m.items() if k != "n"} for n, m in errors["overall"].items()}
    results = {
        "role": "Secondary diagnostic: historical comparison and what-if only; not used in rotation scores.",
        "target": "Yield as % of the crop's linear trend (USDA NASS, Riley County). In validation the trend is "
                  "re-fitted inside each fold on training years only.",
        "features": {k: FEATURE_LABELS[k] for k in FEATURES},
        "n_crop_years_summer_crops": int(len(loyo)),
        "n_independent_years": int(loyo.year.nunique()),
        "model_of_record": MODEL_OF_RECORD,
        "best_model": MODEL_OF_RECORD,          # kept for backward compatibility (pre-specified, not CV-selected)
        "random_seed": SEED,
        "validation": {"method": "leave-one-year-out, detrending inside each fold", **errors,
                       "forward_chaining_2015_2025": fwd_m,
                       "bootstrap_skill": bootstrap_skill(loyo), "residual_spread": residual_spread(loyo)},
        "model_comparison_leave_one_year_out": comp,
        "feature_importance": importance_of(final, design(s)),
        "year_2012": y2012,
        "crop_sensitivity": sensitivity(raw),
        "scenarios_yield_change_pct_vs_normal_summer": {
            "provenance": "rf_full_sample_estimate (in-sample; NOT validated forecasts)",
            "hot_dry_like_2012": full12,
            "plus_1C_summer": {k: v for k, v in what_if(1, 0).items() if k in SUMMER_CROPS},
            "plus_2C_summer": {k: v for k, v in what_if(2, 0).items() if k in SUMMER_CROPS},
            "plus_2C_and_20pct_less_rain": {k: v for k, v in what_if(2, -20).items() if k in SUMMER_CROPS},
        },
        "heat_days_per_degree_c": round(heat_days_per_degree(), 1),
        "trend_bu_per_acre_per_year_full_sample": {c: round(float(v[0]), 2) for c, v in full_trend.items()},
        "caveats": [
            f"About {int(loyo.year.nunique())} independent seasons; only one extreme drought (2012).",
            "Held-out predictions shrink toward normal: losses in bad years and gains in good years are under-predicted.",
            "County yields include irrigated fields, which hides heat damage; the model cannot rank crops' heat tolerance.",
            "Intervals here are exploratory (year bootstrap / empirical residuals), not calibrated prediction intervals.",
        ],
    }
    raw.to_csv(C.OUT["yield_dataset"], index=False)
    pred = loyo.rename(columns={"observed_pct_of_normal": "yield_pct_of_normal",
                                f"pred_{MODEL_OF_RECORD}": "predicted_pct_of_normal"})
    pred.to_csv(C.OUT["yield_predictions"], index=False)
    fwd.to_csv(C.OUT["yield_predictions"].with_name("16_yield_model_forward_predictions.csv"), index=False)
    C.OUT["yield_results"].write_text(json.dumps(results, indent=2))
    return results
