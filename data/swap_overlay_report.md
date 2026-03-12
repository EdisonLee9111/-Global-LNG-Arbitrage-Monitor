# Swap Overlay — Hedge Effectiveness Report

## Configuration

- **Mode**: `auto`
- **Notional**: 3,744,000 MMBtu
- **Basis noise std**: 0.0

### Swap Legs

| Leg | Enabled | Hedge Ratio | Swap Rate | MC Mean | Implied Cost |
| --- | :---: | ---: | ---: | ---: | ---: |
| hh | ✓ | 80% | 3.525 | 3.525 | +0.000 |
| jkm | ✓ | 80% | 15.336 | 15.336 | +0.000 |
| charter | – | 50% | 0.000 | 60013.343 | +0.000 |
| fx | – | 50% | 0.000 | 159.474 | +0.000 |

---

## Distribution Comparison — Optimal Spread ($/MMBtu)

| Metric | Unhedged | Hedged | Δ |
| --- | ---: | ---: | ---: |
| Mean | +9.150 | +9.150 | -0.000 |
| Std Dev | 2.451 | 1.610 | -0.841 |
| Median (P50) | +9.121 | +9.046 | -0.075 |
| P05 (VaR 5%) | +5.146 | +6.911 | +1.765 |
| CVaR 5% | +4.169 | +6.700 | +2.531 |
| Skewness | +0.060 | +0.487 | +0.427 |
| Kurtosis | +0.003 | -0.249 | -0.252 |
| P(Spread > 0) | 100.0% | 100.0% | +0.0% |

## Distribution Comparison — Optimal TCE ($/day)

| Metric | Unhedged | Hedged | Δ |
| --- | ---: | ---: | ---: |
| Mean | +943,681 | +947,496 | +3,816 |
| Std Dev | 308,684 | 250,293 | -58,390 |
| P05 | +429,425 | +466,714 | +37,289 |
| P95 | +1,442,764 | +1,316,370 | -126,394 |
| P(TCE > 0) | 100.0% | 100.0% | +0.0% |

---

## Hedge Effectiveness

| Metric | Value |
| --- | ---: |
| Variance Reduction | 56.8% |
| VaR Reduction ($/MMBtu) | +1.765 |
| CVaR Reduction ($/MMBtu) | +2.531 |
| Hedge Cost ($/MMBtu) | +0.000 |
| Sharpe (Unhedged) | 3.734 |
| Sharpe (Hedged) | 5.684 |
| Sharpe Improvement | +1.950 |
| P(Loss) Change | +0.0% |
| JKM Effective Coverage | 96.3% |

---

## Hedge Ratio Sensitivity

| h | VaR 5% | CVaR 5% | Var Reduction | Hedge Cost | P(>0) |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0% | +5.146 | +4.169 | 0.0% | +0.000 | 100.0% |
| 25% | +5.864 | +5.113 | 30.6% | +0.000 | 100.0% |
| 50% | +6.432 | +5.944 | 49.5% | +0.000 | 100.0% |
| 75% | +6.863 | +6.601 | 56.8% | +0.000 | 100.0% |
| 100% | +6.845 | +6.664 | 52.4% | +0.000 | 100.0% |

---

## Structural Basis Risk

> 100% JKM swap covers ≈96.3% of Netback JKM exposure (remaining_ratio ≈ 0.963 after BOG decay). The remaining ≈3.7% is structural basis risk from BOG decay, voyage-time variability, and the non-linear Netback structure (shipping + canal fees dilute the JKM coefficient). Charter FFA P&L uses cargo_size as denominator (not delivered volume), introducing an additional ≈3.7% approximation.
