use crate::C;
use num_complex::Complex32;
use rayon::prelude::*;
use rustfft::FftPlanner;

pub struct RangeDoppler {
    /// power[d * n_lags + r], Doppler rows fftshifted (row n_dopp/2 is 0 Hz)
    pub power: Vec<f32>,
    pub n_dopp: usize,
    pub n_lags: usize,
    pub ranges_m: Vec<f64>,
    pub doppler_hz: Vec<f64>,
}

/// Batches algorithm: per-batch range correlation via FFT, then FFT across batches for Doppler.
pub fn caf(reference: &[Complex32], surv: &[Complex32], fs: f64, max_range_m: f64) -> RangeDoppler {
    let n_lags = (max_range_m / C * fs).ceil() as usize + 1;
    let l = (4 * n_lags).next_power_of_two().max(256);
    let b = reference.len() / l;
    let nfft = (l + n_lags).next_power_of_two();
    let mut planner = FftPlanner::<f32>::new();
    let fwd = planner.plan_fft_forward(nfft);
    let inv = planner.plan_fft_inverse(nfft);

    // range profile per batch: rd[batch][lag]
    let rd: Vec<Vec<Complex32>> = (0..b)
        .into_par_iter()
        .map(|bi| {
            let mut r = vec![Complex32::new(0.0, 0.0); nfft];
            let mut s = vec![Complex32::new(0.0, 0.0); nfft];
            r[..l].copy_from_slice(&reference[bi * l..(bi + 1) * l]);
            let s_end = ((bi + 1) * l + n_lags).min(surv.len());
            s[..s_end - bi * l].copy_from_slice(&surv[bi * l..s_end]);
            fwd.process(&mut r);
            fwd.process(&mut s);
            let mut x: Vec<Complex32> = s.iter().zip(&r).map(|(a, b)| a * b.conj()).collect();
            inv.process(&mut x);
            x.truncate(n_lags);
            x
        })
        .collect();

    let dfft = planner.plan_fft_forward(b);
    let hann: Vec<f32> = (0..b).map(|i| 0.5 - 0.5 * (2.0 * std::f32::consts::PI * i as f32 / (b - 1) as f32).cos()).collect();
    let cols: Vec<Vec<f32>> = (0..n_lags)
        .into_par_iter()
        .map(|lag| {
            let mut col: Vec<Complex32> = (0..b).map(|bi| rd[bi][lag] * hann[bi]).collect();
            dfft.process(&mut col);
            // fftshift
            (0..b).map(|d| col[(d + b - b / 2) % b].norm_sqr()).collect()
        })
        .collect();

    let mut power = vec![0f32; b * n_lags];
    for (lag, col) in cols.iter().enumerate() {
        for (d, v) in col.iter().enumerate() {
            power[d * n_lags + lag] = *v;
        }
    }
    let prf = fs / l as f64;
    RangeDoppler {
        power,
        n_dopp: b,
        n_lags,
        ranges_m: (0..n_lags).map(|i| i as f64 * C / fs).collect(),
        doppler_hz: (0..b).map(|d| (d as f64 - (b / 2) as f64) * prf / b as f64).collect(),
    }
}
