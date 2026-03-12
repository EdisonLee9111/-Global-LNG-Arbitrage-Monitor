# Step 2 - Distribution Family Selection (Auto Generated)

Goal: choose distribution/process families for uncertain Netback drivers and parameterize them for 30-60 day horizon.

## Distribution Plan

| parameter | distribution_family | support | key_parameters | horizon_note | implementation_note |
| --- | --- | --- | --- | --- | --- |
| HH price | OU mean-reversion (primary), Lognormal/GBM (fallback) | Price > 0 | S0=3.09, kappa=0.1080, theta=3.53, sigma_ou=0.3136; mu_gbm=0.000724/day, sigma_gbm=0.065980/day | Project from t0 to discharge horizon T=30-60 days | Use OU transition for gas-specific mean reversion; keep GBM as stress/fallback |
| TTF price | OU mean-reversion (primary), Lognormal/GBM (fallback) | Price > 0 | S0=18.85, kappa=0.0116, theta=13.39, sigma_ou=0.4999; mu_gbm=0.002121/day, sigma_gbm=0.037891/day | Project from t0 to discharge horizon T=30-60 days | Use OU transition for gas-specific mean reversion; keep GBM as stress/fallback |
| JKM price | OU mean-reversion (primary), Lognormal/GBM (fallback) | Price > 0 | S0=21.42, kappa=0.0373, theta=13.92, sigma_ou=0.6442; mu_gbm=0.002244/day, sigma_gbm=0.044899/day | Project from t0 to discharge horizon T=30-60 days | Use OU transition for gas-specific mean reversion; keep GBM as stress/fallback |
| Charter rate | Lognormal (base) + optional jump mean-reversion | Rate > 0, right-skewed | S0=60,000 USD/day (config fallback), regime=low season, mu_ln=10.9408, sigma_ln=0.350, jump_lambda~0.04/period, jump_mean~0.30 | Model over same cargo horizon (30-60 days), initialize from current market regime | Captures non-negativity and upside spikes (e.g., >200k/day in tight markets) |
| Fuel cost | Lognormal (tracks VLSFO/LSMGO bunker prices) | Cost > 0 | S0=15,000 USD/day (config fallback), mu_ln=9.5708, sigma_ln=0.300; for MEGI/X-DF LNG-fuelled vessels fuel cost is correlated with HH/JKM price -- model as rho(fuel, gas_price) in joint simulation | Same cargo horizon (30-60 days); co-moves with oil/gas benchmarks | ~20% of total shipping cost; hidden correlation source for LNG-fuelled vessels |
| Voyage days (delay component) | Shifted Gamma for extra delay | Extra delay >= 0 | Base days deterministic by distance/speed; Delay ~ Gamma(k=2.0, theta=1.5) days; Panama dry-season shift=3.0 day(s) | Total voyage days = deterministic base + random delay | Right-skew handles weather/queue/congestion; dry-season Panama handled by shift |
| BOG boil-off rate | Scaled Beta on [0.08%, 0.15%] (or triangular simplification) | 0.0008 <= rate <= 0.0015 | low=0.0800%, high=0.1500%, mode=0.1499%, beta(alpha=18.97, beta=1.03) | Low-impact in v1; can stay fixed in core simulation and move to sensitivity layer | Beta enforces bounded support; triangular(min, mode, max) is lightweight fallback |
| USD/JPY | Normal on returns (base), Lognormal on level (equivalent transform) | Return in R; level > 0 | S0=157.56, mu_ret=0.000253/day, sigma_ret=0.006200/day (replace sigma with option IV when available) | Scale to T=30-60 days: mean~mu*T, vol~sigma*sqrt(T) | Must-model in v1: JPY depreciation raises real cost for Japanese buyers, suppressing spot JKM demand; JPY appreciation does the opposite. Include in joint simulation with price factors. If FX option implied vol is available, override historical sigma for forward-looking risk |

## Notes

- Price variables prefer OU mean reversion for gas economics, with GBM/lognormal as fallback stress view.
- Charter rate uses positive right-skew family with optional jump behavior for peak-season spikes.
- Delay component is modeled separately from deterministic base voyage days.
- BOG is bounded and low-impact; suitable for bounded distributions or sensitivity-only treatment in v1.
