# Monte Carlo Spread Distribution Report

Scenarios: **10,000**

---

## Europe (Rotterdam)

Route: `US_Gulf_to_Rotterdam` (5,000 nm, base laden 12.3 d, canal fee $0)

### Spread ($/MMBtu)

| Metric | Value |
| --- | ---: |
| Mean | $+9.013 |
| Median (P50) | $+9.012 |
| Std Dev | $2.557 |
| P05 | $+4.726 |
| P25 | $+7.331 |
| P75 | $+10.732 |
| P95 | $+13.193 |
| VaR (5%) | $+4.726 |
| CVaR (5%) | $+3.708 |
| P(Spread > 0) | 100.0% |
| P(Spread > $1) | 99.9% |
| Skewness | -0.010 |
| Kurtosis | +0.009 |

### TCE ($/day)

| Metric | Value |
| --- | ---: |
| Mean | $+974,781 |
| Median | $+972,549 |
| P05 | $+504,143 |
| P95 | $+1,443,087 |
| P(TCE > 0) | 100.0% |

---

## Asia (Tokyo via Panama)

Route: `US_Gulf_to_Tokyo_Panama` (9,200 nm, base laden 22.5 d, canal fee $400,000)

### Spread ($/MMBtu)

| Metric | Value |
| --- | ---: |
| Mean | $+6.991 |
| Median (P50) | $+6.975 |
| Std Dev | $2.218 |
| P05 | $+3.405 |
| P25 | $+5.500 |
| P75 | $+8.471 |
| P95 | $+10.676 |
| VaR (5%) | $+3.405 |
| CVaR (5%) | $+2.460 |
| P(Spread > 0) | 99.9% |
| P(Spread > $1) | 99.7% |
| Skewness | +0.029 |
| Kurtosis | -0.005 |

### TCE ($/day)

| Metric | Value |
| --- | ---: |
| Mean | $+468,447 |
| Median | $+466,640 |
| P05 | $+226,341 |
| P95 | $+719,570 |
| P(TCE > 0) | 99.9% |

---

## Asia (Tokyo via COGH)

Route: `US_Gulf_to_Tokyo_COGH` (14,500 nm, base laden 35.5 d, canal fee $0)

### Spread ($/MMBtu)

| Metric | Value |
| --- | ---: |
| Mean | $+6.276 |
| Median (P50) | $+6.257 |
| Std Dev | $2.151 |
| P05 | $+2.781 |
| P25 | $+4.826 |
| P75 | $+7.720 |
| P95 | $+9.852 |
| VaR (5%) | $+2.781 |
| CVaR (5%) | $+1.883 |
| P(Spread > 0) | 99.8% |
| P(Spread > $1) | 99.4% |
| Skewness | +0.029 |
| Kurtosis | -0.008 |

### TCE ($/day)

| Metric | Value |
| --- | ---: |
| Mean | $+284,145 |
| Median | $+282,783 |
| P05 | $+125,531 |
| P95 | $+447,892 |
| P(TCE > 0) | 99.8% |

---

## JERA Domestic Margin Analysis

JERA imports LNG at JKM (USD), converts via USD/JPY, and sells domestically in JPY.  When the import cost exceeds domestic revenue, diversion to the spot market is optimal.

| Metric | Value |
| --- | ---: |
| Domestic Revenue | 1,500 JPY/MMBtu |
| Mean Import Cost | 2,445 JPY/MMBtu |
| Mean Domestic Profit | -945 JPY/MMBtu |
| P05 Domestic Profit | -1,588 JPY/MMBtu |
| P95 Domestic Profit | -326 JPY/MMBtu |
| Divert Probability | 99.5% |

---

## Optimal Strategy (Real Option — Destination Flexibility)

For each scenario the trader picks the route with the highest spread, or chooses *No-Go* if all routes are unprofitable.  The option premium is the additional value created by flexibility.

### Route Selection Probabilities

| Route | P(chosen) |
| --- | ---: |
| Europe (Rotterdam) | 85.7% |
| Asia (Tokyo via Panama) | 14.3% |
| Asia (Tokyo via COGH) | 0.0% |
| No-Go | 0.0% |

### Optimal Spread ($/MMBtu)

| Metric | Value |
| --- | ---: |
| Mean | $+9.150 |
| Median | $+9.121 |
| P05 | $+5.146 |
| P95 | $+13.196 |
| P(Spread > 0) | 100.0% |

**Option Premium (Spread)**: $+0.1373/MMBtu

**Option Premium (TCE)**: $-31,100/day

---

## Sensitivity Analysis

Variance contribution is based on squared Spearman rank correlation, normalised to 100 %.  This captures monotonic nonlinear effects (e.g. exponential BOG decay).

### Europe (Rotterdam)

| Rank | Factor | Spearman rho | Variance % |
| ---: | --- | ---: | ---: |
| 1 | TTF_Price | +0.9571 | 57.6% |
| 2 | JKM_Price | +0.6487 | 26.5% |
| 3 | Fuel_Cost | +0.3723 | 8.7% |
| 4 | Charter_Rate | +0.2946 | 5.5% |
| 5 | HH_Price | -0.1583 | 1.6% |
| 6 | Voyage_Delay | -0.0368 | 0.1% |
| 7 | USD_JPY | -0.0210 | 0.0% |
| 8 | BOG_Rate | -0.0144 | 0.0% |

### Asia (Tokyo via Panama)

| Rank | Factor | Spearman rho | Variance % |
| ---: | --- | ---: | ---: |
| 1 | JKM_Price | +0.9382 | 53.0% |
| 2 | TTF_Price | +0.6250 | 23.5% |
| 3 | Fuel_Cost | +0.4122 | 10.2% |
| 4 | Charter_Rate | +0.3973 | 9.5% |
| 5 | HH_Price | -0.2408 | 3.5% |
| 6 | Voyage_Delay | -0.0511 | 0.2% |
| 7 | BOG_Rate | -0.0294 | 0.1% |
| 8 | USD_JPY | +0.0061 | 0.0% |

### Asia (Tokyo via COGH)

| Rank | Factor | Spearman rho | Variance % |
| ---: | --- | ---: | ---: |
| 1 | JKM_Price | +0.9278 | 53.5% |
| 2 | TTF_Price | +0.6160 | 23.6% |
| 3 | Fuel_Cost | +0.3993 | 9.9% |
| 4 | Charter_Rate | +0.3677 | 8.4% |
| 5 | HH_Price | -0.2602 | 4.2% |
| 6 | Voyage_Delay | -0.0533 | 0.2% |
| 7 | BOG_Rate | -0.0467 | 0.1% |
| 8 | USD_JPY | +0.0043 | 0.0% |

### Optimal

| Rank | Factor | Spearman rho | Variance % |
| ---: | --- | ---: | ---: |
| 1 | TTF_Price | +0.9399 | 53.5% |
| 2 | JKM_Price | +0.6989 | 29.6% |
| 3 | Fuel_Cost | +0.3855 | 9.0% |
| 4 | Charter_Rate | +0.3152 | 6.0% |
| 5 | HH_Price | -0.1724 | 1.8% |
| 6 | Voyage_Delay | -0.0379 | 0.1% |
| 7 | BOG_Rate | -0.0184 | 0.0% |
| 8 | USD_JPY | -0.0175 | 0.0% |
