# Monte Carlo Spread Distribution Report

Scenarios: **10,000**

---

## Europe (Rotterdam)

Route: `US_Gulf_to_Rotterdam` (5,000 nm, base laden 12.3 d, canal fee $0)

### Spread ($/MMBtu)

| Metric | Value |
| --- | ---: |
| Mean | $+3.076 |
| Median (P50) | $+3.079 |
| Std Dev | $0.429 |
| P05 | $+2.363 |
| P25 | $+2.782 |
| P75 | $+3.370 |
| P95 | $+3.784 |
| VaR (5%) | $+2.363 |
| CVaR (5%) | $+2.181 |
| P(Spread > 0) | 100.0% |
| P(Spread > $1) | 100.0% |
| Skewness | -0.022 |
| Kurtosis | -0.047 |

### TCE ($/day)

| Metric | Value |
| --- | ---: |
| Mean | $+332,965 |
| Median | $+332,679 |
| P05 | $+245,421 |
| P95 | $+419,926 |
| P(TCE > 0) | 100.0% |

---

## Asia (Tokyo via Panama)

Route: `US_Gulf_to_Tokyo_Panama` (9,200 nm, base laden 22.5 d, canal fee $400,000)

### Spread ($/MMBtu)

| Metric | Value |
| --- | ---: |
| Mean | $+4.099 |
| Median (P50) | $+4.102 |
| Std Dev | $0.658 |
| P05 | $+3.021 |
| P25 | $+3.649 |
| P75 | $+4.541 |
| P95 | $+5.199 |
| VaR (5%) | $+3.021 |
| CVaR (5%) | $+2.762 |
| P(Spread > 0) | 100.0% |
| P(Spread > $1) | 100.0% |
| Skewness | +0.037 |
| Kurtosis | -0.029 |

### TCE ($/day)

| Metric | Value |
| --- | ---: |
| Mean | $+274,724 |
| Median | $+274,170 |
| P05 | $+199,664 |
| P95 | $+352,840 |
| P(TCE > 0) | 100.0% |

---

## Asia (Tokyo via COGH)

Route: `US_Gulf_to_Tokyo_COGH` (14,500 nm, base laden 35.5 d, canal fee $0)

### Spread ($/MMBtu)

| Metric | Value |
| --- | ---: |
| Mean | $+3.433 |
| Median (P50) | $+3.431 |
| Std Dev | $0.637 |
| P05 | $+2.392 |
| P25 | $+2.998 |
| P75 | $+3.860 |
| P95 | $+4.489 |
| VaR (5%) | $+2.392 |
| CVaR (5%) | $+2.141 |
| P(Spread > 0) | 100.0% |
| P(Spread > $1) | 100.0% |
| Skewness | +0.036 |
| Kurtosis | -0.041 |

### TCE ($/day)

| Metric | Value |
| --- | ---: |
| Mean | $+155,456 |
| Median | $+155,207 |
| P05 | $+107,563 |
| P95 | $+204,744 |
| P(TCE > 0) | 100.0% |

---

## JERA Domestic Margin Analysis

JERA imports LNG at JKM (USD), converts via USD/JPY, and sells domestically in JPY.  When the import cost exceeds domestic revenue, diversion to the spot market is optimal.

| Metric | Value |
| --- | ---: |
| Domestic Revenue | 1,500 JPY/MMBtu |
| Mean Import Cost | 1,815 JPY/MMBtu |
| Mean Domestic Profit | -315 JPY/MMBtu |
| P05 Domestic Profit | -489 JPY/MMBtu |
| P95 Domestic Profit | -145 JPY/MMBtu |
| Divert Probability | 99.9% |

---

## Optimal Strategy (Real Option — Destination Flexibility)

For each scenario the trader picks the route with the highest spread, or chooses *No-Go* if all routes are unprofitable.  The option premium is the additional value created by flexibility.

### Route Selection Probabilities

| Route | P(chosen) |
| --- | ---: |
| Europe (Rotterdam) | 3.4% |
| Asia (Tokyo via Panama) | 96.6% |
| Asia (Tokyo via COGH) | 0.0% |
| No-Go | 0.0% |

### Optimal Spread ($/MMBtu)

| Metric | Value |
| --- | ---: |
| Mean | $+4.107 |
| Median | $+4.102 |
| P05 | $+3.066 |
| P95 | $+5.199 |
| P(Spread > 0) | 100.0% |

**Option Premium (Spread)**: $+0.0079/MMBtu

**Option Premium (TCE)**: $-53,147/day

---

## Sensitivity Analysis

Variance contribution is based on squared Spearman rank correlation, normalised to 100 %.  This captures monotonic nonlinear effects (e.g. exponential BOG decay).

### Europe (Rotterdam)

| Rank | Factor | Spearman rho | Variance % |
| ---: | --- | ---: | ---: |
| 1 | TTF_Price | +0.6766 | 47.8% |
| 2 | HH_Price | -0.6476 | 43.8% |
| 3 | JKM_Price | +0.2175 | 4.9% |
| 4 | Voyage_Delay | -0.1569 | 2.6% |
| 5 | BOG_Rate | -0.0719 | 0.5% |
| 6 | Fuel_Cost | -0.0551 | 0.3% |
| 7 | Charter_Rate | -0.0191 | 0.0% |
| 8 | USD_JPY | -0.0138 | 0.0% |

### Asia (Tokyo via Panama)

| Rank | Factor | Spearman rho | Variance % |
| ---: | --- | ---: | ---: |
| 1 | JKM_Price | +0.8440 | 62.1% |
| 2 | HH_Price | -0.4299 | 16.1% |
| 3 | TTF_Price | +0.3372 | 9.9% |
| 4 | Fuel_Cost | +0.2562 | 5.7% |
| 5 | Charter_Rate | +0.2161 | 4.1% |
| 6 | Voyage_Delay | -0.1263 | 1.4% |
| 7 | BOG_Rate | -0.0888 | 0.7% |
| 8 | USD_JPY | -0.0120 | 0.0% |

### Asia (Tokyo via COGH)

| Rank | Factor | Spearman rho | Variance % |
| ---: | --- | ---: | ---: |
| 1 | JKM_Price | +0.7798 | 60.2% |
| 2 | HH_Price | -0.4784 | 22.7% |
| 3 | TTF_Price | +0.2875 | 8.2% |
| 4 | Fuel_Cost | +0.2045 | 4.1% |
| 5 | BOG_Rate | -0.1379 | 1.9% |
| 6 | Voyage_Delay | -0.1337 | 1.8% |
| 7 | Charter_Rate | +0.1043 | 1.1% |
| 8 | USD_JPY | -0.0196 | 0.0% |

### Optimal

| Rank | Factor | Spearman rho | Variance % |
| ---: | --- | ---: | ---: |
| 1 | JKM_Price | +0.8410 | 61.5% |
| 2 | HH_Price | -0.4353 | 16.5% |
| 3 | TTF_Price | +0.3445 | 10.3% |
| 4 | Fuel_Cost | +0.2533 | 5.6% |
| 5 | Charter_Rate | +0.2140 | 4.0% |
| 6 | Voyage_Delay | -0.1269 | 1.4% |
| 7 | BOG_Rate | -0.0890 | 0.7% |
| 8 | USD_JPY | -0.0118 | 0.0% |
