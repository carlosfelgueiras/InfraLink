"""LLM-as-assessor precision study: for every diagnostic in a sample file
(sample_diagnostics.py / simplify_diagnostics.py output), check out the exact
(repo, commit) the diagnostic was produced against and ask one fresh opencode
session per configuration to assess it, then infer each agent's verdict
(Correct / Incorrect) from its final message.

Accepts either sample schema:
  - full:       repo / resolved_sha / module_dir / node / target / message / ...
  - simplified: id / node / target / message / github_url
For the simplified one, (repo, commit, module_dir) are parsed back out of
github_url.

Checkout strategy: a pristine snapshot per (repo, commit) is exported with
`git archive` -- i.e. NO .git directory. A worktree would expose the repo's
full history (`git log --all`), which for mined diagnostics can include the
very commit that later added the missing dependency -- an answer leak. Each
(diagnostic, configuration) run then gets its own copy of that snapshot
(APFS clone on macOS, so effectively free), so no run can see another's
side effects.

Isolation per run: `opencode run --standalone` (a private server, so env /
config are honoured and sessions never share state), a new session per
invocation, repo-supplied opencode config ignored, and a default permission
set that allows reading/searching the checkout and the web, but no edits,
shell, or interactive questions. A configuration can override any of this.
With web access the agent could still browse the repo's later history on
GitHub; the prompt asks it not to, which is all that stops it.

Usage:
    python3 run_assessment.py --samples ../recall_eval/sample_30_merged_deepseek_atleast2of3.simplified.json \
        --configs configs.json --rules rules.md --batch-id pilot --dry-run
    python3 run_assessment.py --samples ... --configs configs.json --rules rules.md --batch-id pilot --limit 2
    python3 run_assessment.py --samples ... --configs configs.json --rules rules.md --batch-id run1 --jobs 4
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

STUDY_DIR = Path(__file__).resolve().parent
DEPENDENCY_FIXER_ROOT = STUDY_DIR.parent.parent
DEFAULT_REPOS_DIR = DEPENDENCY_FIXER_ROOT / "dataset/missing_dependency_mining/repos"
DEFAULT_PROMPT_TEMPLATE = STUDY_DIR / "prompt_template.md"
SNAPSHOTS_DIR = STUDY_DIR / "snapshots"
RUNS_DIR = STUDY_DIR / "runs"
# The installer only adds ~/.opencode/bin to PATH in ~/.zshrc, which IDEs and
# non-interactive shells never source.
DEFAULT_OPENCODE_INSTALL = Path.home() / ".opencode/bin/opencode"

# Read/search the checkout plus external information (web search/fetch,
# browser); no edits, shell, or interactive questions. Keys are opencode tool
# permission names; a configuration's own "permission" entries are merged
# over these.
DEFAULT_PERMISSIONS: dict[str, str] = {
    "edit": "deny",
    "bash": "deny",
    "shell": "deny",
    "webfetch": "allow",
    "websearch": "allow",
    "browser": "allow",
    "question": "deny",
    # Nothing outside the run's private checkout -- in particular not runs/,
    # which holds the other configurations' verdicts.
    "external_directory": "deny",
}

# Without an explicit provider, headless `opencode run` cancels every web
# search (it would otherwise ask interactively). Exa works with no API key.
DEFAULT_WEBSEARCH = {"provider": "exa"}

RULES_PLACEHOLDER_MARKER = "TODO: paste the assessment rules here"

_VERDICT_EXACT = re.compile(r"\b(Correct|Incorrect)\b")
_VERDICT_ANYCASE = re.compile(r"\b(correct|incorrect)\b", re.IGNORECASE)


@dataclass(frozen=True)
class Diagnostic:
    id: str
    repo: str  # "<owner>__<name>", same convention as the mining pipeline
    commit: str
    module_dir: str
    node: str
    target: str
    message: str


@dataclass(frozen=True)
class OpencodeConfig:
    name: str
    model: str
    agent: str | None
    config: dict[str, object]  # opencode.json content, already merged over the defaults
    env: dict[str, str]
    extra_args: list[str]


# --------------------------------------------------------------------------
# Loading inputs
# --------------------------------------------------------------------------

def parse_github_url(url: str) -> tuple[str, str, str]:
    """https://github.com/<owner>/<name>/tree/<sha>[/<module_dir>] ->
    ("<owner>__<name>", sha, module_dir)."""
    parts = urlparse(url).path.strip("/").split("/")
    if len(parts) < 4 or parts[2] != "tree":
        raise ValueError(f"unexpected github_url shape: {url}")
    owner, name, _, sha, *rest = parts
    return f"{owner}__{name}", sha, "/".join(rest) or "."


def load_diagnostics(samples_path: Path) -> list[Diagnostic]:
    diagnostics = []
    for record in json.loads(samples_path.read_text()):
        if "repo" in record:
            repo = str(record["repo"])
            commit = str(record["resolved_sha"])
            module_dir = str(record.get("module_dir") or ".")
        else:
            repo, commit, module_dir = parse_github_url(str(record["github_url"]))
        diagnostics.append(Diagnostic(
            id=str(record["id"]),
            repo=repo,
            commit=commit,
            module_dir=module_dir,
            node=str(record["node"]),
            target=str(record["target"]),
            message=str(record["message"]),
        ))
    return diagnostics


def build_opencode_config(user_config: dict[str, object], permission_overrides: object) -> dict[str, object]:
    merged: dict[str, object] = {
        "$schema": "https://opencode.ai/config.json",
        "websearch": DEFAULT_WEBSEARCH,
        **user_config,
    }
    permission = user_config.get("permission", {})
    if isinstance(permission, dict):
        permission = {**DEFAULT_PERMISSIONS, **permission}
    if isinstance(permission_overrides, dict):
        permission = {**(permission if isinstance(permission, dict) else {}), **permission_overrides}
    merged["permission"] = permission
    return merged


def load_configs(configs_path: Path) -> list[OpencodeConfig]:
    """configs.json is a list of:
        {"name": "...", "model": "provider/model[#variant]",
         "agent": optional, "config": optional path to an opencode.json (relative
         to configs.json), "permission": optional overrides, "env": optional,
         "extra_args": optional extra `opencode run` flags}"""
    configs = []
    seen: set[str] = set()
    for entry in json.loads(configs_path.read_text()):
        name = entry["name"]
        if name in seen or not re.fullmatch(r"[A-Za-z0-9._-]+", name):
            raise SystemExit(f"config names must be unique and filesystem-safe: {name!r}")
        seen.add(name)

        user_config: dict[str, object] = {}
        if entry.get("config"):
            user_config = json.loads((configs_path.parent / entry["config"]).read_text())

        configs.append(OpencodeConfig(
            name=name,
            model=entry["model"],
            agent=entry.get("agent"),
            config=build_opencode_config(user_config, entry.get("permission")),
            env={k: str(v) for k, v in entry.get("env", {}).items()},
            extra_args=list(entry.get("extra_args", [])),
        ))
    return configs


def render_prompt(template: str, rules: str, diagnostic: Diagnostic) -> str:
    # Plain token replacement (not str.format): messages are full of HCL `${...}` braces.
    values = {
        "rules": rules.strip(),
        "repo": diagnostic.repo.replace("__", "/", 1),
        "commit": diagnostic.commit,
        "module_dir": diagnostic.module_dir,
        "node": diagnostic.node,
        "target": diagnostic.target,
        "message": diagnostic.message.strip(),
    }
    prompt = template
    for key, value in values.items():
        prompt = prompt.replace("{{" + key + "}}", value)
    return prompt


# --------------------------------------------------------------------------
# Checkouts
# --------------------------------------------------------------------------

_snapshot_locks: dict[tuple[str, str], threading.Lock] = {}
_snapshot_locks_guard = threading.Lock()


def ensure_clone(repos_dir: Path, repo: str) -> Path:
    """Reuses the mining pipeline's existing full clone; only clones from
    GitHub if a sample references a repo that isn't there yet."""
    repo_path = repos_dir / repo
    if not repo_path.is_dir():
        owner, name = repo.split("__", 1)
        print(f"cloning {owner}/{name} into {repo_path}", file=sys.stderr)
        subprocess.run(
            ["git", "clone", "--quiet", f"https://github.com/{owner}/{name}.git", str(repo_path)],
            check=True,
        )
    return repo_path


