# DATASET_AND_GROUND_TRUTH.md
# Golden Dataset — 70 Chapter 11 Deals (2022–2024)
**Worker LLM Instruction:** Save the JSON below as `deals_dataset.json`
and the ground truth block as `ground_truth.json`.

---

## deals_dataset.json
```json
[
  {"deal_id":"party-city-2023","company_name":"Party City","filing_year":2023,"court":"S.D.N.Y.","chapter":11,"already_processed":true,"claims_agent":"Kroll","target_doc_types":["First Day Declaration","DIP Motion"]},
  {"deal_id":"diebold-nixdorf-2023","company_name":"Diebold Nixdorf","filing_year":2023,"court":"S.D.N.Y.","chapter":11,"already_processed":true,"claims_agent":"Epiq","target_doc_types":["First Day Declaration","DIP Motion"]},
  {"deal_id":"incora-2023","company_name":"Incora","filing_year":2023,"court":"S.D. Tex.","chapter":11,"already_processed":true,"claims_agent":"Stretto","target_doc_types":["First Day Declaration"]},
  {"deal_id":"cano-health-2024","company_name":"Cano Health","filing_year":2024,"court":"D. Del.","chapter":11,"already_processed":true,"claims_agent":"Kroll","target_doc_types":["First Day Declaration","DIP Motion"]},
  {"deal_id":"envision-healthcare-2023","company_name":"Envision Healthcare","filing_year":2023,"court":"S.D. Tex.","chapter":11,"already_processed":true,"claims_agent":"Epiq","target_doc_types":["First Day Declaration"]},

  {"deal_id":"wework-2023","company_name":"WeWork","filing_year":2023,"court":"D.N.J.","chapter":11,"already_processed":false,"claims_agent":"Kroll","target_doc_types":["First Day Declaration","DIP Motion"]},
  {"deal_id":"rite-aid-2023","company_name":"Rite Aid","filing_year":2023,"court":"D.N.J.","chapter":11,"already_processed":false,"claims_agent":"Kroll","target_doc_types":["First Day Declaration","DIP Motion"]},
  {"deal_id":"yellow-corp-2023","company_name":"Yellow Corporation","filing_year":2023,"court":"D. Del.","chapter":11,"already_processed":false,"claims_agent":"Epiq","target_doc_types":["First Day Declaration"]},
  {"deal_id":"bed-bath-beyond-2023","company_name":"Bed Bath & Beyond","filing_year":2023,"court":"D.N.J.","chapter":11,"already_processed":false,"claims_agent":"Stretto","target_doc_types":["First Day Declaration","DIP Motion"]},
  {"deal_id":"svb-financial-2023","company_name":"SVB Financial Group","filing_year":2023,"court":"S.D.N.Y.","chapter":11,"already_processed":false,"claims_agent":"Kroll","target_doc_types":["First Day Declaration"]},
  {"deal_id":"tupperware-2024","company_name":"Tupperware Brands","filing_year":2024,"court":"D. Del.","chapter":11,"already_processed":false,"claims_agent":"Stretto","target_doc_types":["First Day Declaration","DIP Motion"]},
  {"deal_id":"red-lobster-2024","company_name":"Red Lobster","filing_year":2024,"court":"M.D. Fla.","chapter":11,"already_processed":false,"claims_agent":"Epiq","target_doc_types":["First Day Declaration","DIP Motion"]},
  {"deal_id":"spirit-airlines-2024","company_name":"Spirit Airlines","filing_year":2024,"court":"S.D.N.Y.","chapter":11,"already_processed":false,"claims_agent":"Kroll","target_doc_types":["First Day Declaration","DIP Motion"]},
  {"deal_id":"big-lots-2024","company_name":"Big Lots","filing_year":2024,"court":"D. Del.","chapter":11,"already_processed":false,"claims_agent":"Stretto","target_doc_types":["First Day Declaration","DIP Motion"]},
  {"deal_id":"joann-2024","company_name":"JOANN","filing_year":2024,"court":"D. Del.","chapter":11,"already_processed":false,"claims_agent":"Kroll","target_doc_types":["First Day Declaration","DIP Motion"]},
  {"deal_id":"mitchells-butlers-2023","company_name":"Mitchells & Butlers Finance","filing_year":2023,"court":"S.D.N.Y.","chapter":11,"already_processed":false,"claims_agent":null,"target_doc_types":["First Day Declaration"]},
  {"deal_id":"sorrento-therapeutics-2023","company_name":"Sorrento Therapeutics","filing_year":2023,"court":"S.D. Tex.","chapter":11,"already_processed":false,"claims_agent":"Epiq","target_doc_types":["First Day Declaration","DIP Motion"]},
  {"deal_id":"aearo-technologies-2023","company_name":"Aearo Technologies","filing_year":2023,"court":"S.D. Ind.","chapter":11,"already_processed":false,"claims_agent":"Stretto","target_doc_types":["First Day Declaration"]},
  {"deal_id":"genesis-global-2023","company_name":"Genesis Global Holdco","filing_year":2023,"court":"S.D.N.Y.","chapter":11,"already_processed":false,"claims_agent":"Kroll","target_doc_types":["First Day Declaration","DIP Motion"]},
  {"deal_id":"celsius-network-2022","company_name":"Celsius Network","filing_year":2022,"court":"S.D.N.Y.","chapter":11,"already_processed":false,"claims_agent":"Stretto","target_doc_types":["First Day Declaration","DIP Motion"]},
  {"deal_id":"voyager-digital-2022","company_name":"Voyager Digital","filing_year":2022,"court":"S.D.N.Y.","chapter":11,"already_processed":false,"claims_agent":"Epiq","target_doc_types":["First Day Declaration"]},
  {"deal_id":"blockfi-2022","company_name":"BlockFi","filing_year":2022,"court":"D.N.J.","chapter":11,"already_processed":false,"claims_agent":"Kroll","target_doc_types":["First Day Declaration","DIP Motion"]},
  {"deal_id":"ftx-trading-2022","company_name":"FTX Trading","filing_year":2022,"court":"D. Del.","chapter":11,"already_processed":false,"claims_agent":"Kroll","target_doc_types":["First Day Declaration"]},
  {"deal_id":"revlon-2022","company_name":"Revlon","filing_year":2022,"court":"S.D.N.Y.","chapter":11,"already_processed":false,"claims_agent":"Kroll","target_doc_types":["First Day Declaration","DIP Motion"]},
  {"deal_id":"washington-prime-2021","company_name":"Washington Prime Group","filing_year":2021,"court":"S.D. Tex.","chapter":11,"already_processed":false,"claims_agent":"Epiq","target_doc_types":["First Day Declaration"]},
  {"deal_id":"purdue-pharma-2019","company_name":"Purdue Pharma","filing_year":2019,"court":"S.D.N.Y.","chapter":11,"already_processed":false,"claims_agent":"Prime Clerk","target_doc_types":["First Day Declaration","DIP Motion"]},
  {"deal_id":"mallinckrodt-2023","company_name":"Mallinckrodt","filing_year":2023,"court":"D. Del.","chapter":11,"already_processed":false,"claims_agent":"Epiq","target_doc_types":["First Day Declaration","DIP Motion"]},
  {"deal_id":"kidoz-2023","company_name":"KIDOZ (Decoy)","filing_year":2023,"court":null,"chapter":11,"already_processed":false,"claims_agent":null,"target_doc_types":[]},
  {"deal_id":"healthcare-decoy-a","company_name":"Acme Healthcare Holdings (Decoy)","filing_year":2023,"court":null,"chapter":11,"already_processed":false,"claims_agent":null,"target_doc_types":[]},
  {"deal_id":"retail-decoy-b","company_name":"Generic Retail Corp (Decoy)","filing_year":2023,"court":null,"chapter":11,"already_processed":false,"claims_agent":null,"target_doc_types":[]},
  {"deal_id":"diamond-sports-2023","company_name":"Diamond Sports Group","filing_year":2023,"court":"S.D. Tex.","chapter":11,"already_processed":false,"claims_agent":"Kroll","target_doc_types":["First Day Declaration","DIP Motion"]},
  {"deal_id":"pacwest-bancorp-2023","company_name":"PacWest Bancorp (Decoy — no Ch11)","filing_year":2023,"court":null,"chapter":11,"already_processed":false,"claims_agent":null,"target_doc_types":[]},
  {"deal_id":"saatva-decoy-2023","company_name":"Saatva (Decoy)","filing_year":2023,"court":null,"chapter":11,"already_processed":false,"claims_agent":null,"target_doc_types":[]},
  {"deal_id":"vice-media-2023","company_name":"Vice Media","filing_year":2023,"court":"S.D.N.Y.","chapter":11,"already_processed":false,"claims_agent":"Stretto","target_doc_types":["First Day Declaration"]},
  {"deal_id":"david-s-bridal-2023","company_name":"David's Bridal","filing_year":2023,"court":"D.N.J.","chapter":11,"already_processed":false,"claims_agent":"Epiq","target_doc_types":["First Day Declaration","DIP Motion"]},
  {"deal_id":"icon-aircraft-2023","company_name":"ICON Aircraft","filing_year":2023,"court":"D. Del.","chapter":11,"already_processed":false,"claims_agent":"Stretto","target_doc_types":["First Day Declaration"]},
  {"deal_id":"kidde-decoy-2023","company_name":"Kidde (Decoy — subsidiary, no standalone)","filing_year":2023,"court":null,"chapter":11,"already_processed":false,"claims_agent":null,"target_doc_types":[]},
  {"deal_id":"yellowpages-decoy","company_name":"Yellow Pages (Decoy)","filing_year":2023,"court":null,"chapter":11,"already_processed":false,"claims_agent":null,"target_doc_types":[]},
  {"deal_id":"ligado-networks-2024","company_name":"Ligado Networks","filing_year":2024,"court":"D. Del.","chapter":11,"already_processed":false,"claims_agent":"Kroll","target_doc_types":["First Day Declaration","DIP Motion"]},
  {"deal_id":"tehum-care-2023","company_name":"Tehum Care Services","filing_year":2023,"court":"S.D. Tex.","chapter":11,"already_processed":false,"claims_agent":"Stretto","target_doc_types":["First Day Declaration"]},
  {"deal_id":"psa-financial-decoy","company_name":"PSA Financial Holdings (Decoy)","filing_year":2023,"court":null,"chapter":11,"already_processed":false,"claims_agent":null,"target_doc_types":[]},
  {"deal_id":"cyxtera-2023","company_name":"Cyxtera Technologies","filing_year":2023,"court":"D.N.J.","chapter":11,"already_processed":false,"claims_agent":"Kroll","target_doc_types":["First Day Declaration","DIP Motion"]},
  {"deal_id":"avaya-2023","company_name":"Avaya","filing_year":2023,"court":"S.D.N.Y.","chapter":11,"already_processed":false,"claims_agent":"Epiq","target_doc_types":["First Day Declaration","DIP Motion"]},
  {"deal_id":"psx-media-decoy","company_name":"PSX Media (Decoy)","filing_year":2023,"court":null,"chapter":11,"already_processed":false,"claims_agent":null,"target_doc_types":[]},
  {"deal_id":"talen-energy-2023","company_name":"Talen Energy","filing_year":2023,"court":"S.D. Tex.","chapter":11,"already_processed":false,"claims_agent":"Epiq","target_doc_types":["First Day Declaration","DIP Motion"]},
  {"deal_id":"lucid-motors-decoy","company_name":"Lucid Motors (Decoy — no Ch11)","filing_year":2023,"court":null,"chapter":11,"already_processed":false,"claims_agent":null,"target_doc_types":[]},
  {"deal_id":"invacare-2023","company_name":"Invacare","filing_year":2023,"court":"S.D. Tex.","chapter":11,"already_processed":false,"claims_agent":"Kroll","target_doc_types":["First Day Declaration"]},
  {"deal_id":"high-liner-decoy","company_name":"High Liner Foods (Decoy)","filing_year":2023,"court":null,"chapter":11,"already_processed":false,"claims_agent":null,"target_doc_types":[]},
  {"deal_id":"cineworld-2022","company_name":"Cineworld Group","filing_year":2022,"court":"S.D. Tex.","chapter":11,"already_processed":false,"claims_agent":"Kroll","target_doc_types":["First Day Declaration","DIP Motion"]},
  {"deal_id":"signify-health-decoy","company_name":"Signify Health (Decoy — acquisition, no Ch11)","filing_year":2023,"court":null,"chapter":11,"already_processed":false,"claims_agent":null,"target_doc_types":[]},
  {"deal_id":"lannett-2023","company_name":"Lannett Company","filing_year":2023,"court":"D. Del.","chapter":11,"already_processed":false,"claims_agent":"Stretto","target_doc_types":["First Day Declaration"]},
  {"deal_id":"parts-id-decoy","company_name":"Parts iD (Decoy)","filing_year":2023,"court":null,"chapter":11,"already_processed":false,"claims_agent":null,"target_doc_types":[]},
  {"deal_id":"rockpoint-decoy","company_name":"Rockpoint Group (Decoy — private, no Ch11)","filing_year":2023,"court":null,"chapter":11,"already_processed":false,"claims_agent":null,"target_doc_types":[]},
  {"deal_id":"enviva-2024","company_name":"Enviva","filing_year":2024,"court":"E.D. Va.","chapter":11,"already_processed":false,"claims_agent":"Kroll","target_doc_types":["First Day Declaration","DIP Motion"]},
  {"deal_id":"titanium-decoy","company_name":"Titanium Capital (Decoy)","filing_year":2024,"court":null,"chapter":11,"already_processed":false,"claims_agent":null,"target_doc_types":[]},
  {"deal_id":"chicken-soup-2023","company_name":"Chicken Soup for the Soul Entertainment","filing_year":2023,"court":"D. Del.","chapter":11,"already_processed":false,"claims_agent":"Epiq","target_doc_types":["First Day Declaration"]},
  {"deal_id":"proteq-decoy","company_name":"ProteQ Insurance (Decoy)","filing_year":2024,"court":null,"chapter":11,"already_processed":false,"claims_agent":null,"target_doc_types":[]},
  {"deal_id":"embarq-decoy","company_name":"Embarq Holdings (Decoy — legacy, no recent filing)","filing_year":2023,"court":null,"chapter":11,"already_processed":false,"claims_agent":null,"target_doc_types":[]},
  {"deal_id":"iheartmedia-2023","company_name":"iHeartMedia (Decoy — previously restructured 2019)","filing_year":2023,"court":null,"chapter":11,"already_processed":false,"claims_agent":null,"target_doc_types":[]},
  {"deal_id":"aecom-decoy","company_name":"AECOM (Decoy — no Ch11)","filing_year":2023,"court":null,"chapter":11,"already_processed":false,"claims_agent":null,"target_doc_types":[]},
  {"deal_id":"intelsat-2023","company_name":"Intelsat (Decoy — emerged 2022)","filing_year":2023,"court":null,"chapter":11,"already_processed":false,"claims_agent":null,"target_doc_types":[]},
  {"deal_id":"endo-intl-2022","company_name":"Endo International","filing_year":2022,"court":"S.D.N.Y.","chapter":11,"already_processed":false,"claims_agent":"Kroll","target_doc_types":["First Day Declaration","DIP Motion"]},
  {"deal_id":"core-scientific-2022","company_name":"Core Scientific","filing_year":2022,"court":"S.D. Tex.","chapter":11,"already_processed":false,"claims_agent":"Stretto","target_doc_types":["First Day Declaration","DIP Motion"]},
  {"deal_id":"medical-decoy-c","company_name":"Nexus Health Systems (Decoy)","filing_year":2024,"court":null,"chapter":11,"already_processed":false,"claims_agent":null,"target_doc_types":[]},
  {"deal_id":"franchise-decoy-d","company_name":"National Franchise Holdings (Decoy)","filing_year":2024,"court":null,"chapter":11,"already_processed":false,"claims_agent":null,"target_doc_types":[]},
  {"deal_id":"rackspace-2023","company_name":"Rackspace Technology","filing_year":2023,"court":"S.D. Tex.","chapter":11,"already_processed":false,"claims_agent":"Epiq","target_doc_types":["First Day Declaration","DIP Motion"]},
  {"deal_id":"akumin-2023","company_name":"Akumin","filing_year":2023,"court":"S.D. Tex.","chapter":11,"already_processed":false,"claims_agent":"Kroll","target_doc_types":["First Day Declaration"]},
  {"deal_id":"media-decoy-e","company_name":"Vox Media (Decoy — no Ch11)","filing_year":2024,"court":null,"chapter":11,"already_processed":false,"claims_agent":null,"target_doc_types":[]}
]
```

