# Matching V2 experiment

Completed a fixed 200-product experiment using four local Amazon exports. Raw quotes, product rows, requests, replies and review workbooks remain in ignored local work/. V1.4, original workbooks and the 10,037-reference library are unchanged.

Observed 21,280 rows, 15,596 ASINs and 932 missing prices. Historical local Action exports cover 7,171 frozen-reference SKUs; these are dated observations, not live quotes.

Actual name-only and name/spec/category analyses each return five candidates per product. A/B top-reference changes: 66. Sensitivity to uncalibrated scoring weights: 23 queries. These are output differences, not accuracy gains.

Price eligibility: 0/1,000 pairs, 0/200 complete rankings. Uncovered C results stay unavailable; no B fallback is counted as price success. Price-effect improvement is unmeasured.

Prepared 60 pairs for separate independent fact review and Owner business review. Both label counts remain zero; Precision@1 and Recall@20 are null. No calibrated weights, replacement recommendation, whole-catalog run or main merge.

See `references/matching_v2_candidate.md` for the provisional formula, source/pack/date contracts and reproducible commands. A source-binding output error and explicit count-product validation repair were preserved; the fixed sample and semantic/scoring contract were not retuned.

Execution caveat: one 10-record A request ran twice during parallel orchestration. Both actual responses/event hashes were preserved; 2 model top-reference choices varied, with unchanged relation classes. Delivery uses the primary pipeline output, not an outcome-selected answer. A same-arm exclusive execution lock was added and tested. Two source-hash response rejections were retried. All recorded event hashes are available.
