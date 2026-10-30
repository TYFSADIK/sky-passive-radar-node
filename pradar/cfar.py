"""2D cell-averaging CFAR on the range-Doppler map.

For each cell, estimate the noise from a ring of training cells (excluding guard
cells around the cell under test) and declare a detection if the cell exceeds
alpha * noise, where alpha gives the design false-alarm probability:
    alpha = N * (Pfa^(-1/N) - 1)    for square-law detection, N training cells.
Implemented with summed-area tables, so it is O(cells) regardless of window size.
"""
import numpy as np


def _box_sum(sat, r0, r1, c0, c1):
    return sat[r1, c1] - sat[r0, c1] - sat[r1, c0] + sat[r0, c0]


def ca_cfar(power, guard=(2, 2), train=(6, 8), pfa=1e-6, exclude_zero_doppler=2):
    D, R = power.shape
    gd, gr = guard
    td, tr = train
    pad = ((gd + td, gd + td), (gr + tr, gr + tr))
    p = np.pad(power, pad, mode="wrap")         # Doppler wraps; range edge effects are acceptable
    sat = np.zeros((p.shape[0] + 1, p.shape[1] + 1))
    sat[1:, 1:] = p.cumsum(0).cumsum(1)
    dd = np.arange(D)[:, None] + gd + td
    rr = np.arange(R)[None, :] + gr + tr
    outer = _box_sum(sat, dd - gd - td, dd + gd + td + 1, rr - gr - tr, rr + gr + tr + 1)
    inner = _box_sum(sat, dd - gd, dd + gd + 1, rr - gr, rr + gr + 1)
    n_train = (2 * (gd + td) + 1) * (2 * (gr + tr) + 1) - (2 * gd + 1) * (2 * gr + 1)
    noise = (outer - inner) / n_train
    alpha = n_train * (pfa ** (-1 / n_train) - 1)
    det = power > alpha * noise
    mid = D // 2
    if exclude_zero_doppler:
        det[mid - exclude_zero_doppler:mid + exclude_zero_doppler + 1, :] = False
    return det, noise


def peaks(power, det, ranges, dopp, max_peaks=20):
    """Collapse detection blobs to local maxima -> list of (range_m, doppler_hz, snr_db)."""
    out = []
    D, R = power.shape
    ys, xs = np.nonzero(det)
    for y, x in zip(ys, xs):
        y0, y1, x0, x1 = max(y - 1, 0), min(y + 2, D), max(x - 1, 0), min(x + 2, R)
        if power[y, x] >= power[y0:y1, x0:x1].max():
            out.append((float(ranges[x]), float(dopp[y]), float(10 * np.log10(power[y, x] / np.median(power)))))
    return sorted(out, key=lambda p: -p[2])[:max_peaks]
