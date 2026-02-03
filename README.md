# Enables adaptive polling by setting the `coldPollRate` for eligible AWSCloudWatch integrations.

## What it does
1) GETs all AWSCloudWatch integrations from the provided domain.
2) Filters out:
   - disabled integrations (unless `--includeDisabled`)
   - integrations that already have `coldPollRate` set (unless `--overrideExisting`)
   - integrations with `metricStreamsSyncState == "ENABLED"`
3) Shows a confirmation table (ID + name) and asks to proceed.
4) PUTs each remaining integration with `coldPollRate` set to the requested value.

## Usage
```bash
python enable_aws_adaptive_polling.py \
  app.us0.signalfx.com \
  <API_TOKEN> \
  --coldPollRateMinutes 15
```

## Arguments
- `domainName` (required): Full domain name, e.g. `app.us0.signalfx.com`.
- `apiToken` (required): SignalFx API token.
- `--coldPollRateMinutes` (optional, default `15`): Sets `coldPollRate` in minutes (1–20).
- `--includeDisabled` (optional): Include disabled integrations.
- `--overrideExisting` (optional): Update even if `coldPollRate` is already set.

## Notes
- You must confirm before any PUT requests run.
- If no integrations match, the script exits without changes.