def ensure_snapshot(repos_dir: Path, repo: str, commit: str) -> Path:
    """History-free export of the full repo tree at `commit`, shared
    read-only source for every run against that (repo, commit)."""
    key = (repo, commit)
    with _snapshot_locks_guard:
        lock = _snapshot_locks.setdefault(key, threading.Lock())

    with lock:
        snapshot_path = SNAPSHOTS_DIR / repo / commit[:12]
        if (snapshot_path / ".snapshot_complete").exists():
            return snapshot_path

        repo_path = ensure_clone(repos_dir, repo)
        if subprocess.run(["git", "-C", str(repo_path), "cat-file", "-e", f"{commit}^{{commit}}"]).returncode != 0:
            subprocess.run(["git", "-C", str(repo_path), "fetch", "--quiet", "origin", commit], check=True)

        if snapshot_path.exists():
            shutil.rmtree(snapshot_path)
        snapshot_path.mkdir(parents=True)
        archive = subprocess.Popen(["git", "-C", str(repo_path), "archive", commit], stdout=subprocess.PIPE)
        subprocess.run(["tar", "-x", "-C", str(snapshot_path)], stdin=archive.stdout, check=True)
        if archive.wait() != 0:
            raise RuntimeError(f"git archive failed for {repo}@{commit}")
        (snapshot_path / ".snapshot_complete").touch()
        return snapshot_path


