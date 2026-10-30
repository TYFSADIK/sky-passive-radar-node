use num_complex::{Complex32, Complex64};

/// c(m) = sum_u conj(ref[u]) * ref[u+m], m = 0..k
fn autocorr(r: &[Complex32], k: usize) -> Vec<Complex64> {
    (0..k)
        .map(|m| r[..r.len() - m].iter().zip(&r[m..]).map(|(a, b)| c64(a.conj()) * c64(*b)).sum())
        .collect()
}

#[inline]
fn c64(z: Complex32) -> Complex64 {
    Complex64::new(z.re as f64, z.im as f64)
}

/// Solve A x = b for Hermitian positive-definite A (row-major k x k) by Cholesky A = L L^H.
fn cholesky_solve(a: &mut [Complex64], b: &[Complex64], k: usize) -> Vec<Complex64> {
    let mut l = vec![Complex64::new(0.0, 0.0); k * k];
    for j in 0..k {
        let mut d = a[j * k + j].re;
        for p in 0..j {
            d -= l[j * k + p].norm_sqr();
        }
        let d = d.max(1e-12).sqrt();
        l[j * k + j] = Complex64::new(d, 0.0);
        for i in j + 1..k {
            let mut s = a[i * k + j];
            for p in 0..j {
                s -= l[i * k + p] * l[j * k + p].conj();
            }
            l[i * k + j] = s / d;
        }
    }
    let mut y = vec![Complex64::new(0.0, 0.0); k];
    for i in 0..k {
        let mut s = b[i];
        for p in 0..i {
            s -= l[i * k + p] * y[p];
        }
        y[i] = s / l[i * k + i];
    }
    let mut x = vec![Complex64::new(0.0, 0.0); k];
    for i in (0..k).rev() {
        let mut s = y[i];
        for p in i + 1..k {
            s -= l[p * k + i].conj() * x[p];
        }
        x[i] = s / l[i * k + i];
    }
    x
}

/// Remove the zero-Doppler subspace spanned by `taps` delayed copies of the reference.
pub fn eca(reference: &[Complex32], surv: &[Complex32], taps: usize) -> Vec<Complex32> {
    let n = reference.len().min(surv.len());
    let c = autocorr(&reference[..n], taps);
    let mut a = vec![Complex64::new(0.0, 0.0); taps * taps];
    for i in 0..taps {
        for j in 0..taps {
            // R[i][j] = c(i-j); c(-m) = conj(c(m))
            a[i * taps + j] = if i >= j { c[i - j] } else { c[j - i].conj() };
        }
    }
    let load = 1e-9 * c[0].re;
    for i in 0..taps {
        a[i * taps + i].re += load;
    }
    // p[i] = sum_t conj(ref[t-i]) * surv[t]
    let p: Vec<Complex64> = (0..taps)
        .map(|i| (i..n).map(|t| c64(reference[t - i].conj()) * c64(surv[t])).sum())
        .collect();
    let w = cholesky_solve(&mut a, &p, taps);
    let w32: Vec<Complex32> = w.iter().map(|z| Complex32::new(z.re as f32, z.im as f32)).collect();
    (0..n)
        .map(|t| {
            let mut est = Complex32::new(0.0, 0.0);
            for (j, wj) in w32.iter().enumerate().take(taps.min(t + 1)) {
                est += wj * reference[t - j];
            }
            surv[t] - est
        })
        .collect()
}

/// ECA-B: independent cancellation per batch, so the filter tracks slowly changing clutter.
pub fn eca_batched(reference: &[Complex32], surv: &[Complex32], taps: usize, batch: usize) -> Vec<Complex32> {
    use rayon::prelude::*;
    let n = reference.len().min(surv.len());
    let starts: Vec<usize> = (0..n).step_by(batch.max(taps * 4)).collect();
    starts
        .par_iter()
        .map(|&s| {
            let e = (s + batch).min(n);
            eca(&reference[s..e], &surv[s..e], taps)
        })
        .collect::<Vec<_>>()
        .concat()
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Deterministic complex noise (xorshift), no rand dependency.
    fn noise(n: usize, seed: u64) -> Vec<Complex32> {
        let mut x = seed;
        let mut next = || {
            x ^= x << 13;
            x ^= x >> 7;
            x ^= x << 17;
            (x as f64 / u64::MAX as f64 - 0.5) as f32
        };
        (0..n).map(|_| Complex32::new(next(), next())).collect()
    }

    #[test]
    fn eca_removes_direct_path_and_clutter() {
        let r = noise(20_000, 7);
        let target = noise(20_000, 99);
        let surv: Vec<Complex32> = (0..r.len())
            .map(|t| r[t] + if t >= 5 { r[t - 5] * 0.3 } else { Complex32::new(0.0, 0.0) } + target[t] * 0.01)
            .collect();
        let out = eca(&r, &surv, 16);
        let p = |v: &[Complex32]| v.iter().map(|z| z.norm_sqr() as f64).sum::<f64>();
        let suppression_db = 10.0 * (p(&surv) / p(&out)).log10();
        assert!(suppression_db > 30.0, "only {suppression_db:.1} dB");
    }
}
