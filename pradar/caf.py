"""Cross-ambiguity function (range-Doppler map) via the batches algorithm.

Split the CPI into B batches of L samples. For each batch, correlate surveillance
with reference over range lags using FFTs; then an FFT across batches gives Doppler.
Cost O(B * L log L) instead of O(N * R * D).  Doppler resolution = 1 / CPI, max
unambiguous Doppler = +- fs / (2 L).
"""
import numpy as np

from .signals import C


def caf(ref, surv, fs, max_range_m=60_000, batch_len=None):
    n_lags = int(np.ceil(max_range_m / C * fs)) + 1
    L = batch_len or max(256, 1 << int(np.ceil(np.log2(4 * n_lags))))
    B = len(ref) // L
    nfft = 1 << int(np.ceil(np.log2(L + n_lags)))
    rd = np.empty((B, n_lags), complex)
    for b in range(B):
        r = ref[b * L:(b + 1) * L]
        s = surv[b * L:min((b + 1) * L + n_lags, len(surv))]
        xc = np.fft.ifft(np.fft.fft(s, nfft) * np.conj(np.fft.fft(r, nfft)))
        rd[b] = xc[:n_lags]
    win = np.hanning(B)[:, None]
    m = np.fft.fftshift(np.fft.fft(rd * win, axis=0), axes=0)
    dopp = np.fft.fftshift(np.fft.fftfreq(B, L / fs))
    ranges = np.arange(n_lags) * C / fs
    return np.abs(m) ** 2, ranges, dopp
