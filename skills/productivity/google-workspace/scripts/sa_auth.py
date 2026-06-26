"""Service-account (Domain-Wide Delegation) auth backend for the
google-workspace skill.

Lets Hermes use Google Calendar / Gmail / Drive **non-interactively** on a
headless host (Railway) by fetching the SA key from Infisical in-memory and
impersonating a Workspace user via DWD — no browser, no refresh-token expiry.

Activated when env GOOGLE_AUTH_MODE=service_account.

Reuses the exact Infisical Universal-Auth + impersonation pattern already
proven in ~/.config/yoursup/drive_ops.py (BIZ-29).

Env (inject on Railway, see deploy notes):
  GOOGLE_AUTH_MODE=service_account              # turns this backend on
  INFISICAL_UNIVERSAL_AUTH_CLIENT_ID / _SECRET  # Hermes-scoped machine identity
  INFISICAL_HOST_URL        (default https://app.infisical.com)
  DRIVE_SA_WORKSPACE_ID     (default c467417a-0d90-4b74-9f82-9d10c1e81101)
  DRIVE_SA_ENV              (default prod)
  DRIVE_SA_PATH             (default /)
  DRIVE_SA_KEY              (default DRIVE_SA_JSON)
  DRIVE_IMPERSONATE_SUBJECT (default masam@yoursup.co.jp)
"""
import json
import os
import urllib.parse
import urllib.request

# Scopes the SA must ALSO be authorized for in Admin console DWD (client_id
# 117411827537347930171). Least-privilege: calendar events + gmail drafts/read
# + drive. gmail.send is intentionally omitted (BIZ-6 = draft-for-approval).
SA_SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/documents",
]


def sa_mode() -> bool:
    return os.environ.get("GOOGLE_AUTH_MODE", "").strip().lower() == "service_account"


def _infisical_token() -> str:
    host = os.environ.get("INFISICAL_HOST_URL", "https://app.infisical.com").rstrip("/")
    payload = {
        "clientId": os.environ["INFISICAL_UNIVERSAL_AUTH_CLIENT_ID"],
        "clientSecret": os.environ["INFISICAL_UNIVERSAL_AUTH_CLIENT_SECRET"],
    }
    req = urllib.request.Request(
        host + "/api/v1/auth/universal-auth/login",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["accessToken"]


def _sa_info() -> dict:
    host = os.environ.get("INFISICAL_HOST_URL", "https://app.infisical.com").rstrip("/")
    ws = os.environ.get("DRIVE_SA_WORKSPACE_ID", "c467417a-0d90-4b74-9f82-9d10c1e81101")
    env = os.environ.get("DRIVE_SA_ENV", "prod")
    path = os.environ.get("DRIVE_SA_PATH", "/")
    key = os.environ.get("DRIVE_SA_KEY", "DRIVE_SA_JSON")
    token = _infisical_token()
    q = urllib.parse.urlencode({"workspaceId": ws, "environment": env, "secretPath": path})
    req = urllib.request.Request(
        host + "/api/v3/secrets/raw/" + key + "?" + q,
        headers={"Authorization": "Bearer " + token},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.load(r)
    return json.loads(d["secret"]["secretValue"])


def credentials():
    """Return impersonated SA credentials for googleapiclient build()."""
    from google.oauth2 import service_account

    creds = service_account.Credentials.from_service_account_info(
        _sa_info(), scopes=SA_SCOPES
    )
    subject = os.environ.get("DRIVE_IMPERSONATE_SUBJECT", "masam@yoursup.co.jp")
    return creds.with_subject(subject)
