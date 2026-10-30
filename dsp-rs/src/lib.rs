//! Passive radar DSP, the real-time counterpart of the Python research pipeline in `../pradar`.
//!
//! * [`eca`]  Extended Cancellation Algorithm, batched (ECA-B). Normal equations use the
//!   Toeplitz autocorrelation of the reference (O(N*K) instead of O(N*K^2)), solved by
//!   complex Cholesky with diagonal loading.
//! * [`caf`]  cross-ambiguity function by the batches algorithm, parallel over batches and lags.
//! * [`cfar`] 2D cell-averaging CFAR with summed-area tables, plus local-maximum peak picking.
//!
//! Input is interleaved little-endian f32 I/Q (`.cf32`), the GNU Radio / KrakenSDR / SoapySDR format.

pub mod caf;
pub mod cfar;
pub mod eca;

use num_complex::Complex32;

pub const C: f64 = 299_792_458.0;

pub fn read_cf32(bytes: &[u8]) -> Vec<Complex32> {
    let (chunks, _) = bytes.as_chunks::<8>();
    chunks
        .iter()
        .map(|b| Complex32::new(f32::from_le_bytes([b[0], b[1], b[2], b[3]]), f32::from_le_bytes([b[4], b[5], b[6], b[7]])))
        .collect()
}

#[derive(Debug, Clone, serde::Serialize)]
pub struct Detection {
    pub range_m: f64,
    pub doppler_hz: f64,
    pub snr_db: f64,
}

pub struct Config {
    pub fs: f64,
    pub max_range_m: f64,
    pub taps: usize,
    pub eca_batch: usize,
    pub pfa: f64,
    pub guard: (usize, usize),
    pub train: (usize, usize),
    pub exclude_zero_doppler: usize,
}

impl Default for Config {
    fn default() -> Self {
        Config { fs: 250_000.0, max_range_m: 45_000.0, taps: 40, eca_batch: 62_500, pfa: 1e-6,
                 guard: (2, 2), train: (6, 8), exclude_zero_doppler: 2 }
    }
}

/// Full pipeline for one coherent processing interval.
pub fn process(reference: &[Complex32], surveillance: &[Complex32], cfg: &Config) -> Vec<Detection> {
    let clean = eca::eca_batched(reference, surveillance, cfg.taps, cfg.eca_batch);
    let map = caf::caf(reference, &clean, cfg.fs, cfg.max_range_m);
    let det = cfar::ca_cfar(&map.power, map.n_dopp, map.n_lags, cfg.guard, cfg.train, cfg.pfa, cfg.exclude_zero_doppler);
    cfar::peaks(&map, &det, 20)
}
