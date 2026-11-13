"""No secrets in the repository. core is PUBLIC, so anything tracked here is published.

Scans every tracked file (`git ls-files`) for private keys, provider tokens and secret-looking assignments, and
checks that files which must never be versioned (databases, .env, licenses, keys) are not. It is a cheap stand-in for
`gitleaks`; running gitleaks in CI later is still worthwhile (it also scans history).

If it flags a harmless value (a documented example, a test key built at runtime), make the value obviously fake
(`example`, `changeme`, `xxxx`) rather than adding an exception here."""
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]  # core/

PATTERNS = {
    "private key block": re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED |PGP )?PRIVATE KEY"),
    "Mercado Pago access token": re.compile(r"APP_USR-\d{6,}-\d{4,}-[0-9a-f]{20,}"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    "Slack token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    "Stripe live key": re.compile(r"\b[sr]k_live_[A-Za-z0-9]{16,}\b"),
    "Resend API key": re.compile(r"\bre_[A-Za-z0-9]{24,}\b"),
    "Google API key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    "JWT": re.compile(r"\beyJ[A-Za-z0-9_-]{15,}\.eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{10,}\b"),
    "URL with password": re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s:/@'\"]+:(?!\*|x{3,}|password|changeme|secret|pass\b)[^\s:/@'\"{$<]{6,}@[\w.-]+"),
}
# NAME = "long random-looking literal" for secret-ish names (not env lookups, not placeholders, not code)
ASSIGN = re.compile(r"""(?ix)\b[\w.-]*(?:secret|password|passwd|api[_-]?key|private[_-]?key|token)[\w.-]*\s*[:=]\s*["']([A-Za-z0-9+/=_\-]{24,})["']""")
PLACEHOLDER = re.compile(r"(?i)prueba|GEZDGNBVGY3TQOJQ|example|changeme|placeholder|xxxx|your[-_]|dummy|fake|test|sample|\.\.\.|<")

FORBIDDEN_PATHS = [
    (re.compile(r"\.(db|sqlite3?)$|\.db-(wal|shm)$"), "database"),
    (re.compile(r"(^|/)\.env($|\.)(?!example)"), ".env file"),
    (re.compile(r"\.(pem|key|pfx|p12)$"), "key/certificate file"),
    (re.compile(r"(^|/)license(_state)?\.(lic|json)$"), "license file"),
    (re.compile(r"(^|/)(secrets|owner)/"), "secrets/owner folder"),
    (re.compile(r"(^|/)secret\.key$"), "secret.key"),
]
SKIP_SUFFIX = {".png", ".jpg", ".jpeg", ".webp", ".ico", ".gif", ".woff", ".woff2", ".ttf", ".bin", ".pdf", ".zip", ".mp4", ".lock", ".svg"}
SKIP_FILES = {"package-lock.json", "access_rules.snapshot.json", "requirements.lock.txt", "THIRD_PARTY_NOTICES.txt"}


def tracked() -> list[Path]:
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=REPO, capture_output=True, check=True).stdout.decode("utf-8", "replace")
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout (nothing to scan)")
    return [REPO / p for p in out.split("\0") if p]


def test_no_forbidden_files_are_tracked():
    bad = []
    for p in tracked():
        rel = p.relative_to(REPO).as_posix()
        for pat, why in FORBIDDEN_PATHS:
            if pat.search(rel):
                bad.append(f"{rel} ({why})")
    assert not bad, f"files that must never be versioned: {bad}"


def test_no_secrets_in_tracked_files():
    hits = []
    for p in tracked():
        if p.suffix.lower() in SKIP_SUFFIX or p.name in SKIP_FILES or not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        rel = p.relative_to(REPO).as_posix()
        for name, pat in PATTERNS.items():
            for m in pat.finditer(text):
                if not PLACEHOLDER.search(m.group(0)):
                    hits.append(f"{rel}:{text.count(chr(10), 0, m.start()) + 1} {name}")
        for m in ASSIGN.finditer(text):
            if not PLACEHOLDER.search(m.group(0)) and len(set(m.group(1))) > 10:  # varied characters: looks random
                hits.append(f"{rel}:{text.count(chr(10), 0, m.start()) + 1} secret-looking assignment")
    assert not hits, "possible secrets in tracked files (make fake values obviously fake, or remove the real ones):\n  " + "\n  ".join(hits[:20])


def test_the_scanner_would_catch_a_leak(tmp_path):
    """Guards the scanner itself: a planted key must be reported (so a green run means something)."""
    sample = "-----BEGIN PRIVATE KEY-----\nMIIE..\n"
    assert PATTERNS["private key block"].search(sample)
    assert PATTERNS["Mercado Pago access token"].search("APP_USR-1234567-021212-" + "a1" * 16 + "-99")
    assert ASSIGN.search('API_KEY = "Zk3pQ9vLx2Rt7Wm4Nc8Bd1Hy6Js0Fg5A"')
    assert not PLACEHOLDER.search("Zk3pQ9vLx2Rt7Wm4Nc8Bd1Hy6Js0Fg5A")
