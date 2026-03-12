# Step 3 - Parameter Estimates (Auto Generated)

Horizon shown is in *trading days* from today.

## HH_Price
- Method: **historical**
- Distribution: `ou`
- Horizon: 45 days

| Parameter | Value |
| --- | --- |
| s0 | 3.087000 |
| kappa | 0.108006 |
| theta | 3.534756 |
| sigma | 0.313598 |
| horizon_mean | 3.531287 |
| horizon_std | 0.674716 |
| horizon_p05 | 2.421379 |
| horizon_p95 | 4.641195 |
| gbm_mu_daily | 0.000724 |
| gbm_sigma_daily | 0.065980 |
| gbm_horizon_p05 | 1.396166 |
| gbm_horizon_p95 | 5.988849 |

## TTF_Price
- Method: **historical**
- Distribution: `ou`
- Horizon: 45 days

| Parameter | Value |
| --- | --- |
| s0 | 18.849405 |
| kappa | 0.011647 |
| theta | 13.394758 |
| sigma | 0.499891 |
| horizon_mean | 16.624410 |
| horizon_std | 2.639533 |
| horizon_p05 | 12.282379 |
| horizon_p95 | 20.966442 |
| gbm_mu_daily | 0.002121 |
| gbm_sigma_daily | 0.037891 |
| gbm_horizon_p05 | 13.217040 |
| gbm_horizon_p95 | 30.500830 |

## JKM_Price
- Method: **historical**
- Distribution: `ou`
- Horizon: 45 days

| Parameter | Value |
| --- | --- |
| s0 | 21.424763 |
| kappa | 0.037297 |
| theta | 13.920188 |
| sigma | 0.644161 |
| horizon_mean | 15.321118 |
| horizon_std | 2.317069 |
| horizon_p05 | 11.509540 |
| horizon_p95 | 19.132696 |
| gbm_mu_daily | 0.002244 |
| gbm_sigma_daily | 0.044899 |
| gbm_horizon_p05 | 13.800786 |
| gbm_horizon_p95 | 37.175716 |

## Charter_Rate
- Method: **expert_prior**
- Distribution: `lognormal`
- Horizon: 45 days
- Source: `config_fallback`

| Parameter | Value |
| --- | --- |
| s0 | 60000.000000 |
| mu_ln | 10.940850 |
| sigma_ln | 0.350000 |
| sigma_daily | 0.022048 |
| horizon_median | 59347.325818 |
| horizon_p05 | 46530.512544 |
| horizon_p95 | 75694.525790 |

## USD_JPY
- Method: **historical**
- Distribution: `gbm`
- Horizon: 45 days

| Parameter | Value |
| --- | --- |
| s0 | 157.559006 |
| mu_daily | 0.000272 |
| sigma_daily | 0.006200 |
| annualized_vol | 0.098419 |
| horizon_mean | 159.500000 |
| horizon_p05 | 148.823995 |
| horizon_p95 | 170.646437 |

## Fuel_Cost
- Method: **expert_prior**
- Distribution: `lognormal`
- Horizon: 45 days
- Source: `config_fallback`

| Parameter | Value |
| --- | --- |
| s0 | 15000.000000 |
| mu_ln | 9.570805 |
| sigma_ln | 0.300000 |
| sigma_daily | 0.018898 |
| horizon_median | 14879.947286 |
| horizon_p05 | 12079.051539 |
| horizon_p95 | 18330.315963 |

## Voyage_Delay
- Method: **expert_prior**
- Distribution: `gamma`
- Horizon: 45 days

| Parameter | Value |
| --- | --- |
| gamma_k | 2.000000 |
| gamma_theta | 1.500000 |
| panama_shift | 3.000000 |
| mean_delay | 6.000000 |

## BOG_Rate
- Method: **manual**
- Distribution: `triangular`
- Horizon: 45 days

| Parameter | Value |
| --- | --- |
| low | 0.000800 |
| mode | 0.001499 |
| high | 0.001500 |
| mean | 0.001266 |
