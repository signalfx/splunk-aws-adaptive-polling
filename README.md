Enables adaptive polling by setting the `inactiveMetricsPollRate` for eligible AWSCloudWatch integrations.

## What it does
1) GETs all AWSCloudWatch integrations from the provided domain.
2) Filters out:
   - disabled integrations (unless `--includeDisabled`)
   - integrations that already have `inactiveMetricsPollRate` set (unless `--overrideExisting`)
   - integrations with `metricStreamsSyncState == "ENABLED"`
3) Shows a confirmation table (ID + name) and asks to proceed.
4) PUTs each remaining integration with `inactiveMetricsPollRate` set to the requested value.

## Usage
```bash
python enable_aws_adaptive_polling.py \
  app.us0.signalfx.com \
  <API_TOKEN> \
  --inactiveMetricsPollRateMinutes 15
```

## Arguments
- `domainName` (required): Full domain name, e.g. `app.us0.signalfx.com`.
- `apiToken` (required): SignalFx API token.
- `--inactiveMetricsPollRateMinutes` (optional, default `15`): Sets `inactiveMetricsPollRate` in minutes (1–60).
- `--includeDisabled` (optional): Include disabled integrations.
- `--overrideExisting` (optional): Update even if `inactiveMetricsPollRate` is already set.

## Notes
- You must confirm before any PUT requests run.
- If no integrations match, the script exits without changes.