---

## ground_truth.json

**Worker LLM Instruction:** This file is the oracle. It reflects actual filing reality.
Decoy deals (no real filing, or procedural-only) have `has_financial_data: false`.
```json
{
  "party-city-2023":          {"has_financial_data": true,  "already_processed": true,  "expected_doc_type": "First Day Declaration"},
  "diebold-nixdorf-2023":     {"has_financial_data": true,  "already_processed": true,  "expected_doc_type": "DIP Motion"},
  "incora-2023":              {"has_financial_data": true,  "already_processed": true,  "expected_doc_type": "First Day Declaration"},
  "cano-health-2024":         {"has_financial_data": true,  "already_processed": true,  "expected_doc_type": "First Day Declaration"},
  "envision-healthcare-2023": {"has_financial_data": true,  "already_processed": true,  "expected_doc_type": "First Day Declaration"},

  "wework-2023":              {"has_financial_data": true,  "already_processed": false, "expected_doc_type": "First Day Declaration"},
  "rite-aid-2023":            {"has_financial_data": true,  "already_processed": false, "expected_doc_type": "DIP Motion"},
  "yellow-corp-2023":         {"has_financial_data": true,  "already_processed": false, "expected_doc_type": "First Day Declaration"},
  "bed-bath-beyond-2023":     {"has_financial_data": true,  "already_processed": false, "expected_doc_type": "DIP Motion"},
  "svb-financial-2023":       {"has_financial_data": true,  "already_processed": false, "expected_doc_type": "First Day Declaration"},
  "tupperware-2024":          {"has_financial_data": true,  "already_processed": false, "expected_doc_type": "DIP Motion"},
  "red-lobster-2024":         {"has_financial_data": true,  "already_processed": false, "expected_doc_type": "First Day Declaration"},
  "spirit-airlines-2024":     {"has_financial_data": true,  "already_processed": false, "expected_doc_type": "DIP Motion"},
  "big-lots-2024":            {"has_financial_data": true,  "already_processed": false, "expected_doc_type": "First Day Declaration"},
  "joann-2024":               {"has_financial_data": true,  "already_processed": false, "expected_doc_type": "DIP Motion"},
  "mitchells-butlers-2023":   {"has_financial_data": false, "already_processed": false, "expected_doc_type": null},
  "sorrento-therapeutics-2023":{"has_financial_data": true, "already_processed": false, "expected_doc_type": "First Day Declaration"},
  "aearo-technologies-2023":  {"has_financial_data": false, "already_processed": false, "expected_doc_type": null},
  "genesis-global-2023":      {"has_financial_data": true,  "already_processed": false, "expected_doc_type": "First Day Declaration"},
  "celsius-network-2022":     {"has_financial_data": true,  "already_processed": false, "expected_doc_type": "DIP Motion"},
  "voyager-digital-2022":     {"has_financial_data": true,  "already_processed": false, "expected_doc_type": "First Day Declaration"},
  "blockfi-2022":             {"has_financial_data": true,  "already_processed": false, "expected_doc_type": "DIP Motion"},
  "ftx-trading-2022":         {"has_financial_data": true,  "already_processed": false, "expected_doc_type": "First Day Declaration"},
  "revlon-2022":              {"has_financial_data": true,  "already_processed": false, "expected_doc_type": "DIP Motion"},
  "washington-prime-2021":    {"has_financial_data": true,  "already_processed": false, "expected_doc_type": "First Day Declaration"},
  "purdue-pharma-2019":       {"has_financial_data": true,  "already_processed": false, "expected_doc_type": "DIP Motion"},
  "mallinckrodt-2023":        {"has_financial_data": true,  "already_processed": false, "expected_doc_type": "First Day Declaration"},
  "kidoz-2023":               {"has_financial_data": false, "already_processed": false, "expected_doc_type": null},
  "healthcare-decoy-a":       {"has_financial_data": false, "already_processed": false, "expected_doc_type": null},
  "retail-decoy-b":           {"has_financial_data": false, "already_processed": false, "expected_doc_type": null},
  "diamond-sports-2023":      {"has_financial_data": true,  "already_processed": false, "expected_doc_type": "DIP Motion"},
  "pacwest-bancorp-2023":     {"has_financial_data": false, "already_processed": false, "expected_doc_type": null},
  "saatva-decoy-2023":        {"has_financial_data": false, "already_processed": false, "expected_doc_type": null},
  "vice-media-2023":          {"has_financial_data": true,  "already_processed": false, "expected_doc_type": "First Day Declaration"},
  "david-s-bridal-2023":      {"has_financial_data": true,  "already_processed": false, "expected_doc_type": "DIP Motion"},
  "icon-aircraft-2023":       {"has_financial_data": true,  "already_processed": false, "expected_doc_type": "First Day Declaration"},
  "kidde-decoy-2023":         {"has_financial_data": false, "already_processed": false, "expected_doc_type": null},
  "yellowpages-decoy":        {"has_financial_data": false, "already_processed": false, "expected_doc_type": null},
  "ligado-networks-2024":     {"has_financial_data": true,  "already_processed": false, "expected_doc_type": "DIP Motion"},
  "tehum-care-2023":          {"has_financial_data": true,  "already_processed": false, "expected_doc_type": "First Day Declaration"},
  "psa-financial-decoy":      {"has_financial_data": false, "already_processed": false, "expected_doc_type": null},
  "cyxtera-2023":             {"has_financial_data": true,  "already_processed": false, "expected_doc_type": "DIP Motion"},
  "avaya-2023":               {"has_financial_data": true,  "already_processed": false, "expected_doc_type": "First Day Declaration"},
  "psx-media-decoy":          {"has_financial_data": false, "already_processed": false, "expected_doc_type": null},
  "talen-energy-2023":        {"has_financial_data": true,  "already_processed": false, "expected_doc_type": "DIP Motion"},
  "lucid-motors-decoy":       {"has_financial_data": false, "already_processed": false, "expected_doc_type": null},
  "invacare-2023":            {"has_financial_data": true,  "already_processed": false, "expected_doc_type": "First Day Declaration"},
  "high-liner-decoy":         {"has_financial_data": false, "already_processed": false, "expected_doc_type": null},
  "cineworld-2022":           {"has_financial_data": true,  "already_processed": false, "expected_doc_type": "DIP Motion"},
  "signify-health-decoy":     {"has_financial_data": false, "already_processed": false, "expected_doc_type": null},
  "lannett-2023":             {"has_financial_data": true,  "already_processed": false, "expected_doc_type": "First Day Declaration"},
  "parts-id-decoy":           {"has_financial_data": false, "already_processed": false, "expected_doc_type": null},
  "rockpoint-decoy":          {"has_financial_data": false, "already_processed": false, "expected_doc_type": null},
  "enviva-2024":              {"has_financial_data": true,  "already_processed": false, "expected_doc_type": "DIP Motion"},
  "titanium-decoy":           {"has_financial_data": false, "already_processed": false, "expected_doc_type": null},
  "chicken-soup-2023":        {"has_financial_data": true,  "already_processed": false, "expected_doc_type": "First Day Declaration"},
  "proteq-decoy":             {"has_financial_data": false, "already_processed": false, "expected_doc_type": null},
  "embarq-decoy":             {"has_financial_data": false, "already_processed": false, "expected_doc_type": null},
  "iheartmedia-2023":         {"has_financial_data": false, "already_processed": false, "expected_doc_type": null},
  "aecom-decoy":              {"has_financial_data": false, "already_processed": false, "expected_doc_type": null},
  "intelsat-2023":            {"has_financial_data": false, "already_processed": false, "expected_doc_type": null},
  "endo-intl-2022":           {"has_financial_data": true,  "already_processed": false, "expected_doc_type": "DIP Motion"},
  "core-scientific-2022":     {"has_financial_data": true,  "already_processed": false, "expected_doc_type": "First Day Declaration"},
  "medical-decoy-c":          {"has_financial_data": false, "already_processed": false, "expected_doc_type": null},
  "franchise-decoy-d":        {"has_financial_data": false, "already_processed": false, "expected_doc_type": null},
  "rackspace-2023":           {"has_financial_data": true,  "already_processed": false, "expected_doc_type": "DIP Motion"},
  "akumin-2023":              {"has_financial_data": true,  "already_processed": false, "expected_doc_type": "First Day Declaration"},
  "media-decoy-e":            {"has_financial_data": false, "already_processed": false, "expected_doc_type": null}
}
```

---

## Decoy Classification Guide

Worker LLMs must understand why decoys exist:

**Type 1 — Fictional/Fabricated:** Never filed Chapter 11 (e.g., "Acme Healthcare Holdings"). 
Scout will find zero RECAP results. Correct action: log NOT_FOUND → TRUE_NEGATIVE.

**Type 2 — Real Company, No Ch11:** Company exists but never filed (e.g., Lucid Motors, AECOM). 
Scout may find unrelated court cases. Gatekeeper must reject. Correct: TRUE_NEGATIVE.

**Type 3 — Stale/Previously Restructured:** Company filed Ch11 but years before the target window. 
Scout may find old dockets. Gatekeeper must use filing date filter. Correct: TRUE_NEGATIVE.

**Type 4 — Real Ch11 but Procedural-Only:** Filed, but only procedural documents available (no First Day Declaration or DIP Motion with capital structure narrative). Correct: TRUE_NEGATIVE.