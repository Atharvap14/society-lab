# Primary-source ledger

Verified on 4 October 2026. Source descriptions are intentionally short. Research hypotheses in this repository are extensions to be tested, not replications already completed.

| Source | Verified contribution relevant to this lab | Version and venue status |
|---|---|---|
| [Clark and Brennan, Grounding in Communication](https://web.stanford.edu/~clark/1990s/Clark%2C%20H.H.%20_%20Brennan%2C%20S.E.%20_Grounding%20in%20communication_%201991.pdf) | Communication requires coordinated contributions and grounding sufficient for a purpose; medium changes grounding costs | 1991 book chapter, authors' Stanford copy |
| [Telang, Singh, Yorke-Smith, Maintenance of Social Commitments in Multiagent Systems](https://ojs.aaai.org/index.php/AAAI/article/view/17355) | Formal treatment of maintaining conditions as social commitments, distinct from only achieving them | AAAI 2021, volume 35(13), 11369–11377 |
| [InterWhen](https://arxiv.org/abs/2602.11202v3) | Intermediate-state monitoring, asynchronous verification, feedback intervention, and policy-derived verifiers | arXiv v3, 13 May 2026; conference acceptance not established in this audit |
| [Dream-RSI](https://dream-rsi.com/) | Replay of realized exploration trees for evaluating exploration policies, with fresh online discovery expanding history | Authors' 2026 technical-report project. Site bibliography contains a placeholder arXiv ID; do not invent a paper identifier or venue |
| [Talk is Cheap, Communication is Hard](https://arxiv.org/abs/2605.01750v2) | Controlled resource negotiation probes shared history, anchoring, references, joint plan formation, and repair | arXiv v2, 12 May 2026; title appears on [COLM 2026 accepted list](https://colm.eventhosts.cc/Conferences/2026/AcceptedPapers) |
| [Cooperative Profiles Predict Multi-Agent LLM Team Performance](https://arxiv.org/abs/2604.20658v1) | Behavioral-game profiles are associated with team outcomes in tested scientific workflows | arXiv v1, 22 April 2026; title appears on COLM 2026 accepted list |
| [High Volatility and Action Bias](https://arxiv.org/abs/2604.02578v2) | Group binary search reveals coordination instability in the studied LLM/human comparison | arXiv v2, 1 October 2026; paper comments report COLM 2026 acceptance |
| [Hudgens and Halloran, Toward Causal Inference With Interference](https://pmc.ncbi.nlm.nih.gov/articles/PMC2600548/) | Defines estimands and experimental inference when one unit's treatment can affect another | JASA 2008, 103(482), 832–842 |
| [Aronow and Samii, Estimating Average Causal Effects Under General Interference](https://arxiv.org/abs/1305.6156) | Randomization design, exposure mapping, and estimands are separate ingredients of network inference | Authors' arXiv version; use a pinned version for implementation |
| [Laya upstream](https://github.com/NandhaKishorM/laya) | Typed choice/score/yes-no decisions and Jev-compatible `POST /v1/systemone`; model/router configuration matters | Living upstream repository; pin a commit before comparing backend performance |
| [von Luxburg, A Tutorial on Spectral Clustering](https://arxiv.org/abs/0711.0189) | Different graph Laplacians, spectral clustering constructions, and their limitations | Statistics and Computing 17(4), 2007; author's arXiv version |
| [Shuman et al., Signal Processing on Graphs](https://arxiv.org/abs/1211.0053v2) | Graph spectral domains and localized/multiscale graph signal analysis | arXiv v2, 10 March 2013; linked IEEE Signal Processing Magazine DOI |

## Transfer limitations

The cited experiments have particular tasks, models, resource regimes, and outcome rubrics. They motivate constructs and interventions; their findings are not evidence that the same mechanism occurs in the Village. The Village is observational, changes over time, and may lack exact prompt and context state.

Laya and Jev are possible measurement backends, not behavioral ground truth. Laya's upstream describes confidence-definition differences from Jev and warns that thresholds depend on held-out calibration, option counts, question types, and language. Preserve raw output, backend version, and label definitions. Fit thresholds on separate data rather than importing performance claims into this domain.

Research agents should add primary sources with source status and the exact supporting claim, record unavailable sources honestly, and preserve failed novelty checks. A venue page establishes acceptance; an arXiv abstract alone does not.
