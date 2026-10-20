"""Verify the authenticated Cloud Run service, including live model/MCP calls."""
import argparse
import json
import subprocess
import urllib.request
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("url")
args = parser.parse_args()
token = subprocess.check_output(["gcloud", "auth", "print-identity-token"], text=True).strip()


def request(path, data=None):
    req = urllib.request.Request(args.url.rstrip("/") + path,
        data=json.dumps(data).encode() if data is not None else None,
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as response:
        return json.load(response)


print("HEALTH", request("/api/health"))
assert "cascade_analyst" in request("/list-apps")
session = request("/apps/cascade_analyst/users/deployment-check/sessions", {})
events = request("/run", {"appName": "cascade_analyst", "userId": "deployment-check",
    "sessionId": session["id"], "newMessage": {"role": "user", "parts": [{"text":
        "Analyze Steel + Lacquer's supply-disruption cascade at two hops with minimum intensity 0.01. Include baseline and filtered counts."}]}})
responses = []
for event in events:
    for part in (event.get("content") or {}).get("parts", []):
        if "functionResponse" in part:
            responses.append(part["functionResponse"])
        if part.get("text"):
            print(part["text"])
successful = {r["name"] for r in responses if r["response"].get("status") == "ok"}
assert {"search_businesses", "analyze_cascade"} <= successful, responses
report = next(r["response"] for r in responses if r["name"] == "analyze_cascade")
assert report["baseline"]["multi_hop_count"] > 0, report
print("CLOUD_RUN_VERIFIED", report["baseline"]["exposed_business_count"], report["filtered"]["exposed_business_count"])
Path("reports").mkdir(exist_ok=True)
Path("reports/deployment-verification.json").write_text(json.dumps(events, indent=2))
