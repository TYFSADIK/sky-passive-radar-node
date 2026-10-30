"""ADS-B ground truth: predict each aircraft's bistatic range and Doppler, then score detections.

Bistatic (excess-path) range: R_b = |Tx->A| + |A->Rx| - |Tx->Rx|
Bistatic Doppler:            f_d = -(1/lambda) d/dt(|Tx->A| + |A->Rx|)
"""
import math

import numpy as np

from .signals import C

WGS84_A, WGS84_E2 = 6378137.0, 6.69437999014e-3


def lla_to_ecef(lat, lon, alt):
    la, lo = math.radians(lat), math.radians(lon)
    n = WGS84_A / math.sqrt(1 - WGS84_E2 * math.sin(la) ** 2)
    return np.array([(n + alt) * math.cos(la) * math.cos(lo), (n + alt) * math.cos(la) * math.sin(lo),
                     (n * (1 - WGS84_E2) + alt) * math.sin(la)])


def enu_basis(lat, lon):
    la, lo = math.radians(lat), math.radians(lon)
    e = np.array([-math.sin(lo), math.cos(lo), 0])
    n = np.array([-math.sin(la) * math.cos(lo), -math.sin(la) * math.sin(lo), math.cos(la)])
    u = np.array([math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la)])
    return e, n, u


def bistatic(tx, rx, ac_pos, ac_vel, freq_hz):
    """All ECEF metres / m/s. Returns (bistatic_range_m, doppler_hz)."""
    a, b = ac_pos - tx, ac_pos - rx
    ra, rb = np.linalg.norm(a), np.linalg.norm(b)
    rng = ra + rb - np.linalg.norm(rx - tx)
    rdot = ac_vel @ (a / ra) + ac_vel @ (b / rb)
    return float(rng), float(-rdot * freq_hz / C)


def aircraft_state(lat, lon, alt_m, gs_kt, track_deg, vrate_fpm=0.0):
    """From dump1090/readsb fields to ECEF position + velocity."""
    p = lla_to_ecef(lat, lon, alt_m)
    e, n, u = enu_basis(lat, lon)
    gs = gs_kt * 0.514444
    tr = math.radians(track_deg)
    v = gs * math.sin(tr) * e + gs * math.cos(tr) * n + vrate_fpm * 0.00508 * u
    return p, v


def associate(dets, predicted, gate_range_m=1500, gate_dopp_hz=4.0):
    """dets: [(range, dopp, snr)], predicted: {icao: (range, dopp)} -> matches, misses, false alarms."""
    used, matches = set(), {}
    for icao, (pr, pd) in predicted.items():
        best = None
        for i, (r, d, _) in enumerate(dets):
            if i in used:
                continue
            if abs(r - pr) <= gate_range_m and abs(d - pd) <= gate_dopp_hz:
                score = (r - pr) ** 2 / gate_range_m ** 2 + (d - pd) ** 2 / gate_dopp_hz ** 2
                if best is None or score < best[1]:
                    best = (i, score)
        if best:
            used.add(best[0])
            matches[icao] = dets[best[0]]
    misses = [k for k in predicted if k not in matches]
    false = [d for i, d in enumerate(dets) if i not in used]
    return matches, misses, false
