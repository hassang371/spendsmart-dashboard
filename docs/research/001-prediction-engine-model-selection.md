# Research: Prediction Engine — Model Selection, Architecture & Training

> **Date:** 2026-04-06
> **Researchers:** 3 parallel research agents (model selection, optimizers/training, open-source papers)
> **Scope:** Evaluate TFT against 20+ modern alternatives, survey 15+ optimizers, analyze innovations from Kimi, DeepSeek, Meta, Apple, Google, Amazon
> **Decision:** Two-tier architecture (Chronos-2 + TFT-Hybrid) — see `docs/features/009-prediction-engine.md`

---

## Table of Contents

1. [Time-Series Model Evaluation](#1-time-series-model-evaluation)
   - 1.1 TFT (Temporal Fusion Transformer)
   - 1.2 PatchTST
   - 1.3 iTransformer
   - 1.4 TimeMixer / TimeMixer++
   - 1.5 TSMixer
   - 1.6 Crossformer, FEDformer, Autoformer
   - 1.7 Notable 2025-2026 Task-Specific Models
2. [Time Series Foundation Models](#2-time-series-foundation-models)
   - 2.1 Amazon Chronos-2
   - 2.2 Google TimesFM 2.5
   - 2.3 Salesforce Moirai 2.0
   - 2.4 TiRex
   - 2.5 IBM TTM (Tiny Time Mixers)
   - 2.6 IBM FlowState
   - 2.7 Datadog Toto
   - 2.8 Nixtla TimeGPT-2
   - 2.9 Lag-Llama
3. [Requirements Matrix](#3-requirements-matrix)
4. [Benchmark Results on Financial/Economic Data](#4-benchmark-results-on-financialeconomic-data)
5. [Personal Finance / Consumer Spending Papers](#5-personal-finance--consumer-spending-papers)
6. [Modern Optimizers Beyond AdamW](#6-modern-optimizers-beyond-adamw)
   - 6.1 Muon
   - 6.2 MuonClip (Kimi/Moonshot AI)
   - 6.3 SOAP
   - 6.4 Kron (PSGD)
   - 6.5 MARS
   - 6.6 Schedule-Free Optimizer (Meta)
   - 6.7 Prodigy
   - 6.8 AdEMAMix (Apple)
   - 6.9 Lion (Google Brain)
   - 6.10 Sophia (Stanford)
   - 6.11 Adan
   - 6.12 Cautious Optimizers
   - 6.13 Grokfast
   - 6.14 Mano
7. [Learning Rate Schedules](#7-learning-rate-schedules)
8. [Training Techniques for Small Models](#8-training-techniques-for-small-models)
   - 8.1 Knowledge Distillation
   - 8.2 Curriculum Learning
   - 8.3 Mixed Precision Training
   - 8.4 Gradient Accumulation
   - 8.5 Early Stopping
   - 8.6 Data Augmentation
   - 8.7 Regularization
9. [Architecture Innovations from Open-Source Models](#9-architecture-innovations-from-open-source-models)
   - 9.1 GQA vs MHA
   - 9.2 RoPE for Temporal Data
   - 9.3 SwiGLU / GeGLU
   - 9.4 RMSNorm vs LayerNorm
   - 9.5 Flash Attention
   - 9.6 Mixture of Experts (MoE)
   - 9.7 Multi-Head Latent Attention (DeepSeek)
   - 9.8 PatchTST / iTransformer Patterns
   - 9.9 Mamba / State Space Models
   - 9.10 Hybrid Mamba+Attention
   - 9.11 Differential Transformer
   - 9.12 xLSTM
   - 9.13 Multi-Token Prediction
   - 9.14 LoRA for Per-User Adaptation
10. [Open-Source Model Deep Dives](#10-open-source-model-deep-dives)
    - 10.1 Kimi K2 (Moonshot AI)
    - 10.2 Kimi K2.5
    - 10.3 DeepSeek-V3
    - 10.4 Meta / Llama
    - 10.5 Mistral / Mixtral
    - 10.6 Google Time Series Research
    - 10.7 Apple Research
11. [Quantization and Efficiency](#11-quantization-and-efficiency)
12. [Recommendations Summary](#12-recommendations-summary)
13. [Sources](#13-sources)

---

## 1. Time-Series Model Evaluation

### 1.1 TFT (Temporal Fusion Transformer) — The Incumbent

**Architecture:** Hybrid LSTM + multi-head attention + gated residual networks + Variable Selection Networks (VSN).

**Strengths:**

- ONLY model with built-in interpretability: per-instance variable importance, temporal attention weights, static enrichment
- Native support for static covariates, past-observed inputs, known future inputs
- Native probabilistic forecasting via quantile regression
- Well-supported in pytorch-forecasting, Darts, NeuralForecast, MATLAB
- Still competitive: 4th overall (1st non-ensemble) in VN1 forecasting competition (2025)

**Weaknesses:**

- Published 2019 — no longer SOTA on benchmarks
- Quadratic attention cost for long sequences
- Requires future covariates in some implementations
- N-HiTS is 50x faster; TiDE is 10-40x faster to train
- Complex architecture with many hyperparameters

**SCALE Suitability:** HIGH for interpretability/covariates; MODERATE for raw accuracy

### 1.2 PatchTST (ICLR 2023)

Segments time series into patches, processes each channel independently. 21% lower MSE vs Transformer baselines. But channel-independent design **ignores inter-variable relationships** (critical gap for our spending/income/balance interaction). No probabilistic forecasting, no covariate support, no interpretability.

**SCALE Suitability:** LOW

### 1.3 iTransformer (ICLR 2024 Spotlight)

Flips the attention axis: attention across variables, FFN across time. SOTA on high-dimensional multivariate benchmarks. But no probabilistic forecasting, no static covariate support, no interpretability.

**SCALE Suitability:** LOW-MODERATE

### 1.4 TimeMixer / TimeMixer++ (ICLR 2024)

All-MLP multiscale decomposition. SOTA in both long and short-term forecasting. Efficient. But no probabilistic/covariate/interpretability support.

**SCALE Suitability:** LOW

### 1.5 TSMixer (Google, KDD 2023)

All-MLP alternating time-mixing and feature-mixing. 8-60% better than Transformer/MLP baselines, 2-3x faster. Simple architecture but missing our core requirements.

**SCALE Suitability:** LOW

### 1.6 Crossformer, FEDformer, Autoformer

All have been surpassed by newer models. None offer probabilistic forecasting, covariate handling, or interpretability. FEDformer's frequency-domain approach achieved 22.6% MSE reduction over Autoformer but is now outdated.

**SCALE Suitability:** LOW for all three

### 1.7 Notable 2025-2026 Task-Specific Models

- **EMTSF:** Ensemble of xLSTM + Linear + PatchTST + minGRU. Outperforms all individual models but complex to deploy.
- **DualPathTST:** Addresses PatchTST's cross-variable gap. Still no covariate/probabilistic support.
- **N-HiTS:** 20% better than Transformers with 50x less compute.

---

## 2. Time Series Foundation Models

### 2.1 Amazon Chronos-2 (Oct 2025) — CURRENT BENCHMARK LEADER

- **Size:** 120M params (28M small variant)
- **Architecture:** Encoder-only (T5-inspired) with group attention mechanism
- **Covariates:** FULL native support — past-only, known-future, categorical
- **Probabilistic:** NATIVE multi-step quantile forecasts
- **Benchmarks:** #1 on fev-bench, GIFT-Eval, and Chronos Benchmark II. >90% win rate vs Chronos-Bolt. Surpasses TimesFM-2.5 and TiRex on WQL and MASE.
- **Inference:** >300 forecasts/sec on A10G GPU. CPU inference supported. Small variant (28M) within 1% accuracy.
- **Open source:** Yes (HuggingFace, GitHub, SageMaker deployment)

**SCALE Suitability:** VERY HIGH

### 2.2 Google TimesFM 2.5 (Sep 2025)

- **Size:** 200M params (down from 500M in v2.0)
- **Context:** 16,384 points (up from 2,048)
- **Covariates:** Partial via XReg (linear ridge regression correction), not native
- **Probabilistic:** YES via optional 30M quantile head
- **Weaknesses:** Quantile collapse on long horizons. Covariate support is post-hoc.

**SCALE Suitability:** HIGH

### 2.3 Salesforce Moirai 2.0 (Aug 2025)

- **Size:** 2x faster, 30x smaller than Moirai 1.0-Large
- **Architecture:** Decoder-only with quantile loss, multi-token prediction
- **Benchmark:** 5th among 37 foundation models on GIFT-Eval
- **Moirai-MoE variant:** 17% improvement, 65x fewer activated parameters

**SCALE Suitability:** MODERATE-HIGH

### 2.4 TiRex (May 2025) — NOTABLE FOR SPARSE DATA

- **Size:** 35M params (smallest top performer)
- **Architecture:** xLSTM-based with Consecutive Patch Masking (CPM)
- **Key strength:** Excels at BOTH short AND long horizons simultaneously. Patch masking handles sparse/intermittent data specifically.
- **Probabilistic:** 9 quantile predictions
- **Weakness:** Limited covariate support

**SCALE Suitability:** HIGH (especially for sparse data handling)

### 2.5 IBM TTM (Tiny Time Mixers) — LIGHTWEIGHT CHAMPION

- **Size:** 1M params
- **Architecture:** TSMixer-based with adaptive patching
- **Key strength:** Runs natively on CPU. 65x faster fine-tuning, 54x faster inference vs LLM methods. Few-shot fine-tuning enables per-user personalization.
- **Weakness:** Not probabilistic out of the box. Smaller pretraining corpus.

**SCALE Suitability:** HIGH for CPU-constrained deployment

### 2.6 IBM FlowState (2025)

- **Size:** 9.1M params (smallest in GIFT-Eval top 10)
- **Architecture:** SSM encoder + functional basis decoder. Sampling-rate invariant.
- **Benchmark:** #2 on GIFT-Eval for zero-shot, outperforming models 20x its size

**SCALE Suitability:** MODERATE

### 2.7 Datadog Toto (May 2025)

151M params, decoder-only, Student-t mixture head. Strong on GIFT-Eval/BOOM. But trained on 43% observability data — wrong domain for finance.

**SCALE Suitability:** MODERATE

### 2.8 Nixtla TimeGPT-2

API-only, closed-source. 60% improvement over v1. But API dependency is unacceptable for 10K-100K users at scale.

**SCALE Suitability:** LOW

### 2.9 Lag-Llama

Probabilistic by design but univariate only, no covariates.

**SCALE Suitability:** LOW-MODERATE

---

## 3. Requirements Matrix

| Requirement | TFT | Chronos-2 | TimesFM 2.5 | TiRex | TTM |
|---|---|---|---|---|---|
| Probabilistic (quantiles) | NATIVE | NATIVE | YES (head) | YES (9Q) | Needs work |
| Interpretability | EXCELLENT | NONE | NONE | NONE | NONE |
| Static covariates | NATIVE | NATIVE | Partial | LIMITED | Fine-tune |
| Future covariates | NATIVE | NATIVE | Partial | LIMITED | Fine-tune |
| Sparse data (90 points) | POOR | GOOD | GOOD | EXCELLENT | GOOD |
| Per-user personalization | Per-user train | In-context | In-context/FT | Zero-shot | Few-shot FT |
| 30-day horizon | GOOD | GOOD | GOOD | GOOD | GOOD |
| CPU inference | SLOW | YES (28M) | YES | YES (35M) | EXCELLENT (1M) |
| Cold start (new users) | NO | YES | YES | YES | YES |
| Ecosystem maturity | EXCELLENT | GOOD | GOOD | NEW | GOOD |

---

## 4. Benchmark Results on Financial/Economic Data

- **M4 Competition:** Hybrid statistical+ML won. Combinations of methods dominated. On finance, simple ensembles often beat complex DL.
- **M5 Competition:** LightGBM ensembles dominated Walmart data. All top performers used pure ML approaches.
- **GIFT-Eval leaderboard (early 2026):** Chronos-2 > TiRex > TimesFM-2.5 > Toto > Moirai 2.0
- **fev-bench:** Chronos-2 leads with statistically significant margins. TiRex at 86.7% win rate, TimesFM-2.5 at 82.1%.
- **DLinear debate:** Simple linear model beat Transformers on Exchange Rate by 40%, but subsequent work showed this was partly due to unfair experimental setup. Consensus: Transformers ARE effective, but the gap is domain-dependent.

---

## 5. Personal Finance / Consumer Spending Papers

Direct research on Transformers for personal finance forecasting is **scarce**. The closest related work involves financial time series forecasting for markets/trading, public expenditure prediction, and consumer spending macroeconomic analysis. No published work applies modern foundation models (Chronos-2, TimesFM) to per-user consumer spending prediction. This is an open area — SCALE would be pioneering.

---

## 6. Modern Optimizers Beyond AdamW

### 6.1 Muon (MomentUm Orthogonalized by Newton-Schulz)

**What it is:** A matrix-structured, spectrum-aware optimizer that orthogonalizes gradients via Newton-Schulz iterations (an efficient SVD approximation). It applies momentum before orthogonalization and uses a quintic polynomial Newton-Schulz iteration that runs stably in bfloat16.

**How it works:** Takes SGD-momentum updates for 2D parameter matrices, then post-processes them by replacing each update with its nearest semi-orthogonal matrix. The tuned NS coefficients are (3.4445, -4.7750, 2.0315), requiring only 5 iterations. For 1D/embedding/output layers, AdamW is still used.

**Benchmarks vs AdamW:** On NanoGPT speedrunning, Muon is 1.35x faster. On a 1.5B transformer, it reached GPT-2 XL performance in 10 8xH100-hours vs 13.3 hours for AdamW. FLOP overhead is only 0.5-0.7%. In the comprehensive "Fantastic Pretraining Optimizers" benchmark (2025), Muon achieved ~1.4x speedup at 0.1B scale over well-tuned AdamW.

**Suitability for SCALE:** STRONG CANDIDATE. Muon excels at small-to-medium model scales where the 1.4x speedup is most pronounced. The overhead is negligible. However, it only applies to 2D weight matrices — embedding layers and 1D parameters still need AdamW. For a 1M-50M time-series transformer, this is an excellent choice for the attention and FFN layers.

### 6.2 MuonClip (Kimi/Moonshot AI, 2025)

**What it is:** An extension of Muon developed by Moonshot AI for their Kimi K2 model. After every update, MuonClip rescales the query and key weight matrices to keep raw attention values in a safe numerical range, preventing logit explosions.

**How it works:** Adds a clipping/rescaling step after Muon's orthogonalization to prevent the runaway growth of attention logits that can crash training at scale. QK-Clip: if max attention score exceeds threshold tau=100, rescales W_q by eta^0.5 and W_k by eta^0.5 where eta = tau/S_max.

**Benchmarks:** Achieved 1.75x and 1.38x convergence speedup over Muon at different model sizes. Enabled K2's pre-training on 15.5 trillion tokens with zero loss spikes.

**Suitability for SCALE:** POSSIBLY OVERKILL. MuonClip was designed for trillion-parameter scale stability. At 1M-50M parameters, vanilla Muon should be stable enough. However, if you encounter attention logit instability during training, MuonClip's rescaling trick is worth adopting as a simple fix.

### 6.3 SOAP (Shampoo + Adam in Preconditioner's Eigenbasis)

**What it is:** A second-order optimizer from Harvard that runs Adam in the eigenbasis provided by Shampoo's preconditioner. It has only one extra hyperparameter over Adam: the preconditioning frequency.

**How it works:** SOAP establishes a formal connection between Shampoo (with 1/2 power) and Adafactor, showing Shampoo is equivalent to running Adafactor in its preconditioner's eigenbasis. SOAP then replaces Adafactor with full Adam for better moment estimation, continually updating the running average of the second moment in the current (slowly changing) coordinate basis.

**Benchmarks vs AdamW:** Reduces iterations by over 40% and wall-clock time by over 35% compared to AdamW. ~20% improvements over Shampoo in both metrics. Tested on 360M and 660M models.

**Suitability for SCALE:** GOOD CANDIDATE but with caveats. SOAP is one of the top-performing matrix-based optimizers. However, it has higher memory overhead (storing preconditioner matrices) and the eigendecomposition step adds wall-clock cost. For a 1M-50M model, the memory overhead is manageable, but the wall-clock benefit may be smaller since Muon achieves similar speedups with less complexity.

### 6.4 Kron (PSGD - Preconditioned Stochastic Gradient Descent)

**What it is:** A second-order optimizer using Kronecker-factored preconditioners with Lie group geometry. It approximates curvature information via either Hessian-based or whitening-based (gg^T) preconditioners.

**How it works:** Uses Kronecker factorization of the preconditioner matrix and updates it using Lie group operations. Has fewer hyperparameters than Adam and can generally act as a drop-in replacement.

**Benchmarks vs AdamW:** In the "Fantastic Pretraining Optimizers" benchmark, Kron was among the top performers alongside Muon and SOAP, consistently outperforming AdamW across regimes.

**Suitability for SCALE:** VIABLE. Kron is a solid choice with good theoretical foundations. The Kronecker factorization is efficient for small-to-medium models. However, the implementation is less mature than Muon or SOAP in terms of community adoption.

### 6.5 MARS (Make vAriance Reduction Shine)

**What it is:** A unified optimization framework reconciling preconditioned gradient methods with variance reduction via scaled stochastic recursive momentum. Accepted at ICML 2025.

**How it works:** Applies variance reduction techniques (normally used in convex optimization) to the large-model training setting by combining them with adaptive preconditioning (AdamW-style or Lion-style). Core formula: c_t = grad + gamma*(beta1/(1-beta1))*[grad(x_t) - grad(x_{t-1})]. Three variants: MARS-AdamW, MARS-Lion, MARS-Shampoo. MARS-approx (using previous step's gradient) works nearly as well with no extra compute.

**Benchmarks vs AdamW:** On GPT-2 Small, MARS-AdamW achieves 45.93 vs 45.72 for AdamW across 9 benchmarks. On GPT-2 XL, MARS reaches 56.52 HellaSwag accuracy vs AdamW's 53.93 after 50B tokens. On GPT-2 770M: reached val loss 2.58 in 27B tokens vs 50B for AdamW.

**Suitability for SCALE:** MODERATE. MARS is a scalar-based optimizer (not matrix-based), so it underperforms Muon/SOAP/Kron. The improvement over AdamW is modest (especially at small scale). Consider it if you want variance reduction benefits without switching to matrix-based methods.

### 6.6 Schedule-Free Optimizer (Meta, 2024)

**What it is:** An approach from Meta that eliminates learning rate schedules entirely by unifying scheduling and iterate averaging. No additional hyperparameters over standard optimizers with momentum.

**How it works:** Develops a theory that unifies scheduling and iterate averaging. Instead of decaying the learning rate, the optimizer maintains a sequence of iterates and combines them through a theoretically-motivated averaging scheme. Formulas: y_t = (1-beta)*z_t + beta*x_t for gradient eval; z_{t+1} = z_t - gamma*grad(y_t); x_{t+1} averaged iterates for evaluation. Eliminates LR schedule entirely. Drop-in replacement for AdamW.

**Benchmarks:** Won the MLCommons 2024 AlgoPerf Algorithmic Efficiency Challenge Self-Tuning track. Achieves state-of-the-art performance across convex to large-scale deep learning problems.

**Suitability for SCALE:** STRONG CANDIDATE. The elimination of learning rate scheduling is a major practical benefit for per-user training where you may not know optimal training duration in advance. Available as `schedulefree` on PyPI.

### 6.7 Prodigy (Adaptive Learning-Rate-Free)

**What it is:** A parameter-free optimizer that automatically estimates the distance to the solution (D), eliminating the need for learning rate tuning. Published at ICML 2024.

**How it works:** Modifies the D-Adaptation method by improving convergence by a factor of O(sqrt(log(D/d_0))). Sets learning rate to 1.0 and adapts it automatically based on gradient signals.

**Benchmarks vs AdamW:** Reaches test accuracy close to hand-tuned Adam across 12 logistic regression benchmarks, VGG11, ResNet-50, ViT, LSTM, DLRM, and GPT training. Recommended optimizer for HuggingFace Diffusers DreamBooth LoRA training.

**Suitability for SCALE:** EXCELLENT for per-user training. When training per-user models, you cannot hand-tune learning rates for each user. Prodigy's automatic LR estimation is ideal. The default lr=1.0 works across architectures. Consider combining Prodigy with Schedule-Free for maximum automation. Available as `prodigyopt` on PyPI.

### 6.8 AdEMAMix (Apple, 2024)

**What it is:** A simple modification of Adam that uses a mixture of two exponential moving averages — a fast EMA for recent gradients and a slow EMA retaining information from tens of thousands of steps earlier.

**How it works:** Standard Adam uses one EMA for the first moment. AdEMAMix maintains two: a fast-decaying EMA (beta1=0.9, recent gradients) and a very slow-decaying EMA (beta3=0.9999, old gradients). Update = (m1/bias_correction + alpha*m2) / (sqrt(v) + eps). This allows the optimizer to benefit from much older gradient information. Significantly reduces forgetting.

**Benchmarks vs AdamW:** When training a 1.3B language model on RedPajama, AdEMAMix matched AdamW performance trained on 197B tokens with only 101B tokens — a ~49% reduction in token usage (+95% efficiency).

**Suitability for SCALE:** PROMISING but needs long training. AdEMAMix's benefit comes from leveraging old gradients, which requires long training runs (hundreds of thousands of steps). For per-user models with limited data, the slow EMA may not accumulate enough history to help. Better suited for cohort-level models trained on more data. The slow EMA preserving long-term gradient memory is ideal for financial patterns.

### 6.9 Lion (Google Brain, 2023)

**What it is:** An optimizer discovered through automated program search (AutoML/genetic algorithms). Uses only the *sign* of the gradient for updates, making it memory-efficient (stores only momentum, not second moments).

**How it works:** Applies the same magnitude update to each parameter via the sign operation. This is fundamentally different from Adam-family optimizers that scale updates by inverse root of second moments.

**Benchmarks vs AdamW:** Boosts ViT ImageNet accuracy by up to 2%. Better FID scores in diffusion models with 2.3x reduced training compute. Matches or slightly outperforms Adam on language perplexity.

**Suitability for SCALE:** GOOD for memory-constrained scenarios. Lion requires 50% less optimizer memory than Adam (no second moment buffer). However, it needs 3-10x smaller learning rate and 3-10x larger weight decay, which complicates hyperparameter transfer. For our small models, memory is unlikely to be a bottleneck, so Lion's main advantage is less relevant.

### 6.10 Sophia (Stanford, 2023)

**What it is:** A lightweight second-order optimizer using diagonal Hessian estimation. It divides gradients by estimated Hessian diagonals with element-wise clipping.

**How it works:** Estimates diagonal Hessian only every k iterations (e.g., every 10 steps), adding negligible average per-step overhead. The clipping controls worst-case update size in non-convex landscapes.

**Benchmarks vs AdamW:** 2x speedup on GPT models (125M to 1.5B) in steps, compute, and wall-clock time. A 540M model trained by Sophia matches a 770M model trained by AdamW.

**Suitability for SCALE:** STRONG CANDIDATE. Sophia's per-parameter curvature adaptation is excellent for heterogeneous parameter landscapes common in time-series transformers (where attention weights and FFN weights have very different curvatures). The infrequent Hessian estimation makes it practical. At 1M-50M parameters, the Hessian computation is cheap.

### 6.11 Adan (Adaptive Nesterov Momentum)

**What it is:** Incorporates Nesterov acceleration into adaptive gradient methods without the extra forward pass normally required. Published in IEEE TPAMI 2024.

**How it works:** Reformulates Nesterov acceleration into a "Nesterov Momentum Estimation" (NME) that avoids computing gradients at the extrapolation point. Uses NME to estimate both first and second moments.

**Benchmarks vs AdamW:** Sets new SoTAs on ResNet, ConvNext, ViT, Swin, MAE, DETR, GPT-2. Can use half the training epochs of SoTA optimizers. Tolerant to batch sizes from 1k to 32k.

**Suitability for SCALE:** GOOD. Adan's fast convergence (half epochs) is attractive for per-user training where compute budgets are limited. However, it uses two extra buffers over Adam, increasing memory usage. At our model scale this is fine.

### 6.12 Cautious Optimizers (C-AdamW, C-Lion)

**What it is:** A one-line modification to any momentum-based optimizer that masks out updates where momentum and gradient signs disagree. Published November 2024.

**How it works:** Before applying the update, checks if the sign of the momentum component matches the sign of the current gradient. If they disagree, that component's update is zeroed out. If they agree, the component is scaled by alpha > 1.

**Benchmarks:** C-AdamW achieves 1.47x speedup on LLaMA 1B; C-Lion achieves 1.28x. Virtually zero overhead.

**Suitability for SCALE:** EXCELLENT as an add-on. This is a free lunch — literally one line of code added to any existing optimizer. Apply C-AdamW, C-Muon, or C-Sophia as a wrapper. No downside, consistent improvement.

### 6.13 Grokfast (2024)

**What it is:** An optimizer augmentation that accelerates "grokking" (delayed generalization after memorization) by amplifying slow-varying gradient components.

**How it works:** Spectrally decomposes parameter trajectories into fast-varying (overfitting) and slow-varying (generalizing) components. Amplifies the slow components via frequency-domain filtering.

**Benchmarks:** 50x+ acceleration of grokking phenomenon. Applicable to images, language, and graph tasks.

**Suitability for SCALE:** NICHE but interesting. If your per-user models show the grokking pattern (good training loss but delayed test improvement), Grokfast could help. For standard time-series forecasting, other optimizers provide more reliable gains.

### 6.14 Mano (Manifold Normalized Optimizer, Feb 2026)

**What it is:** The newest optimizer in this space. Uses manifold normalization on the Oblique manifold, requiring no spectral preconditioning.

**Benchmarks:** 1.75x and 1.38x convergence speedup over Muon. The Oblique manifold yields the shortest geodesic distance compared to Sphere and Stiefel manifolds.

**Suitability for SCALE:** PROMISING but very new. Only published February 2026, so limited community validation. If early results hold up, it could supersede Muon as the go-to matrix-based optimizer.

### Optimizer Recommendation Summary

| Optimizer | Speedup vs AdamW | Memory Overhead | Complexity | Recommendation for 1M-50M TS model |
|---|---|---|---|---|
| **Muon** | 1.3-1.4x | Low | Medium | **Primary choice** for attention/FFN layers |
| **Sophia** | ~2x in steps | Low | Medium | **Strong alternative** — curvature adaptation |
| **Schedule-Free AdamW** | Competitive | None | Low | **Best for unknown training duration** |
| **Prodigy** | Matches tuned Adam | None | Low | **Best for per-user training** (no LR tuning) |
| **C-AdamW** | 1.47x | None | Trivial | **Always use as wrapper** on any optimizer |
| SOAP | 1.35-1.4x | High | High | Good but complex |
| MARS | 1.05-1.1x | Low | Medium | Marginal improvement |
| AdEMAMix | ~2x tokens | Low | Low | Needs long runs |
| Lion | Competitive | 50% less | Low | Memory not a concern at our scale |
| Adan | ~2x epochs | Higher | Medium | Good convergence speed |

**Concrete recommendation:** Use Muon (for 2D weight matrices) + AdamW (for embeddings/1D params) with the Cautious wrapper applied to both. Use Prodigy for per-user models where LR tuning is impractical. Use Schedule-Free AdamW if training duration varies across users/cohorts.

---

## 7. Learning Rate Schedules

### 7.1 Cosine Annealing with Warmup

Linear warmup for ~1-2% of steps, then cosine decay to near-zero. The standard schedule for LLM pre-training.

**Pros:** Simple, well-understood, packs several desirable mathematical properties. Good for fixed-length training runs.
**Cons:** Requires knowing total training steps in advance. Not suitable for continuous/variable-length training.
**For SCALE:** Good default for cohort models with known training budgets. Not ideal for per-user models where training length varies.

### 7.2 Warmup-Stable-Decay (WSD)

Three phases: linear warmup (1-2% of steps), constant LR plateau (60-80%), then rapid decay (10-25%).

**Pros:** Does not require knowing total training budget upfront. During the constant phase, loss is higher than cosine, but during decay it drops sharply, often reaching better final performance. Supports branching: maintain the constant-LR "trunk" indefinitely and branch off with decay to create checkpoints.
**Cons:** The plateau phase can feel wasteful. Requires choosing when to start decay.
**For SCALE:** RECOMMENDED for cohort models. The branching capability is excellent — train a base model at constant LR, then spawn per-user fine-tuning branches with short decay phases.

### 7.3 WSM (Warmup-Stable-Merge, 2025)

An evolution of WSD that replaces online LR decay with offline checkpoint merging. Trains at constant LR, then merges recent checkpoints with theoretically-derived weights.

**Performance:** +3.5% MATH, +2.9% HumanEval, +5.5% MMLU-Pro over classical WSD.
**For SCALE:** INTERESTING. Eliminates the need for a decay phase entirely. You can train at constant LR and merge checkpoints offline. The merge duration is the most critical factor.

### 7.4 1-Cycle Policy / Cyclic Learning Rates

Ramps LR from low to high and back down in a single cycle, with inverse-cyclic momentum. Enables "super-convergence" — reaching high accuracy in fewer epochs.

**For SCALE:** GOOD for fine-tuning. When fine-tuning per-user models from a cohort checkpoint, 1-cycle policy can achieve convergence in very few epochs. Use LR range test to find max LR (divide by 10 for min).

### 7.5 Schedule-Free (Meta, 2024)

Eliminates the schedule entirely (see optimizer section 6.6 above).

**For SCALE:** STRONG CANDIDATE for per-user training. No schedule to tune, no training duration to specify. Combine with Prodigy for fully automated LR + schedule.

### Schedule Recommendation

- **Cohort pre-training:** WSD (warmup 1-2%, stable 70%, decay 20%) or cosine annealing
- **Per-user fine-tuning from cohort checkpoint:** 1-cycle policy (5-20 epochs) or Schedule-Free
- **Per-user training from scratch:** Schedule-Free + Prodigy (fully automated)

---

## 8. Training Techniques for Small Models

### 8.1 Knowledge Distillation from Foundation Models

**State of the art (2025):**

- **DistilTS framework** is the first distillation framework specifically for time-series foundation models. Achieves comparable performance while reducing parameters by up to 1/150 and accelerating inference by up to 6000x.
- **TimeKD** uses privileged knowledge distillation (PKD), leveraging both correlation and feature distillations to transfer representations from LLM-empowered teacher models to lightweight student models.
- Key techniques: soft label distillation (match teacher's output distribution), feature distillation (match intermediate representations), and correlation distillation (match attention patterns).

**Recommendation:** Distill from a time-series foundation model like Time-MoE-50M (available on HuggingFace) or Chronos into your per-user model. Use soft labels from the foundation model as additional training signal. This gives your small model the benefit of patterns learned from massive pre-training data.

### 8.2 Curriculum Learning for Time Series

**Best practices (2024-2025):**

- **Sort by complexity:** Start with clean, low-noise time series segments; progressively introduce noisy, regime-switching periods.
- **Frequency-cropping:** Early stages reveal only low spatial frequencies; later stages restore full-spectrum detail.
- **Progressive sequence length:** Start with short forecast horizons (e.g., 7 days), progressively increase to full horizon (e.g., 90 days).
- **Augmentation schedules:** Progressively increase data augmentation strength throughout training.
- **Model growing:** Optionally start with a shallow/thin model and progressively increase depth/width.

**Recommendation for financial time series:** (1) Start with smooth, regular spending patterns. (2) Introduce seasonal variations. (3) Add irregular/bursty transactions. (4) Finally train on the full distribution including anomalies.

### 8.3 Mixed Precision Training

**Key findings (2024):**

- **BF16 is strongly preferred** over FP16 for training. BF16's 8 exponent bits match FP32's dynamic range, virtually eliminating overflow/underflow issues.
- **FP16 risks:** Gradients can underflow to zero below 6.1x10^-5, halting learning for affected parameters. Requires loss scaling to mitigate.
- **DeepSeek's innovation:** Fine-grained FP8 quantization with blockwise (128x128) and tilewise (1x128) scaling achieves <0.25% accuracy loss vs BF16. But this requires Hopper-class GPUs.
- **Accumulation:** Always accumulate in FP32 regardless of compute precision.

**Recommendation:** Use BF16 mixed precision (available on Ampere+ GPUs). It is a free speedup with virtually no accuracy cost. For CPU-only or older GPU training, use FP32. FP8 is not worth the complexity at our model scale.

### 8.4 Gradient Accumulation Strategies

**Surprising recent finding (2025):** A paper from 2025 challenges the conventional wisdom that small batch sizes require gradient accumulation:

- Small batch sizes train stably and are more robust to hyperparameter choices
- Small batches achieve equal or better per-FLOP performance than larger batches
- Even vanilla SGD without momentum works with small batches

**Recommendation:** Use the smallest batch size that maximizes GPU throughput (likely 32-128 for 1M-50M parameter models). Avoid gradient accumulation unless training on multiple GPUs. If you must simulate larger batches, hold the second-moment half-life fixed in terms of tokens (not steps).

### 8.5 Early Stopping Criteria

**What to monitor:**

- **Primary:** Validation loss (typically MSE or MAE for forecasting)
- **Secondary:** Downstream metrics (e.g., forecast accuracy at specific horizons)
- **Advanced (2024):** Spectral signatures of convergence — training can be demarcated into three stages: structural exploration, heavy-tailed structure stabilization, and convergence saturation

**Patience settings:**

- For per-user fine-tuning (short runs): patience = 3-5 evaluation intervals
- For cohort pre-training (long runs): patience = 10-20 evaluation intervals
- Use exponential moving average of validation loss rather than raw values to avoid premature stopping from fluctuations

**Recommendation:** Monitor validation loss with EMA smoothing, patience=5 for per-user, patience=15 for cohort. Also track per-horizon forecast accuracy as a secondary signal.

### 8.6 Data Augmentation for Time Series

| Technique | Description | Best for |
|---|---|---|
| **Jittering** | Add Gaussian noise to each time step | Robustness to measurement noise |
| **Scaling** | Multiply entire series by random factor | Robustness to magnitude changes |
| **Magnitude Warping** | Multiply by smooth cubic spline | Preserves shape, varies magnitude |
| **Window Slicing** | Crop to 90% length at random offset, interpolate back | Data diversity |
| **Time Warping** | Smooth non-linear distortion of time axis | Robustness to speed changes |
| **Window Warping** | Compress/expand random window segments | Local temporal variability |
| **Permutation** | Randomly shuffle fixed-length segments | Reduce order dependence |
| **Rotation** (multivariate) | Rotate feature space | Cross-feature robustness |

**Recommendation for financial time series:**

1. **Jittering** (sigma=0.01-0.03 of series std) — always apply
2. **Scaling** (factor 0.8-1.2) — simulates income/spending magnitude variations
3. **Magnitude Warping** — simulates gradual spending habit changes
4. **Window Slicing** — creates more training samples from limited per-user data
5. **Avoid Permutation** — temporal order is critical for financial data

### 8.7 Regularization

**Dropout:**

- Standard: 0.1-0.2 for pre-training, 0.3-0.5 for fine-tuning on small per-user datasets
- **AttentionDrop (2024):** Directly perturbs attention distributions; variants include hard attention masking that zeroes out top-k attention logits per query to encourage diverse context usage
- **Dynamic Dropout (2024):** Adjusts dropout rate based on training epoch or validation loss

**Weight Decay:**

- Standard: 0.01-0.1 (higher for small datasets)
- With AdamW, weight decay is decoupled from the gradient update
- For per-user fine-tuning: use 0.05-0.1

**Spectral Normalization:**

- **sigmaReparam** reparametrizes all linear layers with spectral normalization + learned scalar
- Provides stability without warmup, weight decay, or adaptive optimizers
- Prevents attention entropy collapse (pathologically concentrated attention scores)

**Recommendation:** Dropout 0.1 for cohort pre-training, 0.3 for per-user fine-tuning. Weight decay 0.01-0.05 for pre-training, 0.05-0.1 for fine-tuning. Consider AttentionDrop as an additional regularizer for small user datasets. Apply sigmaReparam if you encounter training instability.

---

## 9. Architecture Innovations from Open-Source Models

### 9.1 Grouped Query Attention (GQA) vs Multi-Head Attention (MHA)

GQA partitions query heads into groups that share key-value heads. MQA uses 1 KV head for all queries; GQA uses G groups (between 1 and H). Reduces KV cache memory at inference. Llama 2/3 uses GQA with 8 KV heads across all model sizes.

**For SCALE:** MARGINAL benefit. GQA's primary advantage is inference memory/speed. For a 1M-50M model, KV cache is already small. MHA is fine. If you want a future-proof architecture, use GQA with 2-4 groups as a mild efficiency gain. Do not use MQA (single KV head) — quality drops too much at small scale.

### 9.2 RoPE (Rotary Position Embeddings) for Temporal Data

Encodes absolute position via rotation matrices that naturally induce relative position dependency in attention scores. Key properties: sequence length flexibility, decaying inter-token dependency with distance, and smooth extrapolation beyond training horizon.

**For time series specifically:**

- RoMAE (Rotary Masked Autoencoders) with continuous-coordinates RoPE outperforms time-series-specialized architectures on irregular and multivariate temporal benchmarks
- Translation invariance: All outputs remain invariant under time shifts, enabling flexible re-zeroing
- Continuous time support: Can handle irregular time series (transactions at arbitrary times)

**For SCALE:** STRONGLY RECOMMENDED. Financial transactions are irregularly spaced. RoPE with continuous coordinates (encoding actual timestamps rather than position indices) naturally handles this. It also supports extrapolation to longer sequences than seen in training.

### 9.3 SwiGLU / GeGLU Activation Functions

Gated Linear Unit variants where the sigmoid gate is replaced with Swish (SwiGLU) or GELU (GeGLU). Used in Llama, Mistral, PaLM, and Apple's models. Consistently better perplexity than ReLU or GELU. The gating mechanism provides better gradient flow and expressiveness.

**Implementation note:** To maintain parameter count parity with standard FFN, set hidden_dim to ~2/3 of what you'd use with ReLU (since SwiGLU has 3 weight matrices vs 2).

**For SCALE:** RECOMMENDED. SwiGLU is one of the highest-ROI architectural changes. Simple to implement, consistent improvement. Use SwiGLU for all FFN layers.

### 9.4 RMSNorm vs LayerNorm

RMSNorm drops the mean-centering and bias of LayerNorm, normalizing only by root-mean-square. 7-64% training speedup with no performance loss. 2024 research showed that mechanistically, RMSNorm-based models naturally produce hidden representations orthogonal to the uniform vector, making LayerNorm's mean removal inconsequential.

**Emerging alternative:** Peri-LN (2025) applies LN both before and after each module, yielding both fast convergence and strong stability at extreme depths.

**For SCALE:** RECOMMENDED. Use pre-RMSNorm (RMSNorm before attention and FFN, as in Llama). At 1M-50M parameters the speed difference is small, but RMSNorm is simpler and has become the standard.

### 9.5 Flash Attention

IO-aware exact attention that tiles the computation to reduce HBM reads/writes. FlashAttention-3 (2024) optimized for H100. Flash Attention's benefit scales with sequence length, not model size. Even for a 1M parameter model, if sequences are long (e.g., 512-4096 time steps), Flash Attention helps.

**For SCALE:** USE if sequence length > 256. For financial time series with long context windows (e.g., 1 year of daily transactions = 365 tokens, or transaction-level = thousands), Flash Attention provides meaningful speedup. It's a standard PyTorch feature now (`torch.nn.functional.scaled_dot_product_attention` auto-selects Flash Attention).

### 9.6 Mixture of Experts (MoE) for Small Scale

**Recent developments:**

- **Time-MoE (ICLR 2025 Spotlight):** Specifically designed for time series forecasting. Decoder-only with MoE, supports arbitrary prediction horizons, context up to 4096. Models available at 50M on HuggingFace.
- **OLMoE:** 7B total / 1B active across 64 experts, outperforming dense models with 6-7x more compute.
- **Moirai-MoE (ICML 2025):** MoE for time-series foundation models. 17% improvement over dense equivalent. Outperforms Chronos/TimesFM with 65x fewer active params.

Memory concern: All experts must be in memory even though only top-k are active. At 50M parameters total with 8 experts, each expert is ~6M parameters — very manageable.

**For SCALE:** PROMISING for multi-user/multi-pattern models. MoE can route different financial behavior patterns (regular spenders, irregular income, seasonal workers) to specialized experts. Consider a small MoE (4-8 experts, top-2 routing) for cohort models. For per-user models, dense architecture is simpler and sufficient.

### 9.7 Multi-Head Latent Attention (MLA, DeepSeek)

Compresses KV caches into low-rank latent vectors (dim 512 for a 7168 hidden dim model). Only the compressed vector stored in KV cache. Up-projects to full K, V on the fly. Result: 93.3% KV cache reduction, 5.76x throughput. Strictly more expressive than GQA at equal cache size. Uses decoupled RoPE (separate small vectors carry positional info).

**For SCALE:** NOT NEEDED at our scale. MLA's benefit is KV cache compression for inference on massive models. At 1M-50M parameters, the KV cache is tiny. The added complexity of compression/decompression is not justified.

### 9.8 PatchTST / iTransformer Architecture Patterns

**PatchTST:** Segments time series into patches (subseries tokens). Channel-independent (each feature shares weights). Encoder-only. 21% MSE reduction. Self-supervised pre-training (mask patches) works excellently. Foundational technique for any time-series transformer.

**iTransformer:** Inverts the token dimension — treats each *variable* as a token across time. Attention discovers cross-feature relationships. FFN learns temporal patterns per variate. Highly effective when variable interactions matter.

**For SCALE:** Consider **patching** as a tokenization strategy — e.g., group 7 days of transactions into one patch token. This reduces sequence length and captures local patterns. Channel-independence (PatchTST style) or variable-as-token (iTransformer style) depends on whether your features interact strongly.

### 9.9 Mamba / State Space Models

**Mamba:** Selective SSM, O(n) complexity, 5x throughput vs transformers. Mamba-3B matches Transformer-6B. Multiple time-series adaptations exist (S-Mamba, TSMamba, MambaStock).

### 9.10 Hybrid Mamba+Attention

7:1 Mamba:Attention ratio (as in Jamba). Use attention for critical local correlations, Mamba for long-range context. The most promising direction for financial forecasting.

### 9.11 Differential Transformer (ICLR 2025)

Attention = diff of two softmax maps. Cancels noise. Good for noisy financial data.

### 9.12 xLSTM

mLSTM variant is fully parallelizable with matrix memory. Alternative to Mamba. Used in TiRex foundation model.

### 9.13 Multi-Token Prediction (DeepSeek V3, Meta)

Predicts one additional future token at each position. Uses sequential MTP modules. MTP loss weight 0.3 (first 10T) then 0.1. Enables speculative decoding at inference (1.8x speedup, >80% acceptance). Very relevant for financial forecasting: predict multiple future steps simultaneously, densifying training signal.

### 9.14 LoRA for Per-User Adaptation

Train base model on general financial data. Per-user: rank 4-8 LoRA adapters on attention projections. Adapters are tiny (few KB). Multiple users served efficiently.

---

## 10. Open-Source Model Deep Dives

### 10.1 Kimi K2 (Moonshot AI, July 2025)

**Architecture:** 1.04T total params, 32.6B active, 61 layers, hidden dim 7168, 64 attention heads, MLA attention, 384 experts (8 active per token), expert hidden dim 2048. Trained on 15.5T tokens with zero loss spikes.

**MuonClip Optimizer — key innovation.** Muon runs SGD + Nesterov momentum, then orthogonalizes each 2D parameter update via Newton-Schulz iteration (nearest orthogonal matrix = steepest descent under spectral norm). Achieves ~2x compute efficiency vs AdamW. QK-Clip prevents attention logit explosion: if max attention score exceeds threshold tau=100, rescales W_q by eta^0.5 and W_k by eta^0.5 where eta = tau/S_max.

**Training recipe:** LR 2e-4 constant for 10T tokens (500-step warmup), cosine decay to 2e-5 over 5.5T tokens, annealing at 2e-5 to 7e-6. Weight decay 0.1, batch 67M tokens.

### 10.2 Kimi K2.5 (January 2026)

Introduced Agent Swarm with PARL (Parallel-Agent RL): trainable orchestrator + frozen subagents. Key finding: early fusion of multiple modalities outperforms late-stage injection. Visual RL improves text performance, suggesting cross-modal training transfer. The "Toggle" technique alternates budget-limited and standard scaling phases during RL, reducing output tokens by 25-30% with negligible quality impact.

### 10.3 DeepSeek-V3 (Dec 2024)

**Multi-head Latent Attention (MLA):** Compresses KV into low-rank latent vector (dim 512 for 7168 hidden dim). 93.3% KV cache reduction, 5.76x throughput. Strictly more expressive than GQA at equal cache size. Uses decoupled RoPE.

**Auxiliary-loss-free load balancing for MoE:** Adds learnable bias per expert to routing scores (selection only, not gating values). Bias adjusted dynamically — decrease if overloaded, increase if underloaded. No interference gradients.

**Multi-Token Prediction (MTP):** Predicts one additional future token at each position. Sequential MTP modules. MTP loss weight 0.3 (first 10T) then 0.1. Enables speculative decoding at inference (1.8x speedup, >80% acceptance).

**FP8 training framework:** Block-wise quantization (1x128 tiles for activations, 128x128 for weights). <0.25% accuracy loss vs BF16.

**Training recipe:** AdamW (beta1=0.9, beta2=0.95, wd=0.1). LR: warmup to 2.2e-4 over 2K steps, constant 10T tokens, cosine decay to 2.2e-5 over 4.3T, then constant 7.3e-6. Batch ramp 3072 to 15360. Gradient clip 1.0.

### 10.4 Meta / Llama Research

**GQA (Llama 3):** Multiple query heads share K,V projections. Simpler than MLA but less expressive.

**RoPE:** Encodes position as rotation in cosine-sine planes. Parameter-free, relative, scales well. Natural for encoding temporal distance in time series.

**QK-Norm:** Applies RMSNorm to Q and K before attention. Prevents logit drift. Used by every major 2025 model. Zero-cost stability improvement.

**Llama 4 iRoPE:** Interleaves 3 RoPE layers + 1 NoPE (No Position) layer. RoPE layers focus on local patterns; NoPE layers attend equally to all positions for global connections. Brilliant for time series where you need both local pattern recognition and long-range dependency capture. MoE: 128 routed experts + 1 shared, top-1 routing.

**Muon Optimizer (Moonshot + UCLA, Feb 2025):** Scaled Muon to 16B MoE via: (1) adding weight decay, (2) per-parameter update scale adjustment. Distributed with ZeRO-1 style. ~2x efficiency vs AdamW. Open-sourced as "Moonlight" on GitHub.

### 10.5 Mistral / Mixtral

**Sliding Window Attention:** Limits receptive field to fixed window (e.g., 4096). Memory O(n*w) instead of O(n^2). At layer k, effective field = k*w. Relevant for long time series.

**Sparse MoE:** 8 experts, top-2, 47B total / 13B active. 6x faster than Llama 2 70B. Simple linear+softmax gating.

### 10.6 Google Time Series Research

**TimesFM (ICML 2024):** Decoder-only transformer, patch-based tokenization, 200M params pretrained on 100B time points. Zero-shot forecasting across domains.

**TSMixer (TMLR 2023):** All-MLP — alternates time-mixing and feature-mixing MLPs. Parameter growth O(L+C) not O(L*C). Outperforms PatchTST, Autoformer, DeepAR, TFT. Extremely parameter-efficient for small models.

**TFT (Google 2021):** Handles static covariates + known future inputs + exogenous series. Variable selection networks for feature importance. Interpretable attention (shared Values matrix). Directly addresses financial forecasting input types.

### 10.7 Apple Research

**AdEMAMix Optimizer:** Two EMAs — fast (beta1=0.9, recent gradients) and slow (beta3=0.9999, old gradients). Update = (m1/bias_correction + alpha*m2) / (sqrt(v) + eps). 1.3B model on 101B tokens matches AdamW on 197B tokens (+95% efficiency). Significantly reduces forgetting. The slow EMA preserving long-term gradient memory is ideal for financial patterns.

---

## 11. Quantization and Efficiency

For 1M-50M models: Quantization is **NOT relevant for training** (model fits in FP32 easily). **IS relevant for deployment** — INT8 via ONNX Runtime enables browser/mobile inference. ONNX gives 2-4x speedup over PyTorch with graph optimizations.

---

## 12. Recommendations Summary

### Model Selection Decision

| Component | Choice | Reasoning |
|---|---|---|
| Cold-start engine (Tier 1) | **Chronos-2-Small (28M)** | #1 on all benchmarks, zero-shot, native covariates, CPU inference, Apache 2.0 |
| Personalized engine (Tier 2) | **TFT-Hybrid (12-15M)** | Only model with native interpretability + upgraded with modern innovations |
| Fallback | TTM (1M) | If extreme lightweightness is needed |

### Architecture Innovations to Integrate

**Tier 1 (must-have):**

| Innovation | Source | Effort |
|---|---|---|
| SwiGLU FFN | Llama/PaLM/Mistral | ~2 hours |
| RMSNorm | All 2025 models | ~1 hour |
| QK-Norm | Universal 2025 | ~30 min |
| RoPE (continuous) | Llama / RoMAE | ~4 hours |
| Muon optimizer | UCLA/Moonshot | ~3 hours |
| Cautious wrapper | Nov 2024 paper | ~5 min |
| LoRA adapters | Microsoft | ~4 hours |
| Knowledge distillation | DistilTS / TimeKD | ~3 hours |

**Tier 2 (after v1):** Multi-Token Prediction, Differential Attention, Mamba layers, iRoPE, Prodigy optimizer

**Tier 3 (future):** MoE routing, Auxiliary-loss-free load balancing, AdEMAMix, Spectral normalization

### Training Recipe

**Cohort pre-training:** Muon+AdamW (Cautious), WSD schedule, BF16, batch 32-128, dropout 0.1, patience 15

**Per-user fine-tuning:** Prodigy (lr=1.0), 1-cycle or Schedule-Free, dropout 0.3, patience 5, LoRA rank 4-8

### Key Risk

Before committing, benchmark Chronos-2 against TFT on SCALE's actual transaction data. Foundation models can underperform on domain-specific distributions not well represented in pretraining. A/B testing on real user data should be the final decision gate.

---

## 13. Sources

### Model Papers

- Chronos-2: <https://www.amazon.science/blog/introducing-chronos-2-from-univariate-to-universal-forecasting> (Oct 2025)
- TFT: <https://arxiv.org/abs/1912.09363> (Google, 2019)
- PatchTST: <https://arxiv.org/abs/2211.14730> (ICLR 2023)
- iTransformer: <https://arxiv.org/abs/2310.06625> (ICLR 2024)
- TimesFM 2.5: Google AI (Sep 2025)
- TiRex: <https://arxiv.org/abs/2505.23719> (May 2025)
- IBM TTM: <https://arxiv.org/abs/2401.03955> (2024)
- Moirai 2.0: <https://arxiv.org/abs/2511.11698> (Salesforce, 2025)
- Time-MoE: <https://arxiv.org/abs/2409.16040> (ICLR 2025)
- Mamba: <https://arxiv.org/abs/2312.00752> (2023)
- Chronos-Bolt: <https://aws.amazon.com/blogs/machine-learning/fast-and-accurate-zero-shot-forecasting-with-chronos-bolt-and-autogluon/>
- TSMixer: <https://research.google/blog/tsmixer-an-all-mlp-architecture-for-time-series-forecasting/>
- TimeGPT-2: <https://www.nixtla.io/blog/timegpt-2-announcement>
- Lag-Llama: <https://arxiv.org/abs/2310.08278>
- Chronos-2 HuggingFace: <https://huggingface.co/amazon/chronos-2>
- In-Context Fine-Tuning: <https://arxiv.org/abs/2410.24087>

### Optimizer Papers

- MARS: <https://arxiv.org/abs/2411.10438> (ICML 2025)
- Muon: <https://kellerjordan.github.io/posts/muon/> and <https://github.com/KellerJordan/Muon>
- MuonClip / Kimi K2: <https://github.com/moonshotai/Kimi-K2> and <https://intuitionlabs.ai/articles/kimi-k2-technical-deep-dive>
- SOAP: <https://arxiv.org/abs/2409.11321> (Harvard, 2024)
- Schedule-Free: <https://arxiv.org/abs/2405.15682> and <https://github.com/facebookresearch/schedule_free> (Meta, 2024)
- Prodigy: <https://arxiv.org/abs/2306.06101> and <https://github.com/konstmish/prodigy> (ICML 2024)
- Sophia: <https://arxiv.org/abs/2305.14342> (Stanford, 2023)
- AdEMAMix: <https://machinelearning.apple.com/research/ademamix-optimizer> (Apple, 2024)
- Lion: <https://arxiv.org/abs/2302.06675> (Google Brain, 2023)
- Adan: <https://arxiv.org/abs/2208.06677> (IEEE TPAMI 2024)
- Cautious Optimizers: <https://arxiv.org/abs/2411.16085> (Nov 2024)
- Grokfast: <https://arxiv.org/abs/2405.20233> (2024)
- Mano: <https://arxiv.org/abs/2601.23000> (Feb 2026)
- Kron (PSGD): <https://github.com/lixilinx/psgd_torch>
- Fantastic Pretraining Optimizers benchmark: <https://arxiv.org/html/2509.02046v1>

### Architecture Innovation Papers

- SwiGLU: <https://arxiv.org/abs/2002.05202> (Noam Shazeer)
- RoPE: <https://arxiv.org/abs/2104.09864> (Su et al.)
- Flash Attention: <https://arxiv.org/abs/2205.14135> (Tri Dao)
- DeepSeek-V3 MLA: <https://arxiv.org/abs/2412.19437>
- DeepSeek FP8 Training: <https://research.colfax-intl.com/deepseek-r1-and-fp8-mixed-precision-training/>
- LoRA: <https://arxiv.org/abs/2106.09685> (Microsoft)
- Differential Attention: ICLR 2025
- DistilTS: <https://arxiv.org/abs/2601.12785> (2025)
- TimeKD: <https://arxiv.org/abs/2505.02138>
- Llama 4 iRoPE: Meta (2025)
- RMSNorm analysis: <https://arxiv.org/html/2409.12951v1>
- Peri-LayerNorm: <https://arxiv.org/abs/2502.02732>
- GQA overview: <https://www.ibm.com/think/topics/grouped-query-attention>
- Flash Attention evolution: <https://www.digitalocean.com/community/tutorials/flashattention-4-llm-inference-optimization>
- sigmaReparam: <https://openreview.net/forum?id=QwqxO8URJzn>
- PatchTST: <https://github.com/yuqinie98/PatchTST>
- LLM Architecture Comparison: <https://magazine.sebastianraschka.com/p/the-big-llm-architecture-comparison>
- DeepSeek MLA explained: <https://towardsdatascience.com/deepseek-v3-explained-1-multi-head-latent-attention-ed6bee2a67c4/>

### Training Technique Sources

- Curriculum Learning survey: <https://dl.acm.org/doi/10.1145/3589335.3641257> (ACM 2024)
- Small batch training: <https://arxiv.org/abs/2507.07101> (2025)
- Time series augmentation survey: <https://link.springer.com/article/10.1007/s00521-023-08459-3>
- Dynamic Dropout: <https://arxiv.org/html/2411.03236>
- Early stopping for transformers: <https://arxiv.org/html/2510.16074v1>
- AttentionDrop: <https://arxiv.org/abs/2504.12088>
- Time series transformer survey 2025: <https://www.sciencedirect.com/science/article/pii/S1574013725001595>
- WSD schedule: <https://arxiv.org/html/2410.05192v1>
- WSM decay-free schedule: <https://arxiv.org/abs/2507.17634>

### Benchmark Resources

- GIFT-Eval leaderboard: <https://huggingface.co/spaces/Salesforce/GIFT-Eval>
- fev-bench: <https://arxiv.org/abs/2509.26468>
- Autoformer blog (DLinear debate): <https://huggingface.co/blog/autoformer>
