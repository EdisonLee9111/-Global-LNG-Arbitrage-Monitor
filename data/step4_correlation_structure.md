# Step 4 - Correlation Structure (Auto Generated)

Estimated from 258 daily log-return observations.

## Target Correlation Matrix

| | HH_Price | JKM_Price | TTF_Price | USD_JPY | Charter_Rate | Fuel_Cost |
| --- | --- | --- | --- | --- | --- | --- |
| **HH_Price** | +1.000 | +0.082 | +0.119 | -0.087 | +0.192 | +0.717 |
| **JKM_Price** | +0.082 | +1.000 | +0.700 | -0.018 | +0.540 | +0.670 |
| **TTF_Price** | +0.119 | +0.700 | +1.000 | -0.043 | +0.398 | +0.588 |
| **USD_JPY** | -0.087 | -0.018 | -0.043 | +1.000 | +0.048 | +0.094 |
| **Charter_Rate** | +0.192 | +0.540 | +0.398 | +0.048 | +1.000 | +0.255 |
| **Fuel_Cost** | +0.717 | +0.670 | +0.588 | +0.094 | +0.255 | +1.000 |

## Gaussian Copula Demo Sample Correlation (sanity check)

| | HH_Price | JKM_Price | TTF_Price | USD_JPY | Charter_Rate | Fuel_Cost |
| --- | --- | --- | --- | --- | --- | --- |
| **HH_Price** | +1.000 | +0.081 | +0.112 | -0.093 | +0.196 | +0.706 |
| **JKM_Price** | +0.081 | +1.000 | +0.709 | -0.025 | +0.538 | +0.679 |
| **TTF_Price** | +0.112 | +0.709 | +1.000 | -0.032 | +0.398 | +0.597 |
| **USD_JPY** | -0.093 | -0.025 | -0.032 | +1.000 | +0.040 | +0.094 |
| **Charter_Rate** | +0.196 | +0.538 | +0.398 | +0.040 | +1.000 | +0.260 |
| **Fuel_Cost** | +0.706 | +0.679 | +0.597 | +0.094 | +0.260 | +1.000 |

## Notes

- **JKM is synthetic** (TTF + Asia premium + noise in current data loader); the JKM–TTF correlation is artificially elevated (~0.95+). With a real JKM feed (e.g. Platts JKM) expect ρ ≈ 0.80–0.85. Until then, consider overriding this pair via `pairwise_overrides`.
- Charter_Rate has no daily series; correlations are injected from domain priors (JKM~0.55, TTF~0.40, HH~0.20, FX~0.05) and can be overridden.
- Fuel_Cost has no daily series; correlations are injected from domain priors for MEGI/X-DF LNG-fuelled vessels (HH~0.75, JKM~0.70, TTF~0.60, Charter~0.25, FX~0.10) and can be overridden.
- Matrix is projected to nearest PSD after any override to guarantee valid Cholesky decomposition.
- Demo sample correlation should closely match target; deviations shrink with more samples.