def copy_snapshot(snapshot_path: Path, workdir: Path) -> None:
    """Per-run private copy. `cp -c` makes APFS copy-on-write clones on macOS."""
    workdir.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform == "darwin":
        subprocess.run(["cp", "-cR", str(snapshot_path), str(workdir)], check=True)
    else:
        shutil.copytree(snapshot_path, workdir, symlinks=True)
    (workdir / ".snapshot_complete").unlink(missing_ok=True)


# --------------------------------------------------------------------------
# Running opencode and reading its output
# --------------------------------------------------------------------------

def resolve_opencode_bin(explicit: str | None) -> str:
    candidate = explicit or shutil.which("opencode") or str(DEFAULT_OPENCODE_INSTALL)
    if not (Path(candidate).is_file() and os.access(candidate, os.X_OK)):
        raise SystemExit(
            f"opencode binary not found (tried {candidate!r}); put it on PATH or pass --opencode-bin"
        )
    return candidate


def run_opencode(
    workdir: Path,
    prompt: str,
    config: OpencodeConfig,
    *,
    opencode_bin: str,
    config_path: Path,
    title: str,
    timeout_seconds: int,
) -> tuple[str, str, int | str, float]:
    """Returns (stdout, stderr, exit_code, duration_seconds). exit_code is the
    string "TIMEOUT" if the run was killed, rather than raising -- one hung
    case must not stall the whole batch."""
    command = [
        opencode_bin, "run",
        "--standalone", "--auto",
        "--format", "json",
        "--model", config.model,
        "--title", title,
    ]
    if config.agent:
        command += ["--agent", config.agent]
    command += config.extra_args
    command += [prompt]

    env = {
        **os.environ,
        # opencode takes its project directory from $PWD, not the process cwd;
        # an inherited PWD would point every agent at this study directory.
        "PWD": str(workdir),
        "OPENCODE_CONFIG": str(config_path),
        "OPENCODE_DISABLE_PROJECT_CONFIG": "1",  # never let the assessed repo configure the agent
        "OPENCODE_DISABLE_AUTOUPDATE": "1",
        **config.env,
    }

    start = time.monotonic()
    try:
        result = subprocess.run(
            command, cwd=workdir, env=env, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=timeout_seconds,
        )
        return result.stdout, result.stderr, result.returncode, time.monotonic() - start
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return stdout, stderr, "TIMEOUT", time.monotonic() - start


