#!/usr/bin/env python3
"""
Nature-Mirror Mesh -- Propagation Oracle: PREDICTION step.

Runs BEFORE any recording is made and must never look at a recording.
It fetches live solar data from NOAA SWPC (free JSON), probes for a real
ITU-R P.533 propagation model, applies whichever model is honestly
available, and writes a falsifiable prediction to:

  lab/results/oracle_prediction.json        (machine readable)
  lab/results/oracle_prediction_header.txt  (human readable; the scorer
                                             places it verbatim at the
                                             top of oracle_ci.log)

Prediction, per receiver site x band (20 m = 14074 kHz, 40 m = 7074 kHz):
expected unique FT8 decodes in a 90 s recording, in categories
  many (>=10), few (1-9), none (0)
plus a per-site predicted_best_band.

MODEL SELECTION (honesty is part of the deliverable):
  1. Probe `import itur.models.itu533` (ITU-R P.533 HF model).
     Verified 2026-10-20: PyPI `itur` 0.4.0 installs cleanly, but its
     models package ships itu453/530/618/676/835/836/837/838/839/840/
     1144/1510/1511/1623/1853 -- there is NO itu533 module, so P.533 is
     NOT usable from itur 0.4.0. The probe result is recorded verbatim
     in the prediction file either way.
  2. If the probe fails, fall back to "heuristic v1" (below) and the
     prediction file says so in its "model" field.

HEURISTIC v1 (transparent toy model, all constants stated here and in the
prediction JSON):
  * Sample points: the receiver site plus points 1500 km away at bearings
    0/90/180/270 deg (proxy FT8 path midpoints).
  * Solar elevation at each sample from date/UTC (declination from day of
    year; subsolar longitude from UTC hour; equation of time ignored).
  * foF2_day  = 3.0 + 0.062 * F10.7            (noon-ish asymptote)
    foF2_night = 4.2 MHz
    blended by a smoothstep of solar elevation over [-10 deg, +8 deg].
  * MUF_proxy = 3.1 * foF2 (single-hop obliquity factor, ~1500 km hop).
  * Band support at a sample is a logistic in (MUF - band frequency):
      s = 1 / (1 + exp(-(MUF - f) / 1.2))          for 20 m
      s = 1 / (1 + exp(-(MUF - f) / 1.0))          for 40 m
    and 40 m is multiplied by a D-layer absorption factor
      1.0 at night, down to ~0.25 at local noon (absorption ~ 1/f^2 is
      exactly why 40 m dies at midday while 20 m thrives).
  * Site+band score = mean support over the 5 samples.
    Categories: score >= 0.55 -> "many", >= 0.25 -> "few", else "none".
  * If forecast Ap >= 30 all scores are multiplied by 0.75 and the run
    is flagged geomagnetically disturbed.

$0, receive-only. This script transmits nothing; it only reads NOAA.
"""

import json
import math
import os
import sys
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(HERE, "results")
PRED_JSON = os.path.join(RESULTS_DIR, "oracle_prediction.json")
PRED_HEADER = os.path.join(RESULTS_DIR, "oracle_prediction_header.txt")

NOAA_45DAY = "https://services.swpc.noaa.gov/json/45-day-forecast.json"
NOAA_OBSERVED = ("https://services.swpc.noaa.gov/json/solar-cycle/"
                 "observed-solar-cycle-indices.json")

SITES = [
    {"site": "ireland", "host": "emeraldsdr.ddns.net:8073",
     "label": "Carlow, Ireland (Europe)", "lat": 52.84, "lon": -6.93},
    {"site": "australia", "host": "22537.proxy.kiwisdr.com:8073",
     "label": "Esk, Queensland, Australia (Oceania)",
     "lat": -27.24, "lon": 152.42},
]
BANDS = [("20m", 14074, 14.074), ("40m", 7074, 7.074)]

CATEGORY_THRESHOLDS = {"none": 0, "few": "1-9 unique decodes",
                       "many": ">=10 unique decodes"}


