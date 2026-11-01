# Universal features of price formation in financial markets: perspectives from Deep Learning
Justin A. Sirignano, Rama Cont A — 2018 — doi:10.48550/arXiv.1803.06917 — OpenAlex W4301480741
Retrieved 2026-10-29 UTC from OpenAlex. Cited by 20 (by year: 2019:1, 2020:1, 2021:4, 2022:2, 2023:3, 2024:5, 2025:2, 2026:1). Abstract only; claims are the paper's, not Quant Lab results.

## Extracted from abstract
- **assets:** equities
- **frequency:** intraday
- **sample period:** not stated
- **markets/countries:** not stated
- **horizons:** not stated
- **Sharpe claims:** not stated
- **return claims:** not stated
- **t-stats:** not stated
- **costs:** mentioned
- **out-of-sample:** mentioned

## Abstract
Using a large-scale Deep Learning approach applied to a high-frequency database containing billions of electronic market quotes and transactions for US equities, we uncover nonparametric evidence for the existence of a universal and stationary price formation mechanism relating the dynamics of supply and demand for a stock, as revealed through the order book, to subsequent variations in its market price. We assess the model by testing its out-of-sample predictions for the direction of price moves given the history of price and order flow, across a wide range of stocks and time periods. The universal price formation model is shown to exhibit a remarkably stable out-of-sample prediction accuracy across time, for a wide range of stocks from different sectors. Interestingly, these results also hold for stocks which are not part of the training sample, showing that the relations captured by the model are universal and not asset-specific. The universal model --- trained on data from all stocks --- outperforms, in terms of out-of-sample prediction accuracy, asset-specific linear and nonlinear models trained on time series of any given stock, showing that the universal nature of price formation weighs in favour of pooling together financial data from various stocks, rather than designing asset- or sector-specific models as commonly done. Standard data normalizations based on volatility, price level or average spread, or partitioning the training data into sectors or categories such as large/small tick stocks, do not improve training results. On the other hand, inclusion of price and order flow history over many past observations is shown to improve forecasting performance, showing evidence of path-dependence in price dynamics.

## Did it hold up? Citing papers on replication/critique/costs/decay (3)
| year | cites | title | tags | link |
|---|---|---|---|---|
| 2019 | 288 | DeepLOB: Deep Convolutional Neural Networks for Limit Order Books | - | https://doi.org/10.1109/tsp.2019.2907260 |
| 2023 | 31 | Transformers Versus LSTMs for Electronic Trading | - | https://doi.org/10.2139/ssrn.4577922 |
| 2026 | 0 | Exploiting market state data for forecasting stock prices: an analysis using predictive algorithms for the Dow | - | https://doi.org/10.1186/s40854-026-00950-9 |

## What it helped: most-cited citing papers (8)
| year | cites | title | link |
|---|---|---|---|
| 2019 | 288 | DeepLOB: Deep Convolutional Neural Networks for Limit Order Books | https://doi.org/10.1109/tsp.2019.2907260 |
| 2018 | 92 | Improving Stock Closing Price Prediction Using Recurrent Neural Network and Technical Indicators | https://doi.org/10.1162/neco_a_01124 |
| 2021 | 46 | Understanding the Performance of Machine Learning Models to Predict Credit Default: A Novel Approach for Super | https://doi.org/10.2139/ssrn.3774075 |
| 2023 | 31 | Transformers Versus LSTMs for Electronic Trading | https://doi.org/10.2139/ssrn.4577922 |
| 2024 | 28 | Systemic risk prediction using machine learning: Does network connectedness help prediction? | https://doi.org/10.1016/j.irfa.2024.103147 |
| 2021 | 24 | Slow Momentum with Fast Reversion: A Trading Strategy Using Deep Learning and Changepoint Detection | https://doi.org/10.3905/jfds.2021.1.081 |
| 2020 | 16 | Data Science in Economics | https://doi.org/10.21203/rs.3.rs-27318/v1 |
| - | 14 | Curriculum Learning in Deep Neural Networks for Financial Forecasting | https://openalex.org/W3103688967 |

## Most recent citing papers (8)
| year | cites | title | link |
|---|---|---|---|
| 2026 | 0 | Exploiting market state data for forecasting stock prices: an analysis using predictive algorithms for the Dow | https://doi.org/10.1186/s40854-026-00950-9 |
| 2025 | 0 | A multi-axis diagnostic framework for Hybrid Quantum-Classical Neural Networks in Empirical setting | https://doi.org/10.21203/rs.3.rs-7093575/v1 |
| 2025 | 0 | Forecasting Intraday Volume in Equity Markets with Machine Learning | https://doi.org/10.2139/ssrn.5340629 |
| 2024 | 1 | Generative-discriminative machine learning models for high-frequency financial regime classification | https://doi.org/10.21203/rs.3.rs-4497881/v1 |
| 2024 | 6 | Mesoscale effects of trader learning behaviors in financial markets: A multi-agent reinforcement learning stud | https://doi.org/10.1371/journal.pone.0301141 |
| 2024 | 28 | Systemic risk prediction using machine learning: Does network connectedness help prediction? | https://doi.org/10.1016/j.irfa.2024.103147 |
| 2024 | 0 | Technological and Economic Threats to the U.S. Financial System: An Initial Assessment of Growing Risks | https://doi.org/10.7249/rra2533-1 |
| 2024 | 0 | Predict Mini Flash Crashes from High-Frequency Data by Machine Learning | https://doi.org/10.2139/ssrn.4848471 |

## Builds on: most-cited references (0 of 0)
| year | cites | title | link |
|---|---|---|---|

## Related works (OpenAlex) (8)
| year | cites | title | link |
|---|---|---|---|
| 2023 | 51 | Deep order flow imbalance: Extracting alpha at multiple horizons from the limit order book | https://doi.org/10.1111/mafi.12413 |
| 2025 | 3 | Ascertaining price formation in financial markets with machine learning: Evidence from Chinese stocks | https://doi.org/10.1016/j.pacfin.2025.103029 |
| 2024 | 1 | Price predictability in limit order book with deep learning model | https://doi.org/10.1080/13504851.2024.2409330 |
| 2020 | 1 | Deep Recurrent Modelling of Stationary Bitcoin Price Formation Using the Order Flow | https://doi.org/10.1007/978-3-030-61401-0_17 |
| 2024 | 0 | L’effondrement byzantin et la prise de Constantinople par les Turcs en 1453 | https://openalex.org/W7137454219 |
| 2024 | 0 | L’ordre capétien en France au début du xive siècle | https://openalex.org/W7137710669 |
| 2026 | 0 | Market Conditions and Predictability of Stock Prices: An Empirical Analysis Based on Deep Learning Models | https://doi.org/10.12677/fia.2026.152042 |
| 2026 | 0 | Forecasting stock prices: Deep Learning and Full Order Book Dynamics | https://doi.org/10.3917/fina.pr.055 |
