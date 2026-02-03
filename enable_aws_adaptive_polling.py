#!/usr/bin/env python3
import argparse
import json
import sys
import urllib.error
import urllib.request


def http_request(method, url, token, body=None):
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("X-SF-TOKEN", token)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = resp.read().decode("utf-8")
            if payload:
                return resp.status, json.loads(payload)
            return resp.status, None
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8") if e.fp else ""
        raise RuntimeError(f"HTTP {e.code} for {url}: {err_body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Request failed for {url}: {e}") from e


def main():
    parser = argparse.ArgumentParser(
        description="Enable adaptive polling for eligible AWSCloudWatch integrations."
    )
    parser.add_argument(
        "domainName",
        help=(
            "full domain name (e.g. app.us1.signalfx.com)"
        ),
    )
    parser.add_argument("apiToken", help="API token, found on UI in: [My Profile -> Show User API Access Token] OR [Settings -> Access Tokens]")
    parser.add_argument(
        "--coldPollRateMinutes",
        type=int,
        default=15,
        metavar="minutes",
        help="cold poll rate to set, allowed range 1-20 minutes (default: 15)",
    )
    parser.add_argument(
        "--includeDisabled",
        action="store_true",
        default=False,
        help="include disabled integrations (default: false)",
    )
    parser.add_argument(
        "--overrideExisting",
        action="store_true",
        default=False,
        help="override cold poll rate for integrations which already have adaptive polling configured (default: false)",
    )
    args = parser.parse_args()
    if args.coldPollRateMinutes < 1 or args.coldPollRateMinutes > 20:
        parser.error("--coldPollRateMinutes must be in range 1-20")

    base = f"https://{args.domainName}"
    list_url = f"{base}/v2/integration?type=AWSCloudWatch"

    _, payload = http_request("GET", list_url, args.apiToken)
    results = payload.get("results", []) if isinstance(payload, dict) else []
    print(
        f"Found {len(results)} integrations of type AWSCloudWatch"
    )
    candidates = []
    filtered_disabled = []
    filtered_cold_poll = []
    filtered_streaming = []
    for item in results:
        if not isinstance(item, dict):
            continue
        if not args.includeDisabled and not item.get("enabled", False):
            integ_id = item.get("id")
            if integ_id:
                filtered_disabled.append(integ_id)
            continue
        if not args.overrideExisting and "coldPollRate" in item and item.get("coldPollRate") is not None:
            integ_id = item.get("id")
            if integ_id:
                filtered_cold_poll.append(integ_id)
            continue
        if item.get("metricStreamsSyncState") == "ENABLED":
            integ_id = item.get("id")
            if integ_id:
                filtered_streaming.append(integ_id)
            continue
        candidates.append(item)

    remaining = [
        (item.get("id"), item.get("name"))
        for item in candidates
        if item.get("id")
    ]
    remaining_ids = [rid for rid, _ in remaining]
    if not args.includeDisabled and filtered_disabled:
        print(
            f"Filtered out disabled integrations ({len(filtered_disabled)}): "
            f"{', '.join(filtered_disabled)}"
        )
    if not args.overrideExisting and filtered_cold_poll:
        print(
            f"Filtered out integrations with cold poll rate already set ({len(filtered_cold_poll)}): "
            f"{', '.join(filtered_cold_poll)}"
        )
    if filtered_streaming:
        print(
            f"Filtered out integrations with metricStreamsSyncState==ENABLED ({len(filtered_streaming)}): "
            f"{', '.join(filtered_streaming)}"
        )
    if remaining:
        print(f"{len(remaining_ids)} integrations queued for update: ")
        id_width = max(len(rid) for rid, _ in remaining)
        print(f"{'ID'.ljust(id_width)}  NAME")
        print(f"{'-' * id_width}  {'-' * 4}")
        for rid, name in remaining:
            print(f"{rid.ljust(id_width)}  {name if name is not None else ''}")
        reply = input("Proceed with PUT updates? [y/N]: ").strip().lower()
        if reply not in ("y", "yes"):
            print("Aborted. No updates performed.")
            return
    else:
        print("No integrations meet the provided criteria. No updates performed.")
        return

    updated_ids = []
    for item in candidates:
        integ_id = item.get("id")
        if not integ_id:
            continue
        body = dict(item)
        body["coldPollRate"] = args.coldPollRateMinutes * 60000
        put_url = f"{base}/v2/integration/{integ_id}"
        status, _ = http_request("PUT", put_url, args.apiToken, body=body)
        if 200 <= status < 300:
            updated_ids.append(integ_id)

    if updated_ids:
        print(f"Updated {len(updated_ids)} integrations: {', '.join(updated_ids)}")
    else:
        print("Updated 0 integrations")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
