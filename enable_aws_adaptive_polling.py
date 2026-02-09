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


def format_minutes(value, missing_label=None):
    if value is None:
        return missing_label or ""
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return ""
    if numeric >= 1000:
        numeric = numeric / 60000
    if numeric.is_integer():
        return str(int(numeric))
    return str(round(numeric, 2))


def print_table(rows, show_cold_poll_rate, missing_label=None):
    if not rows:
        return
    if show_cold_poll_rate:
        headers = ("ID", "NAME", "COLD_POLL_RATE")
        id_width = max(len(headers[0]), *(len(rid) for rid, _, _ in rows))
        name_width = max(len(headers[1]), *(len(name or "") for _, name, _ in rows))
        minutes_width = max(
            len(headers[2]),
            *(len(format_minutes(minutes, missing_label)) for _, _, minutes in rows),
        )

        print(f"{headers[0].ljust(id_width)}  {headers[1].ljust(name_width)}  {headers[2].ljust(minutes_width)}")
        print(f"{'-' * id_width}  {'-' * name_width}  {'-' * minutes_width}")
        for rid, name, minutes in rows:
            print(
                f"{rid.ljust(id_width)}  "
                f"{(name or '').ljust(name_width)}  "
                f"{format_minutes(minutes, missing_label).ljust(minutes_width)}"
            )
        return

    headers = ("ID", "NAME")
    id_width = max(len(headers[0]), *(len(rid) for rid, _, _ in rows))
    name_width = max(len(headers[1]), *(len(name or "") for _, name, _ in rows))
    print(f"{headers[0].ljust(id_width)}  {headers[1].ljust(name_width)}")
    print(f"{'-' * id_width}  {'-' * name_width}")
    for rid, name, _ in rows:
        print(
            f"{rid.ljust(id_width)}  "
            f"{(name or '').ljust(name_width)}"
        )


def print_updated(rows, total_expected, show_cold_poll_rate, target_minutes):
    if total_expected and len(rows) == total_expected:
        print("All updates succeeded. Adaptive polling is enabled and set to " f"{target_minutes} minutes")
        return
    if rows:
        suffix = "s" if len(rows) != 1 else ""
        print(f"Updated {len(rows)} integration{suffix}:")
        print_table(rows, show_cold_poll_rate)
        return
    print("Updated 0 integrations")


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
    parser.add_argument("apiToken",
                        help="API token, found on UI in: [My Profile -> Show User API Access Token] OR [Settings -> Access Tokens]")
    parser.add_argument(
        "--coldPollRateMinutes",
        type=int,
        default=15,
        metavar="minutes",
        help="cold poll rate to set (default: 15)",
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
    if args.coldPollRateMinutes < 1:
        parser.error("--coldPollRateMinutes must be a positive value")

    base = f"https://{args.domainName}"
    list_url = f"{base}/v2/integration?type=AWSCloudWatch"

    _, payload = http_request("GET", list_url, args.apiToken)
    results = payload.get("results", []) if isinstance(payload, dict) else []
    suffix = "s" if len(results) != 1 else ""
    print(f"Found {len(results)} integration{suffix} of type AWSCloudWatch.")
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
        (item.get("id"), item.get("name"), item.get("coldPollRate"))
        for item in candidates
        if item.get("id")
    ]
    remaining_ids = [rid for rid, _, _ in remaining]
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
        remaining_suffix = "s" if len(remaining_ids) != 1 else ""
        print(f"\n{len(remaining_ids)} integration{remaining_suffix} queued for update: ")
        print_table(remaining, args.overrideExisting, missing_label="none")
        reply = input("\nProceed with updates? [y/N]: ").strip().lower()
        print()
        if reply not in ("y", "yes"):
            print("Aborted. No updates performed.")
            return
    else:
        print("No integrations meet the provided criteria. No updates performed.")
        return

    updated = []
    update_error = None
    try:
        for item in candidates:
            integ_id = item.get("id")
            if not integ_id:
                continue
            body = dict(item)
            body["coldPollRate"] = args.coldPollRateMinutes * 60000
            put_url = f"{base}/v2/integration/{integ_id}"
            http_request("PUT", put_url, args.apiToken, body=body)
            updated.append((integ_id, item.get("name"), args.coldPollRateMinutes))
    except Exception as exc:
        update_error = exc
        raise
    finally:
        if update_error is not None:
            print("Update FAILED before completion.")
            print_updated(updated, len(candidates), args.overrideExisting, args.coldPollRateMinutes,)

    print_updated(updated, len(candidates), args.overrideExisting, args.coldPollRateMinutes, )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        sys.exit(1)
