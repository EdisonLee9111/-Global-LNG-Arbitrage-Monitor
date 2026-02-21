# Step 4 - Correlation Structure (Auto Generated)

Estimated from 199 daily log-return observations.

## Target Correlation Matrix

| | HH_Price | JKM_Price | TTF_Price | USD_JPY | Charter_Rate |
| --- | --- | --- | --- | --- | --- |
| **HH_Price** | +1.000 | +0.353 | +0.277 | -0.010 | +0.200 |
| **JKM_Price** | +0.353 | +1.000 | +0.810 | +0.241 | +0.550 |
| **TTF_Price** | +0.277 | +0.810 | +1.000 | +0.211 | +0.400 |
| **USD_JPY** | -0.010 | +0.241 | +0.211 | +1.000 | +0.050 |
| **Charter_Rate** | +0.200 | +0.550 | +0.400 | +0.050 | +1.000 |

## Gaussian Copula Demo Sample Correlation (sanity check)

| | HH_Price | JKM_Price | TTF_Price | USD_JPY | Charter_Rate |
| --- | --- | --- | --- | --- | --- |
| **HH_Price** | +1.000 | +0.361 | +0.287 | +0.014 | +0.219 |
| **JKM_Price** | +0.361 | +1.000 | +0.823 | +0.245 | +0.548 |
| **TTF_Price** | +0.287 | +0.823 | +1.000 | +0.196 | +0.408 |
| **USD_JPY** | +0.014 | +0.245 | +0.196 | +1.000 | +0.069 |
| **Charter_Rate** | +0.219 | +0.548 | +0.408 | +0.069 | +1.000 |

## Notes

- Charter_Rate has no daily series; correlations are injected from domain priors (JKM~0.55, TTF~0.40, HH~0.20, FX~0.05) and can be overridden.
- Matrix is projected to nearest PSD after any override to guarantee valid Cholesky decomposition.
- Demo sample correlation should closely match target; deviations shrink with more samples.