def fetch_json(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent":
                                                "nature-mirror-mesh/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def get_solar_data(now):
    """Return dict of solar inputs + provenance. Never raises."""
    solar = {"status": "ok", "sources": [], "fetched_utc":
             now.strftime("%Y-%m-%dT%H:%M:%SZ"),
             "f107_used": None, "f107_kind": None,
             "ap_used": None, "ssn_smoothed_r12": None}
    today = now.strftime("%Y-%m-%d")
    # 1) 45-day forecast product: today's forecast F10.7 + Ap.
    try:
        d = fetch_json(NOAA_45DAY)
        solar["sources"].append(NOAA_45DAY)
        for row in d.get("data", []):
            if row.get("time", "").startswith(today):
                if row.get("metric") == "f107":
                    solar["f107_forecast_today"] = row.get("value")
                elif row.get("metric") == "ap":
                    solar["ap_forecast_today"] = row.get("value")
    except Exception as e:  # noqa: BLE001 - provenance matters, not the type
        solar["forecast_error"] = "%s: %s" % (type(e).__name__, e)
    # 2) Observed monthly indices: latest observed F10.7 month + latest
    #    smoothed sunspot number (the R12-style input P.533 would use).
    try:
        d = fetch_json(NOAA_OBSERVED)
        solar["sources"].append(NOAA_OBSERVED)
        valid_f = [r for r in d if isinstance(r.get("f10.7"), (int, float))
                   and r["f10.7"] > 0]
        if valid_f:
            last = valid_f[-1]
            solar["f107_observed_latest_month"] = {
                "month": last.get("time-tag"), "f10.7": last.get("f10.7"),
                "ssn": last.get("ssn")}
        valid_s = [r for r in d
                   if isinstance(r.get("smoothed_swpc_ssn"), (int, float))
                   and r["smoothed_swpc_ssn"] > 0]
        if valid_s:
            last = valid_s[-1]
            solar["ssn_smoothed_r12"] = {
                "month": last.get("time-tag"),
                "value": last.get("smoothed_swpc_ssn")}
    except Exception as e:  # noqa: BLE001
        solar["observed_error"] = "%s: %s" % (type(e).__name__, e)
    # Choose the F10.7 the model actually uses: today's forecast first
    # (it is the value issued for the prediction day), else latest
    # observed month, else a stated fallback default.
    if solar.get("f107_forecast_today") is not None:
        solar["f107_used"] = float(solar["f107_forecast_today"])
        solar["f107_kind"] = "NOAA 45-day forecast for prediction date"
    elif solar.get("f107_observed_latest_month"):
        solar["f107_used"] = float(
            solar["f107_observed_latest_month"]["f10.7"])
        solar["f107_kind"] = "latest observed monthly F10.7 (fallback)"
    else:
        solar["f107_used"] = 100.0
        solar["f107_kind"] = "FALLBACK DEFAULT 100 (NOAA unreachable)"
        solar["status"] = "degraded: NOAA unreachable, default F10.7 used"
    solar["ap_used"] = (float(solar["ap_forecast_today"])
                        if solar.get("ap_forecast_today") is not None
                        else None)
    return solar


def probe_p533():
    """Honestly probe for a usable ITU-R P.533 implementation."""
    probe = {"itur_installed": False, "itu533_module": False,
             "detail": ""}
    try:
        import itur  # noqa: F401
        probe["itur_installed"] = True
        probe["itur_version"] = getattr(itur, "__version__", "unknown")
    except Exception as e:  # noqa: BLE001
        probe["detail"] = "itur not importable: %s" % e
        return probe
    try:
        import itur.models.itu533  # noqa: F401
        probe["itu533_module"] = True
        probe["detail"] = "itur.models.itu533 importable"
    except Exception as e:  # noqa: BLE001
        probe["detail"] = ("itur %s present but itur.models.itu533 NOT "
                           "available (%s: %s); itur 0.4.0 ships no P.533 "
                           "HF model" % (probe.get("itur_version"),
                                         type(e).__name__, e))
    return probe


# ------------------------- heuristic v1 -------------------------------

def solar_elevation_deg(lat, lon, now):
    n = now.timetuple().tm_yday
    decl = math.radians(-23.44 * math.cos(
        math.radians(360.0 / 365.0 * (n + 10))))
    utc_h = (now.hour + now.minute / 60.0 + now.second / 3600.0)
    lon_sub = 180.0 - 15.0 * utc_h          # subsolar longitude (approx)
    phi = math.radians(lat)
    h = math.radians(lon - lon_sub)
    sin_e = (math.sin(phi) * math.sin(decl)
             + math.cos(phi) * math.cos(decl) * math.cos(h))
    return math.degrees(math.asin(max(-1.0, min(1.0, sin_e))))


def destination_point(lat, lon, bearing_deg, dist_km):
    r = 6371.0
    d = dist_km / r
    br = math.radians(bearing_deg)
    phi1, lam1 = math.radians(lat), math.radians(lon)
    phi2 = math.asin(math.sin(phi1) * math.cos(d)
                     + math.cos(phi1) * math.sin(d) * math.cos(br))
    lam2 = lam1 + math.atan2(math.sin(br) * math.sin(d) * math.cos(phi1),
                             math.cos(d) - math.sin(phi1) * math.sin(phi2))
    return math.degrees(phi2), math.degrees(lam2)


def smoothstep(x, lo, hi):
    t = max(0.0, min(1.0, (x - lo) / (hi - lo)))
    return t * t * (3.0 - 2.0 * t)


def heuristic_scores(site, f107, ap, now):
    samples = [(site["lat"], site["lon"], "site")]
    for b in (0, 90, 180, 270):
        la, lo = destination_point(site["lat"], site["lon"], b, 1500.0)
        samples.append((la, lo, "mid-%03d" % b))
    per_band = {name: [] for name, _, _ in BANDS}
    sample_rows = []
    for la, lo, tag in samples:
        e = solar_elevation_deg(la, lo, now)
        w = smoothstep(e, -10.0, 8.0)
        fof2 = 4.2 + ((3.0 + 0.062 * f107) - 4.2) * w
        muf = 3.1 * fof2
        row = {"sample": tag, "lat": round(la, 2), "lon": round(lo, 2),
               "solar_elev_deg": round(e, 1), "foF2_MHz": round(fof2, 2),
               "MUF_proxy_MHz": round(muf, 2)}
        for name, _khz, fmhz in BANDS:
            width = 1.2 if name == "20m" else 1.0
            s = 1.0 / (1.0 + math.exp(-(muf - fmhz) / width))
            if name == "40m" and e > 0:
                s *= max(0.25, 1.0 - 0.75 * math.sin(math.radians(e)))
            per_band[name].append(s)
            row[name + "_support"] = round(s, 3)
        sample_rows.append(row)
    out = {}
    disturbed = ap is not None and ap >= 30
    for name, _khz, _fmhz in BANDS:
        score = sum(per_band[name]) / len(per_band[name])
        if disturbed:
            score *= 0.75
        out[name] = {"score": round(score, 3),
                     "expected_decodes": categorize(score)}
    return out, sample_rows, disturbed


def categorize(score):
    if score >= 0.55:
        return "many"
    if score >= 0.25:
        return "few"
    return "none"


# ------------------------------ main ----------------------------------

def main():
    now = datetime.now(timezone.utc)
    solar = get_solar_data(now)
    probe = probe_p533()

    # This build scores with heuristic v1. If a future itur release ships
    # itu533, the probe will show it -- but the prediction must still not
    # silently claim P.533 numbers it did not compute, so the model field
    # only ever names the model that actually produced the scores.
    model = "heuristic v1"
    model_note = ("itur/P.533 probe: %s. Scores in this file were "
                  "produced by transparent heuristic v1."
                  % probe["detail"])

    sites_out = []
    for site in SITES:
        scores, samples, disturbed = heuristic_scores(
            site, solar["f107_used"], solar["ap_used"], now)
        best = max(BANDS, key=lambda b: scores[b[0]]["score"])[0]
        sites_out.append({
            "site": site["site"], "host": site["host"],
            "label": site["label"], "lat": site["lat"], "lon": site["lon"],
            "bands": {name: {"freq_khz": khz,
                             "score": scores[name]["score"],
                             "expected_decodes":
                                 scores[name]["expected_decodes"]}
                      for name, khz, _f in BANDS},
            "predicted_best_band": best,
            "geomagnetic_disturbance_discount_applied": disturbed,
            "samples": samples})

    pred = {
        "experiment": "Nature-Mirror Mesh -- Propagation Oracle Test",
        "prediction_made_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "predicted_for_utc_hour": now.strftime("%Y-%m-%dT%H:00Z"),
        "model": model,
        "model_note": model_note,
        "itur_probe": probe,
        "solar_data": solar,
        "sites": sites_out,
        "measured_category_thresholds": CATEGORY_THRESHOLDS,
        "heuristic_v1_constants": {
            "sample_points": "site + 1500 km at bearings 0/90/180/270",
            "foF2_day_MHz": "3.0 + 0.062 * F10.7",
            "foF2_night_MHz": 4.2,
            "day_night_blend": "smoothstep of solar elevation [-10, +8] deg",
            "MUF_proxy": "3.1 * foF2",
            "support": "logistic in (MUF - band freq); 40m extra D-layer "
                       "absorption factor down to 0.25 at local noon",
            "category_from_score": ">=0.55 many; >=0.25 few; else none",
            "ap_discount": "Ap >= 30 -> all scores x0.75"},
        "integrity": ("This prediction was generated from NOAA solar "
                      "data and geometry ONLY, before any recording "
                      "existed. It does not read any WAV, log, or "
                      "reception result."),
    }

    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(PRED_JSON, "w") as f:
        json.dump(pred, f, indent=2)

    lines = []
    lines.append("=== PROPAGATION ORACLE PREDICTION (made BEFORE recording) ===")
    lines.append("Prediction made (UTC): %s  for hour %s"
                 % (pred["prediction_made_utc"],
                    pred["predicted_for_utc_hour"]))
    lines.append("Model: %s" % model)
    lines.append("Model note: %s" % model_note)
    lines.append("Solar data: F10.7 used = %s (%s); Ap = %s; "
                 "smoothed SSN (R12) = %s"
                 % (solar["f107_used"], solar["f107_kind"],
                    solar["ap_used"],
                    (solar.get("ssn_smoothed_r12") or {}).get("value")))
    lines.append("Solar sources: %s" % "; ".join(solar["sources"]))
    for s in sites_out:
        lines.append("Site %s (%s, %s): predicted best band = %s | "
                     "20m: %s (score %.3f) | 40m: %s (score %.3f)"
                     % (s["site"], s["label"], s["host"],
                        s["predicted_best_band"],
                        s["bands"]["20m"]["expected_decodes"],
                        s["bands"]["20m"]["score"],
                        s["bands"]["40m"]["expected_decodes"],
                        s["bands"]["40m"]["score"]))
    lines.append("Measured categories: none = 0 unique decodes; "
                 "few = 1-9; many = >=10 (90 s recording, ft8_lib decode).")
    lines.append("Integrity: prediction derived from NOAA data + "
                 "geometry only; no recording was consulted.")
    header = "\n".join(lines) + "\n"
    with open(PRED_HEADER, "w") as f:
        f.write(header)

    print(header)
    print("Wrote %s and %s" % (PRED_JSON, PRED_HEADER))
    return 0


if __name__ == "__main__":
    sys.exit(main())
