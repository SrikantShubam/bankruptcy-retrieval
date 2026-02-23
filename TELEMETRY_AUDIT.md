# Telemetry Audit Report

## Bug 3 Analysis — F1=1.0 with Zero API Calls

### Findings from execution_log.jsonl analysis:

1. **All PIPELINE_TERMINAL events show `pipeline_status: "active"`**
   - This is incorrect - should be "DOWNLOADED", "NOT_FOUND", "FETCH_FAILED", etc.
   - The pipeline never properly sets terminal status after Scout/Gatekeeper/Fetcher

2. **API calls were made but no files downloaded**
   - Each deal shows `total_api_calls_this_deal: 3` or more
   - But `downloaded_file: null` for all deals
   - This means API calls returned results but no PDF was successfully downloaded

3. **Classification Logic Bug**
   - The `classify()` function only returns TRUE_POSITIVE for `pipeline_status == "DOWNLOADED"`
   - For status "active", it returns "UNCLASSIFIED"
   - But benchmark report shows TP=17 with 0 API calls in the final tally

### Root Cause

The telemetry `finalise()` method shows `total_api_calls: 0` but the log shows 3+ API calls per deal. This is a tracking bug - the `_api_calls_total` is not being accumulated correctly, OR the benchmark report is reading from a stale/cached file.

Additionally, the pipeline status remains "active" throughout - the nodes never update it to "DOWNLOADED" or "NOT_FOUND" after processing.

### Evidence

From logs/execution_log.jsonl:
```
{"event_type": "PIPELINE_TERMINAL", ..., "pipeline_status": "active", "total_api_calls_this_deal": 3, "downloaded_file": null}
```

Every single non-excluded deal has status "active" - this explains why:
- Precision/Recall are miscalculated 
- F1=1.0 is a false metric

### Recommended Fix

1. **Fix nodes.py**: Update pipeline_status in scout_node, gatekeeper_node, fetcher_node to:
   - "NOT_FOUND" if no candidates found
   - "SKIPPED" if gatekeeper rejects
   - "DOWNLOADED" if file successfully saved
   - "FETCH_FAILED" if download fails

2. **Fix telemetry.py**: Add validation that pipeline_status is a known terminal status before classifying

3. **Verify ground_truth.json is loaded correctly** and `has_financial_data` values are accurate

4. **Clear execution_log.jsonl** before each run to avoid stale data affecting benchmark
