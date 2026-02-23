# Monte Carlo Spread Distribution Report

Scenarios: **10,000**

---

## Europe (Rotterdam)

Route: `US_Gulf_to_Rotterdam` (5,000 nm, base laden 12.3 d, canal fee $0)

### Spread ($/MMBtu)

| Metric | Value |
| --- | ---: |
| Mean | $+3.082 |
| Median (P50) | $+3.085 |
| Std Dev | $0.423 |
| P05 | $+2.378 |
| P25 | $+2.792 |
| P75 | $+3.372 |
| P95 | $+3.779 |
| VaR (5%) | $+2.378 |
| CVaR (5%) | $+2.198 |
| P(Spread > 0) | 100.0% |
| P(Spread > $1) | 100.0% |
| Skewness | -0.023 |
| Kurtosis | -0.047 |

### TCE ($/day)

| Metric | Value |
| --- | ---: |
| Mean | $+333,626 |
| Median | $+333,384 |
| P05 | $+246,643 |
| P95 | $+419,545 |
| P(TCE > 0) | 100.0% |

---

## Asia (Tokyo via Panama)

Route: `US_Gulf_to_Tokyo_Panama` (9,200 nm, base laden 22.5 d, canal fee $400,000)

### Spread ($/MMBtu)

| Metric | Value |
| --- | ---: |
| Mean | $+4.108 |
| Median (P50) | $+4.111 |
| Std Dev | $0.617 |
| P05 | $+3.097 |
| P25 | $+3.685 |
| P75 | $+4.522 |
| P95 | $+5.128 |
| VaR (5%) | $+3.097 |
| CVaR (5%) | $+2.854 |
| P(Spread > 0) | 100.0% |
| P(Spread > $1) | 100.0% |
| Skewness | +0.038 |
| Kurtosis | -0.032 |

### TCE ($/day)

| Metric | Value |
| --- | ---: |
| Mean | $+275,273 |
| Median | $+274,861 |
| P05 | $+204,647 |
| P95 | $+348,929 |
| P(TCE > 0) | 100.0% |

---

## Asia (Tokyo via COGH)

Route: `US_Gulf_to_Tokyo_COGH` (14,500 nm, base laden 35.5 d, canal fee $0)

### Spread ($/MMBtu)

| Metric | Value |
| --- | ---: |
| Mean | $+3.441 |
| Median (P50) | $+3.439 |
| Std Dev | $0.601 |
| P05 | $+2.458 |
| P25 | $+3.032 |
| P75 | $+3.845 |
| P95 | $+4.438 |
| VaR (5%) | $+2.458 |
| CVaR (5%) | $+2.224 |
| P(Spread > 0) | 100.0% |
| P(Spread > $1) | 100.0% |
| Skewness | +0.034 |
| Kurtosis | -0.044 |

### TCE ($/day)

| Metric | Value |
| --- | ---: |
| Mean | $+155,831 |
| Median | $+155,558 |
| P05 | $+110,350 |
| P95 | $+202,777 |
| P(TCE > 0) | 100.0% |

---

## JERA Domestic Margin Analysis

JERA imports LNG at JKM (USD), converts via USD/JPY, and sells domestically in JPY.  When the import cost exceeds domestic revenue, diversion to the spot market is optimal.

| Metric | Value |
| --- | ---: |
| Domestic Revenue | 1,500 JPY/MMBtu |
| Mean Import Cost | 1,815 JPY/MMBtu |
| Mean Domestic Profit | -315 JPY/MMBtu |
| P05 Domestic Profit | -478 JPY/MMBtu |
| P95 Domestic Profit | -156 JPY/MMBtu |
| Divert Probability | 100.0% |

---

## Optimal Strategy (Real Option — Destination Flexibility)

For each scenario the trader picks the route with the highest spread, or chooses *No-Go* if all routes are unprofitable.  The option premium is the additional value created by flexibility.

### Route Selection Probabilities

| Route | P(chosen) |
| --- | ---: |
| Europe (Rotterdam) | 2.6% |
| Asia (Tokyo via Panama) | 97.4% |
| Asia (Tokyo via COGH) | 0.0% |
| No-Go | 0.0% |

### Optimal Spread ($/MMBtu)

| Metric | Value |
| --- | ---: |
| Mean | $+4.113 |
| Median | $+4.111 |
| P05 | $+3.125 |
| P95 | $+5.128 |
| P(Spread > 0) | 100.0% |

**Option Premium (Spread)**: $+0.0054/MMBtu

**Option Premium (TCE)**: $-54,450/day

---

## Sensitivity Analysis

Variance contribution is based on squared Spearman rank correlation, normalised to 100 %.  This captures monotonic nonlinear effects (e.g. exponential BOG decay).

### Europe (Rotterdam)

| Rank | Factor | Spearman rho | Variance % |
| ---: | --- | ---: | ---: |
| 1 | TTF_Price | +0.6684 | 46.9% |
| 2 | HH_Price | -0.6545 | 44.9% |
| 3 | JKM_Price | +0.2063 | 4.5% |
| 4 | Voyage_Delay | -0.1587 | 2.6% |
| 5 | BOG_Rate | -0.0730 | 0.6% |
| 6 | Fuel_Cost | -0.0640 | 0.4% |
| 7 | Charter_Rate | -0.0254 | 0.1% |
| 8 | USD_JPY | -0.0139 | 0.0% |

### Asia (Tokyo via Panama)

| Rank | Factor | Spearman rho | Variance % |
| ---: | --- | ---: | ---: |
| 1 | JKM_Price | +0.8224 | 61.4% |
| 2 | HH_Price | -0.4582 | 19.1% |
| 3 | TTF_Price | +0.3168 | 9.1% |
| 4 | Fuel_Cost | +0.2268 | 4.7% |
| 5 | Charter_Rate | +0.1920 | 3.3% |
| 6 | Voyage_Delay | -0.1337 | 1.6% |
| 7 | BOG_Rate | -0.0949 | 0.8% |
| 8 | USD_JPY | -0.0131 | 0.0% |

### Asia (Tokyo via COGH)

| Rank | Factor | Spearman rho | Variance % |
| ---: | --- | ---: | ---: |
| 1 | JKM_Price | +0.7500 | 58.3% |
| 2 | HH_Price | -0.5079 | 26.7% |
| 3 | TTF_Price | +0.2624 | 7.1% |
| 4 | Fuel_Cost | +0.1705 | 3.0% |
| 5 | BOG_Rate | -0.1467 | 2.2% |
| 6 | Voyage_Delay | -0.1410 | 2.1% |
| 7 | Charter_Rate | +0.0722 | 0.5% |
| 8 | USD_JPY | -0.0210 | 0.0% |

### Optimal

| Rank | Factor | Spearman rho | Variance % |
| ---: | --- | ---: | ---: |
| 1 | JKM_Price | +0.8201 | 60.9% |
| 2 | HH_Price | -0.4623 | 19.4% |
| 3 | TTF_Price | +0.3225 | 9.4% |
| 4 | Fuel_Cost | +0.2246 | 4.6% |
| 5 | Charter_Rate | +0.1904 | 3.3% |
| 6 | Voyage_Delay | -0.1340 | 1.6% |
| 7 | BOG_Rate | -0.0951 | 0.8% |
| 8 | USD_JPY | -0.0131 | 0.0% |