def parse_events(stdout: str) -> dict[str, object]:
    """Pulls the session id, the final assistant message, errors and usage
    out of `opencode run --format json`'s event stream."""
    session_id = None
    texts_by_message: dict[str, list[str]] = {}
    message_order: list[str] = []
    errors: list[object] = []
    cost = 0.0
    tokens = {"input": 0, "output": 0, "reasoning": 0, "cache_read": 0, "cache_write": 0}
    tool_calls = 0

    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        session_id = session_id or event.get("sessionID")
        part = event.get("part") or {}
        kind = event.get("type")

        if kind == "text":
            message_id = part.get("messageID", "")
            if message_id not in texts_by_message:
                texts_by_message[message_id] = []
                message_order.append(message_id)
            texts_by_message[message_id].append(part.get("text", ""))
        elif kind == "tool_use":
            tool_calls += 1
        elif kind == "step_finish":
            cost += float(part.get("cost") or 0)
            step_tokens = part.get("tokens") or {}
            tokens["input"] += int(step_tokens.get("input") or 0)
            tokens["output"] += int(step_tokens.get("output") or 0)
            tokens["reasoning"] += int(step_tokens.get("reasoning") or 0)
            cache = step_tokens.get("cache") or {}
            tokens["cache_read"] += int(cache.get("read") or 0)
            tokens["cache_write"] += int(cache.get("write") or 0)
        elif kind == "error":
            errors.append(event.get("error"))

    final_text = "\n".join(texts_by_message[message_order[-1]]) if message_order else ""
    return {
        "session_id": session_id,
        "final_text": final_text,
        "errors": errors,
        "cost": cost,
        "tokens": tokens,
        "tool_calls": tool_calls,
    }


def infer_verdict(final_text: str) -> dict[str, object]:
    """The rules ask the agent to answer with the word Correct or Incorrect.
    Takes the LAST such word in the final message (agents tend to reason
    first and conclude last), preferring the capitalised form the rules ask
    for. `ambiguous` flags final messages that mention both words, so those
    can be spot-checked by hand."""
    matches = _VERDICT_EXACT.findall(final_text) or _VERDICT_ANYCASE.findall(final_text)
    mentioned = {m.capitalize() for m in _VERDICT_ANYCASE.findall(final_text)}
    return {
        "verdict": matches[-1].capitalize() if matches else "UNKNOWN",
        "ambiguous": len(mentioned) > 1,
        "matches": [m.capitalize() for m in matches],
    }


# --------------------------------------------------------------------------
# One (diagnostic, configuration) run
# --------------------------------------------------------------------------

def run_output_dir(batch_id: str, diagnostic: Diagnostic, config: OpencodeConfig) -> Path:
    return RUNS_DIR / batch_id / diagnostic.id / config.name


def already_done(output_dir: Path) -> bool:
    return (output_dir / "exit_code").exists()


