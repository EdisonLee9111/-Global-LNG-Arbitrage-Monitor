# Step 1 - Netback 参数清单与建模优先级

目的：先识别当前 Netback 公式的输入参数，并按不确定性与方差贡献进行分层，确定第一版模型范围。

## 1) 当前参数清单（与代码一致）

| 参数 | 当前代码取值 | 类型 | 波动特征 | 是否值得建模 |
|---|---|---|---|---|
| HH 价格 | `main.py` 中 `market_data.iloc[-1]["HH_Price"]`（来源 `data_loader.fetch_henry_hub()`） | 市场风险 | 日频波动，具均值回复特征 | 必须 |
| JKM 价格 | `main.py` 中 `market_data.iloc[-1]["JKM_Price"]`（由 `generate_synthetic_jkm()` 合成：`TTF + premium + seasonal + noise`） | 市场风险 | 日频波动，季节性强 | 必须 |
| TTF 价格 | `main.py` 中 `market_data.iloc[-1]["TTF_Price"]`（来源 `data_loader.fetch_ttf()`） | 市场风险 | 日频波动，季节性明显 | 必须 |
| 租船费 | `config.DEFAULT_CHARTER_RATE = 60000`，由 `LNGCalculator(charter_rate=...)` 使用 | 市场风险 | 周频到月频波动，季节性强 | 必须 |
| 航行天数 | `distance_nm / speed`（`calculate_voyage_days()`，速度为配置常量） | 运营风险 | 受天气、拥堵、绕航影响 | 应该 |
| BOG 蒸发率 | `config.BOIL_OFF_RATE = 0.15%/day` | 运营风险 | 船型相关，小幅波动 | 可选（影响相对小） |
| 运河费 | `config.CANAL_FEE_PANAMA = 400000`、`CANAL_FEE_SUEZ = 300000` | 结构性 | 阶段性调整，短期近似常量 | 暂不建模 |
| 液化费 | `config.DEFAULT_LIQUEFACTION_COST = 3.0` | 合同性 | 长协锁定，低频变动 | 暂不建模 |
| USD/JPY | `market_data["USD_JPY"]`（来源 `data_loader.fetch_usd_jpy()`） | 市场风险 | 日频波动，宏观驱动明显 | 应该（影响亚洲买家行为） |

## 2) 判断原则（第一版）

按对 `Arb_Spread = Netback - HH` 的方差贡献排序，通常：

1. 价格因子（HH/TTF/JKM）
2. 运费因子（Charter）
3. 航行天数
4. 其他成本项（BOG、运河费、液化费）

因此第一版建议只建模 4 个必须项：`HH`、`TTF`、`JKM`、`租船费`。其余参数先固定或用简单区间近似。

## 3) 第一版建模边界（可直接执行）

- **纳入随机过程**：`HH_Price`、`TTF_Price`、`JKM_Price`、`charter_rate`
- **固定常量**：`boil_off_rate`、`canal_fee`、`liquefaction_cost`
- **预留情景变量**：`voyage_days`、`USD_JPY`（先做上下限场景，不进入主随机核）

## 4) 与现有代码的接口建议

- 使用 `market_data` 历史序列估计价格与相关性（HH/TTF/JKM）。
- 在 `LNGCalculator` 层新增可注入参数（例如场景化 `charter_rate` 与 `speed`），保持向后兼容。
- 先不改 `calculate_netback()` 主公式，仅把输入从“单点值”提升为“场景值/路径值”。
