"""Extended Cancellation Algorithm (ECA), Colone et al. 2009.

Project the surveillance signal onto the subspace spanned by delayed copies of the
reference (and optionally +-1 Doppler-bin copies, ECA-S style) and subtract it.
That removes the direct path and stationary clutter on the zero-Doppler ridge,
which is otherwise 40-60 dB above any aircraft echo.
"""
import numpy as np


def eca(ref, surv, n_taps=64, doppler_bins=(0.0,), fs=None, batch=None):
    """Return clutter-cancelled surveillance. Batched (ECA-B) if batch is set: adapts to slow clutter changes."""
    if batch:
        out = np.empty_like(surv)
        for s in range(0, len(surv), batch):
            out[s:s + batch] = eca(ref[s:s + batch], surv[s:s + batch], n_taps, doppler_bins, fs)
        return out
    n = len(ref)
    cols = []
    t = np.arange(n)
    for fd in doppler_bins:
        r = ref if fd == 0 else ref * np.exp(2j * np.pi * fd * t / fs)
        for k in range(n_taps):
            cols.append(np.concatenate([np.zeros(k, complex), r[:n - k]]))
    X = np.stack(cols, axis=1)
    w, *_ = np.linalg.lstsq(X, surv, rcond=None)
    return surv - X @ w
