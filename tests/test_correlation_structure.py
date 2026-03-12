"""
test_correlation_structure.py — Tests for Gaussian Copula correlation engine.

Design notes (from user review):
- nearest_psd output may differ from input by O(eps) due to the re-normalization
  step (diag → 1.0).  Use np.allclose with atol=1e-10, not strict equality.
- Cholesky reconstruction: L @ L.T should equal the (potentially slightly
  adjusted) PSD matrix, not necessarily the raw input.
"""

import numpy as np
import pytest
from scipy import stats as sp_stats

from src.correlation_structure import (
    nearest_psd,
    cholesky_decompose,
    sample_correlated_uniforms,
)


# ---------------------------------------------------------------------------
# Helper: build test matrices
# ---------------------------------------------------------------------------

def _valid_corr_3x3() -> np.ndarray:
    """A valid 3×3 positive-definite correlation matrix."""
    return np.array([
        [1.00,  0.60,  0.20],
        [0.60,  1.00,  0.40],
        [0.20,  0.40,  1.00],
    ])


def _near_singular_corr() -> np.ndarray:
    """Near-PSD matrix: one eigenvalue is very small but should be clipped > 0."""
    base = _valid_corr_3x3()
    # Knock the (0,1) pair toward 0.99 to make it nearly rank-deficient
    perturbed = base.copy()
    perturbed[0, 1] = 0.99
    perturbed[1, 0] = 0.99
    return perturbed


def _non_psd_matrix() -> np.ndarray:
    """Explicitly non-PSD matrix (negative eigenvalue before fixing)."""
    m = np.array([
        [1.0,  0.9,  0.9],
        [0.9,  1.0,  0.9],
        [0.9,  0.9,  1.0],
    ])
    # This has eigenvalues [2.7, 0.1, 0.1] → all positive actually,
    # so inject a clearly negative off-diagonal
    m2 = np.array([
        [ 1.0, -0.9,  0.9],
        [-0.9,  1.0, -0.9],
        [ 0.9, -0.9,  1.0],
    ])
    return m2


# ---------------------------------------------------------------------------
# 1. nearest_psd: all eigenvalues become positive
# ---------------------------------------------------------------------------

class TestNearestPSD:
    def test_all_eigenvalues_positive_after_fix(self):
        """After projection, all eigenvalues must be > 0."""
        mat = _non_psd_matrix()
        fixed = nearest_psd(mat)
        eigvals = np.linalg.eigvalsh(fixed)
        assert np.all(eigvals > 0), (
            f"Found non-positive eigenvalues: {eigvals}"
        )

    def test_diagonal_is_ones(self):
        """nearest_psd always re-normalizes to a correlation matrix (diag=1)."""
        fixed = nearest_psd(_near_singular_corr())
        np.testing.assert_allclose(np.diag(fixed), 1.0, atol=1e-12)

    def test_valid_matrix_preserved(self):
        """
        A valid PSD correlation matrix passes through nearest_psd nearly unchanged.
        Due to re-normalization step, allow atol=1e-10 (not strict equality).
        """
        mat = _valid_corr_3x3()
        fixed = nearest_psd(mat)
        np.testing.assert_allclose(fixed, mat, atol=1e-10)


# ---------------------------------------------------------------------------
# 2. Cholesky: L @ L.T ≈ nearest_psd(corr_matrix)
# ---------------------------------------------------------------------------

class TestCholesky:
    def test_reconstruction(self):
        """L @ L.T must recover the PSD-projected correlation matrix."""
        df_corr_pd = __import__("pandas").DataFrame(
            _valid_corr_3x3(),
            index=["A", "B", "C"],
            columns=["A", "B", "C"],
        )
        from src.correlation_structure import cholesky_decompose
        L = cholesky_decompose(df_corr_pd)
        reconstructed = L @ L.T
        np.testing.assert_allclose(
            reconstructed,
            nearest_psd(_valid_corr_3x3()),
            atol=1e-12,
        )


# ---------------------------------------------------------------------------
# 3. Gaussian Copula: sampled uniforms ∈ [0, 1]
# ---------------------------------------------------------------------------

class TestGaussianCopula:
    def test_uniforms_in_unit_interval(self):
        """All sampled uniform values must lie within [0, 1]."""
        L = np.linalg.cholesky(_valid_corr_3x3())
        rng = np.random.default_rng(seed=99)
        u = sample_correlated_uniforms(L, n_samples=2_000, rng=rng)
        assert u.shape == (2_000, 3)
        assert np.all(u >= 0.0) and np.all(u <= 1.0)

    def test_marginals_approximately_uniform(self):
        """
        Each column of u should be approximately Uniform(0,1).
        A KS test against U[0,1] should not reject at alpha=0.001.
        """
        L = np.linalg.cholesky(_valid_corr_3x3())
        rng = np.random.default_rng(seed=100)
        u = sample_correlated_uniforms(L, n_samples=5_000, rng=rng)
        for col_idx in range(u.shape[1]):
            ks_stat, p_value = sp_stats.kstest(u[:, col_idx], "uniform")
            assert p_value > 0.001, (
                f"Column {col_idx}: KS p-value {p_value:.4f} suggests "
                f"marginals are not uniform"
            )