def assess_one(
    diagnostic: Diagnostic,
    config: OpencodeConfig,
    *,
    prompt: str,
    batch_id: str,
    repos_dir: Path,
    opencode_bin: str,
    timeout_seconds: int,
    keep_workdirs: bool,
) -> str:
    output_dir = run_output_dir(batch_id, diagnostic, config)
    output_dir.mkdir(parents=True, exist_ok=True)

    snapshot_path = ensure_snapshot(repos_dir, diagnostic.repo, diagnostic.commit)
    workdir_parent = Path(tempfile.mkdtemp(prefix=f"assess-{diagnostic.id}-{config.name}-"))
    workdir = workdir_parent / diagnostic.repo.split("__", 1)[1]
    copy_snapshot(snapshot_path, workdir)

    config_path = output_dir / "opencode.json"
    config_path.write_text(json.dumps(config.config, indent=2))
    (output_dir / "prompt.md").write_text(prompt)

    try:
        stdout, stderr, exit_code, duration = run_opencode(
            workdir, prompt, config,
            opencode_bin=opencode_bin,
            config_path=config_path,
            title=f"assess {diagnostic.id} [{config.name}]",
            timeout_seconds=timeout_seconds,
        )
    finally:
        if keep_workdirs:
            (output_dir / "workdir_path").write_text(str(workdir))
        else:
            shutil.rmtree(workdir_parent, ignore_errors=True)

    parsed = parse_events(stdout)
    verdict = infer_verdict(str(parsed["final_text"]))
    if verdict["verdict"] == "UNKNOWN" and (parsed["errors"] or exit_code != 0):
        # A failed run (bad model/variant, provider error, timeout) is not an
        # agent that declined to answer -- keep the two apart in results.csv.
        verdict["verdict"] = "ERROR"
    result = {
        "id": diagnostic.id,
        "config": config.name,
        "model": config.model,
        "agent": config.agent,
        "repo": diagnostic.repo,
        "commit": diagnostic.commit,
        "module_dir": diagnostic.module_dir,
        "node": diagnostic.node,
        "target": diagnostic.target,
        **verdict,
        "session_id": parsed["session_id"],
        "exit_code": exit_code,
        "duration_seconds": duration,
        "cost": parsed["cost"],
        "tokens": parsed["tokens"],
        "tool_calls": parsed["tool_calls"],
        "errors": parsed["errors"],
    }

    (output_dir / "events.jsonl").write_text(stdout)
    (output_dir / "stderr.log").write_text(stderr)
    (output_dir / "final_message.md").write_text(str(parsed["final_text"]))
    (output_dir / "result.json").write_text(json.dumps(result, indent=2))
    # exit_code written last -- its presence marks this run as done (see already_done)
    (output_dir / "exit_code").write_text(str(exit_code))

    flag = " (ambiguous)" if verdict["ambiguous"] else ""
    if verdict["verdict"] == "ERROR" and parsed["errors"]:
        first_error = parsed["errors"][0]
        flag += f" -- {first_error.get('message', first_error) if isinstance(first_error, dict) else first_error}"
    return f"{diagnostic.id} [{config.name}] -> {verdict['verdict']}{flag} exit={exit_code} {duration:.0f}s ${parsed['cost']:.4f}"


# --------------------------------------------------------------------------
# Summary
# --------------------------------------------------------------------------

SUMMARY_FIELDS = [
    "id", "config", "model", "verdict", "ambiguous", "exit_code", "duration_seconds",
    "cost", "tool_calls", "session_id", "repo", "commit", "module_dir", "node", "target",
]


