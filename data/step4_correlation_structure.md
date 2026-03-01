# Step 4 - Correlation Structure (Auto Generated)

Estimated from 755 daily log-return observations.

## Target Correlation Matrix

| | HH_Price | JKM_Price | TTF_Price | USD_JPY | Charter_Rate | Fuel_Cost |
| --- | --- | --- | --- | --- | --- | --- |
| **HH_Price** | +1.000 | +0.028 | +0.018 | +0.005 | +0.180 | +0.672 |
| **JKM_Price** | +0.028 | +1.000 | +0.458 | +0.004 | +0.527 | +0.632 |
| **TTF_Price** | +0.018 | +0.458 | +1.000 | +0.003 | +0.387 | +0.554 |
| **USD_JPY** | +0.005 | +0.004 | +0.003 | +1.000 | +0.047 | +0.091 |
| **Charter_Rate** | +0.180 | +0.527 | +0.387 | +0.047 | +1.000 | +0.263 |
| **Fuel_Cost** | +0.672 | +0.632 | +0.554 | +0.091 | +0.263 | +1.000 |

## Gaussian Copula Demo Sample Correlation (sanity check)

| | HH_Price | JKM_Price | TTF_Price | USD_JPY | Charter_Rate | Fuel_Cost |
| --- | --- | --- | --- | --- | --- | --- |
| **HH_Price** | +1.000 | +0.028 | +0.010 | -0.004 | +0.183 | +0.660 |
| **JKM_Price** | +0.028 | +1.000 | +0.469 | -0.003 | +0.526 | +0.645 |
| **TTF_Price** | +0.010 | +0.469 | +1.000 | +0.019 | +0.386 | +0.560 |
| **USD_JPY** | -0.004 | -0.003 | +0.019 | +1.000 | +0.042 | +0.090 |
| **Charter_Rate** | +0.183 | +0.526 | +0.386 | +0.042 | +1.000 | +0.268 |
| **Fuel_Cost** | +0.660 | +0.645 | +0.560 | +0.090 | +0.268 | +1.000 |

## Notes

- **JKM is synthetic** (TTF + Asia premium + noise in current data loader); the JKM–TTF correlation is artificially elevated (~0.95+). With a real JKM feed (e.g. Platts JKM) expect ρ ≈ 0.80–0.85. Until then, consider overriding this pair via `pairwise_overrides`.
- Charter_Rate has no daily series; correlations are injected from domain priors (JKM~0.55, TTF~0.40, HH~0.20, FX~0.05) and can be overridden.
- Fuel_Cost has no daily series; correlations are injected from domain priors for MEGI/X-DF LNG-fuelled vessels (HH~0.75, JKM~0.70, TTF~0.60, Charter~0.25, FX~0.10) and can be overridden.
- Matrix is projected to nearest PSD after any override to guarantee valid Cholesky decomposition.
- Demo sample correlation should closely match target; deviations shrink with more samples.