def write_summary(batch_id: str) -> Path:
    """Rebuilt from every result.json on disk, so it also covers runs from
    earlier (resumed) invocations of the same batch."""
    batch_dir = RUNS_DIR / batch_id
    rows = [json.loads(p.read_text()) for p in sorted(batch_dir.glob("*/*/result.json"))]
    summary_path = batch_dir / "results.csv"
    with summary_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    counts: dict[str, dict[str, int]] = {}
    for row in rows:
        per_config = counts.setdefault(row["config"], {})
        per_config[row["verdict"]] = per_config.get(row["verdict"], 0) + 1
    for name, per_config in sorted(counts.items()):
        print(f"  {name}: {dict(sorted(per_config.items()))}", file=sys.stderr)
    return summary_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--samples", type=Path, required=True, help="Sample diagnostics JSON (full or simplified schema)")
    parser.add_argument("--configs", type=Path, required=True, help="JSON list of opencode configurations")
    parser.add_argument("--rules", type=Path, required=True, help="Assessment rules, inserted into the prompt")
    parser.add_argument("--prompt-template", type=Path, default=DEFAULT_PROMPT_TEMPLATE)
    parser.add_argument("--repos-dir", type=Path, default=DEFAULT_REPOS_DIR, help="Where full clones live (<owner>__<repo>)")
    parser.add_argument("--opencode-bin", default=None, help=f"opencode executable (default: PATH, then {DEFAULT_OPENCODE_INSTALL})")
    parser.add_argument("--batch-id", default="default", help="Subdirectory under runs/ to write into")
    parser.add_argument("--only-config", action="append", default=None, help="Only run this config name (repeatable)")
    parser.add_argument("--ids", default=None, help="Comma-separated diagnostic ids to run (debugging)")
    parser.add_argument("--limit", type=int, default=None, help="Only the first N diagnostics (cheap pilot runs)")
    parser.add_argument("--jobs", type=int, default=1, help="Concurrent opencode sessions")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--force", action="store_true", help="Re-run even if already marked done")
    parser.add_argument("--keep-workdirs", action="store_true", help="Don't delete each run's private checkout copy")
    parser.add_argument("--dry-run", action="store_true", help="Print the plan and first rendered prompt; run nothing")
    args = parser.parse_args()

    rules = args.rules.read_text()
    if RULES_PLACEHOLDER_MARKER in rules:
        raise SystemExit(f"{args.rules} still contains the placeholder -- paste the real assessment rules first")
    template = args.prompt_template.read_text()

    diagnostics = load_diagnostics(args.samples)
    if args.ids is not None:
        wanted = {i.strip() for i in args.ids.split(",")}
        diagnostics = [d for d in diagnostics if d.id in wanted]
    if args.limit is not None:
        diagnostics = diagnostics[: args.limit]

    configs = load_configs(args.configs)
    if args.only_config:
        configs = [c for c in configs if c.name in set(args.only_config)]

    planned = [(d, c) for d in diagnostics for c in configs]
    print(f"{len(diagnostics)} diagnostics x {len(configs)} configs = {len(planned)} sessions", file=sys.stderr)

    if args.dry_run:
        for d, c in planned:
            print(f"[dry-run] {d.id}: {d.repo}@{d.commit[:12]} :: {d.module_dir} [{c.name} -> {c.model}]")
        if planned:
            print("\n----- first rendered prompt -----\n" + render_prompt(template, rules, planned[0][0]))
        return

    opencode_bin = resolve_opencode_bin(args.opencode_bin)

    todo = []
    for d, c in planned:
        if already_done(run_output_dir(args.batch_id, d, c)) and not args.force:
            print(f"skip (already done): {d.id} [{c.name}]", file=sys.stderr)
        else:
            todo.append((d, c))

    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {
            pool.submit(
                assess_one, d, c,
                prompt=render_prompt(template, rules, d),
                batch_id=args.batch_id,
                repos_dir=args.repos_dir,
                opencode_bin=opencode_bin,
                timeout_seconds=args.timeout_seconds,
                keep_workdirs=args.keep_workdirs,
            ): (d, c)
            for d, c in todo
        }
        for future in as_completed(futures):
            d, c = futures[future]
            try:
                print(future.result(), file=sys.stderr)
            except Exception as exc:  # one broken checkout must not kill the batch
                error_path = run_output_dir(args.batch_id, d, c) / "error.log"
                error_path.parent.mkdir(parents=True, exist_ok=True)
                error_path.write_text(traceback.format_exc())
                print(f"{d.id} [{c.name}] FAILED: {exc!r} (traceback: {error_path})", file=sys.stderr)

    if (RUNS_DIR / args.batch_id).is_dir():
        print(f"summary: {write_summary(args.batch_id)}", file=sys.stderr)


if __name__ == "__main__":
    main()
