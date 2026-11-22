# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Project command line: ./hack <command> (macOS/Linux) or .\\hack <command> (Windows).

Standard library only, so it runs before any project dependency is installed.
The wrappers (./hack, hack.cmd) install uv if needed and run this with uv's Python.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
INFRA = ROOT / "infra"
ENV_FILE = ROOT / ".env"
ENV_EXAMPLE = ROOT / ".env.example"
ENV_SHARED = ROOT / ".env.age"
# Agent skills: the source is in .agents/skills (Codex and the Agent Skills
# standard); Claude Code only reads .claude/skills, so that's a generated copy.
SKILLS_SRC = ROOT / ".agents" / "skills"
SKILLS_CLAUDE = ROOT / ".claude" / "skills"

# Supabase containers the app doesn't use (saves RAM and a few GB of downloads).
SUPABASE_EXCLUDE = "logflare,vector,edge-runtime,imgproxy"

IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")


# --------------------------------------------------------------------------- output

if IS_WIN:
    os.system("")  # turns on ANSI colours in the Windows console
# Redirected output on Windows (pipes, CI logs) defaults to the ANSI code page (cp1252),
# which can't encode ✓/✗ and crashes print(). Write UTF-8 everywhere instead.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
_TTY = sys.stdout.isatty()


def _style(code: str):
    return lambda s: f"\033[{code}m{s}\033[0m" if _TTY else str(s)


bold, dim, red, green, yellow, blue = (_style(c) for c in ("1", "2", "31", "32", "33", "34"))


def step(msg: str) -> None:
    print(f"\n{blue('==>')} {bold(msg)}", flush=True)


def ok(msg: str) -> None:
    print(f"    {green('✓')} {msg}", flush=True)


def warn(msg: str) -> None:
    print(f"    {yellow('!')} {msg}", flush=True)


class Fail(Exception):
    """Stops the command with a message (no traceback)."""


# --------------------------------------------------------------------------- processes


def which(name: str) -> str | None:
    return shutil.which(name)


def child_env(extra: dict[str, str] | None) -> dict[str, str]:
    env = {**os.environ, **(extra or {})}
    # uv runs this script in its own virtualenv; don't leak it into `uv run` in backend/.
    env.pop("VIRTUAL_ENV", None)
    return env


def run(
    cmd: list[str],
    *,
    cwd: Path = ROOT,
    env: dict[str, str] | None = None,
    check: bool = True,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    # Resolve through PATH ourselves so Windows finds npm.cmd, npx.cmd etc.
    exe = which(cmd[0]) or cmd[0]
    if not capture:
        print(dim(f"    $ {' '.join(cmd)}"), flush=True)
    try:
        result = subprocess.run(
            [exe, *cmd[1:]],
            cwd=cwd,
            env=child_env(env),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=capture,
        )
    except FileNotFoundError as e:
        raise Fail(f"{cmd[0]} is not installed (run ./hack setup)") from e
    if check and result.returncode != 0:
        detail = f"\n{result.stderr.strip()}" if capture and result.stderr else ""
        raise Fail(f"`{' '.join(cmd)}` failed (exit {result.returncode}){detail}")
    return result


def output(cmd: list[str], **kw) -> str:
    return run(cmd, capture=True, **kw).stdout.strip()


def run_foreground(cmd: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None) -> int:
    """Run a long-lived command. Ctrl+C reaches it too; wait for its clean shutdown."""
    print(dim(f"    $ {' '.join(cmd)}"), flush=True)
    proc = subprocess.Popen([which(cmd[0]) or cmd[0], *cmd[1:]], cwd=cwd, env=child_env(env))
    while True:
        try:
            return proc.wait()
        except KeyboardInterrupt:
            continue


def uv() -> str:
    # `uv run` exports UV (its own path); a fresh Windows install isn't on PATH yet.
    return os.environ.get("UV") or which("uv") or "uv"


# --------------------------------------------------------------------------- tools


@dataclass(frozen=True)
class Tool:
    name: str
    why: str
    version_args: tuple[str, ...]
    min_version: tuple[int, ...] = ()
    brew: str = ""  # formula, or "--cask <name>"
    winget: str = ""
    scoop: bool = False  # Windows: install from the Supabase scoop bucket
    docs: str = ""
    hint: str = ""  # extra advice when an old version wins on PATH


TOOLS = {
    t.name: t
    for t in [
        Tool(
            "docker",
            "runs local Supabase and the app",
            ("--version",),
            (24,),
            brew="--cask docker",
            winget="Docker.DockerDesktop",
            docs="https://docs.docker.com/get-docker/",
        ),
        Tool(
            "node",
            "frontend tooling and Playwright",
            ("--version",),
            (24,),
            brew="node",
            winget="OpenJS.NodeJS.LTS",
            docs="https://nodejs.org",
            hint="With nvm/fnm: `nvm install 24` / `fnm install 24`, then open a new terminal.",
        ),
        Tool(
            "supabase",
            "local Postgres + Auth, migrations",
            ("--version",),
            (3, 0),
            brew="supabase/tap/supabase",
            scoop=True,
            docs="https://supabase.com/docs/guides/local-development/cli/getting-started",
        ),
        Tool(
            "gh",
            "GitHub CLI: team .env sharing, deploys",
            ("--version",),
            brew="gh",
            winget="GitHub.cli",
            docs="https://cli.github.com",
        ),
        Tool(
            "age",
            "encrypts the shared team .env",
            ("--version",),
            brew="age",
            winget="FiloSottile.age",
            docs="https://github.com/FiloSottile/age#installation",
        ),
        Tool(
            "terraform",
            "creates the deploy infrastructure",
            ("version",),
            (1, 6),
            brew="hashicorp/tap/terraform",
            winget="Hashicorp.Terraform",
            docs="https://developer.hashicorp.com/terraform/install",
        ),
    ]
}
DEV_TOOLS = ["docker", "node", "supabase", "gh", "age"]
DEPLOY_TOOLS = ["terraform", "gh"]


def parse_version(text: str) -> tuple[int, ...] | None:
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", text)
    return tuple(int(g) for g in m.groups() if g is not None) if m else None


def fmt_version(v: tuple[int, ...]) -> str:
    return ".".join(map(str, v))


def tool_version(tool: Tool) -> tuple[int, ...] | None:
    if not which(tool.name):
        return None
    r = run([tool.name, *tool.version_args], capture=True, check=False)
    return parse_version(r.stdout + r.stderr) or (0,)


def refresh_path() -> None:
    """Pick up PATH changes from installers without opening a new terminal."""
    extra: list[str] = []
    if IS_WIN:
        import winreg

        for hive, key in [
            (
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
            ),
            (winreg.HKEY_CURRENT_USER, "Environment"),
        ]:
            try:
                with winreg.OpenKey(hive, key) as k:
                    extra += os.path.expandvars(winreg.QueryValueEx(k, "Path")[0]).split(";")
            except OSError:
                pass
        extra += [
            str(Path.home() / "scoop" / "shims"),
            str(Path.home() / ".local" / "bin"),
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Links"),
        ]
    else:
        extra += ["/opt/homebrew/bin", "/usr/local/bin", str(Path.home() / ".local" / "bin")]
    current = os.environ.get("PATH", "").split(os.pathsep)
    added = [p for p in extra if p and p not in current and Path(p).is_dir()]
    os.environ["PATH"] = os.pathsep.join(current + added)


def ensure_scoop() -> bool:
    if which("scoop"):
        return True
    warn("installing scoop (Windows package manager, needed for the Supabase CLI)")
    run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "RemoteSigned",
            "-Command",
            "irm get.scoop.sh | iex",
        ],
        check=False,
    )
    refresh_path()
    return bool(which("scoop"))


def install_tool(tool: Tool, upgrade: bool) -> bool:
    """Install or upgrade with the platform's package manager. False if we can't."""
    # Homebrew on macOS (and Linuxbrew for formulas; casks are macOS-only).
    if which("brew") and tool.brew and (IS_MAC or not tool.brew.startswith("--cask")):
        args = tool.brew.split()
        if upgrade and run(["brew", "upgrade", *args], check=False).returncode == 0:
            return True
        return run(["brew", "install", *args], check=False).returncode == 0
    if IS_WIN and tool.scoop:
        if not ensure_scoop():
            return False
        run(
            ["scoop", "bucket", "add", "supabase", "https://github.com/supabase/scoop-bucket.git"],
            check=False,
        )
        return (
            run(["scoop", "update" if upgrade else "install", "supabase"], check=False).returncode
            == 0
        )
    if IS_WIN and tool.winget and which("winget"):
        run(
            [
                "winget",
                "upgrade" if upgrade else "install",
                "--id",
                tool.winget,
                "--exact",
                "--accept-source-agreements",
                "--accept-package-agreements",
            ],
            check=False,
        )  # winget's exit codes are unreliable; the version re-check decides
        return True
    return False


def ensure_tool(name: str, install: bool = True) -> None:
    tool = TOOLS[name]
    version = tool_version(tool)
    good = version is not None and version >= tool.min_version
    if good:
        ok(f"{name} {fmt_version(version)}  {dim(tool.why)}")
        return
    need = f" (need {fmt_version(tool.min_version)}+)" if tool.min_version else ""
    problem = "is missing" if version is None else f"{fmt_version(version)} is too old{need}"
    manual = f"Install it: {tool.docs}" + (f"\n    {tool.hint}" if tool.hint else "")
    if not install:
        raise Fail(f"{name} {problem}. Run ./hack setup, or {manual}")
    warn(f"{name} {problem}, installing")
    if not install_tool(tool, upgrade=version is not None):
        raise Fail(f"{name} {problem} and can't be installed automatically here. {manual}")
    refresh_path()
    version = tool_version(tool)
    if version is None or version < tool.min_version:
        raise Fail(
            f"{name} still {problem} after installing. Open a new terminal and re-run. {manual}"
        )
    ok(f"{name} {fmt_version(version)}  {dim(tool.why)}")


def ensure_docker_running() -> None:
    if run(["docker", "info"], capture=True, check=False).returncode == 0:
        ok("docker is running")
        return
    warn("Docker isn't running, starting it")
    if IS_MAC:
        if run(["open", "-a", "Docker"], capture=True, check=False).returncode != 0:
            run(["open", "-a", "OrbStack"], capture=True, check=False)
    elif IS_WIN:
        desktop = (
            Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
            / "Docker"
            / "Docker"
            / "Docker Desktop.exe"
        )
        if desktop.exists():
            subprocess.Popen([str(desktop)])
    for _ in range(60):
        time.sleep(2)
        if run(["docker", "info"], capture=True, check=False).returncode == 0:
            ok("docker is running")
            return
    raise Fail(
        "Docker didn't start. Start Docker Desktop (its first start asks you to accept\n"
        "its terms), then re-run."
    )


def ensure_gh_auth() -> None:
    if run(["gh", "auth", "status"], capture=True, check=False).returncode != 0:
        warn("GitHub CLI isn't signed in")
        run(["gh", "auth", "login", "--web", "--git-protocol", "https"])
    ok("gh is signed in")


def github_repo() -> str:
    try:
        return output(["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"])
    except Fail as e:
        raise Fail("Can't find this repo on GitHub. Push it first (gh repo create).") from e


# --------------------------------------------------------------------------- .env

_ENV_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$")


def parse_env(text: str) -> dict[str, str]:
    """KEY=value lines; comments, blanks and junk are skipped; the last duplicate wins."""
    values: dict[str, str] = {}
    for line in text.splitlines():
        m = _ENV_LINE.match(line)
        if not m:
            continue
        value = m.group(2).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[m.group(1)] = value
    return values


def missing_env_blocks(example: str, existing: dict[str, str]) -> tuple[list[str], str]:
    """Keys of .env.example missing from .env, and the text to append (with their comments)."""
    added: list[str] = []
    blocks: list[str] = []
    comments: list[str] = []
    for line in example.splitlines():
        if line.strip().startswith("#"):
            comments.append(line)
            continue
        m = _ENV_LINE.match(line)
        if m and m.group(1) not in existing:
            added.append(m.group(1))
            blocks.append("\n".join([*comments, line]))
        comments = []
    if not added:
        return [], ""
    return added, "\n# --- Added by ./hack (new in .env.example)\n" + "\n".join(blocks) + "\n"


def sync_env() -> list[str]:
    """Create .env from .env.example, or append keys it lacks. Never changes existing values."""
    example = ENV_EXAMPLE.read_text(encoding="utf-8")
    if not ENV_FILE.exists():
        ENV_FILE.write_text(example, encoding="utf-8")
        return list(parse_env(example))
    text = ENV_FILE.read_text(encoding="utf-8")
    added, appendix = missing_env_blocks(example, parse_env(text))
    if added:
        ENV_FILE.write_text(text.rstrip("\n") + "\n" + appendix, encoding="utf-8")
    return added


def update_env_text(text: str, updates: dict[str, str]) -> tuple[str, list[str]]:
    """Set keys in a .env text in place (append unknown ones). Returns new text, changed keys."""
    current = parse_env(text)
    changed = [k for k, v in updates.items() if current.get(k) != v]
    lines = text.splitlines()
    done: set[str] = set()
    for i, line in enumerate(lines):
        m = _ENV_LINE.match(line)
        if m and m.group(1) in updates:
            lines[i] = f"{m.group(1)}={updates[m.group(1)]}"
            done.add(m.group(1))
    lines += [f"{k}={v}" for k, v in updates.items() if k not in done]
    return "\n".join(lines) + "\n", changed


def write_env_values(updates: dict[str, str]) -> list[str]:
    text, changed = update_env_text(ENV_FILE.read_text(encoding="utf-8"), updates)
    ENV_FILE.write_text(text, encoding="utf-8")
    return changed


def is_secret(key: str) -> bool:
    return any(w in key for w in ("KEY", "SECRET", "TOKEN", "PASSWORD"))


def mask(key: str, value: str) -> str:
    if not value:
        return dim("(empty)")
    if not is_secret(key):
        return value
    return f"{value[:6]}…{dim(f'({len(value)} chars)')}" if len(value) > 10 else "•" * len(value)


# Keep in sync with resolve_llm_provider() in backend/app/core/config.py.
LLM_KEYS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GOOGLE_API_KEY",
}


def llm_summary(env: dict[str, str]) -> str:
    provider = env.get("LLM_PROVIDER", "auto") or "auto"
    if provider == "auto":
        provider = next((p for p, k in LLM_KEYS.items() if env.get(k)), "none")
    if provider == "none":
        return yellow("none: paste the partner's API key into .env (the provider is detected)")
    key = LLM_KEYS.get(provider, "")
    if key and not env.get(key):
        return red(f"{provider}, but {key} is empty")
    return green(provider)


def github_ssh_keys(login: str) -> list[str]:
    """Public SSH keys GitHub publishes for a user, limited to the types age accepts."""
    with urllib.request.urlopen(f"https://github.com/{login}.keys", timeout=15) as res:
        lines = res.read().decode().splitlines()
    return [k.strip() for k in lines if k.startswith(("ssh-ed25519 ", "ssh-rsa "))]


def ssh_identities() -> list[Path]:
    return [p for n in ("id_ed25519", "id_rsa") if (p := Path.home() / ".ssh" / n).exists()]


def ensure_own_github_key() -> None:
    """Make sure one of your local SSH keys is on your GitHub account.

    `./hack env share` encrypts for the keys GitHub publishes, so without one
    nobody can share the team .env with you. Creates a key if you have none.
    """
    login = output(["gh", "api", "user", "-q", ".login"])
    published = {k.split()[1] for k in github_ssh_keys(login)}
    pubs = [p.with_name(p.name + ".pub") for p in ssh_identities()]
    pubs = [p for p in pubs if p.exists()]
    if any(p.read_text().split()[1] in published for p in pubs):
        ok(f"your SSH key is on GitHub ({login})")
        return
    if not pubs:
        warn("no SSH key yet: creating ~/.ssh/id_ed25519 (a passphrase is optional)")
        (Path.home() / ".ssh").mkdir(mode=0o700, exist_ok=True)
        key = Path.home() / ".ssh" / "id_ed25519"
        run(["ssh-keygen", "-t", "ed25519", "-C", f"{login}@github", "-f", str(key)])
        pubs = [key.with_name(key.name + ".pub")]
    warn(f"adding {pubs[0]} to GitHub ({login}), so teammates can share the .env with you")
    add = ["gh", "ssh-key", "add", str(pubs[0]), "--title", "team .env (./hack)"]
    if run(add, capture=True, check=False).returncode != 0:
        # gh's default login can't manage SSH keys; ask once for that permission.
        run(["gh", "auth", "refresh", "--hostname", "github.com", "--scopes", "admin:public_key"])
        run(add)
    ok("SSH key added to GitHub")


# --------------------------------------------------------------------------- skills

_SKILLS_NOTE = (
    "Generated by `./hack skills` from .agents/skills, for Claude Code.\n"
    "Edit the skills in .agents/skills, then run ./hack skills.\n"
)


def _skill_files(base: Path) -> dict[str, bytes]:
    if not base.is_dir():
        return {}
    files = {p.relative_to(base).as_posix(): p.read_bytes() for p in base.rglob("*") if p.is_file()}
    files.pop("README.md", None)  # the note in the copy's root
    return files


def stale_skills() -> list[str]:
    """Files that differ between .agents/skills and its copy in .claude/skills."""
    src, dst = _skill_files(SKILLS_SRC), _skill_files(SKILLS_CLAUDE)
    return sorted(k for k in src.keys() | dst.keys() if src.get(k) != dst.get(k))


def sync_skills() -> list[str]:
    changed = stale_skills()
    if SKILLS_CLAUDE.exists():
        shutil.rmtree(SKILLS_CLAUDE)
    shutil.copytree(SKILLS_SRC, SKILLS_CLAUDE)
    (SKILLS_CLAUDE / "README.md").write_text(_SKILLS_NOTE, encoding="utf-8")
    return changed


# --------------------------------------------------------------------------- Supabase


def supabase_status() -> dict[str, str] | None:
    r = run(["supabase", "status", "-o", "json"], capture=True, check=False)
    if r.returncode != 0 or "{" not in r.stdout:
        return None
    try:
        return json.loads(r.stdout[r.stdout.index("{") :])
    except json.JSONDecodeError:
        return None


def ensure_supabase() -> dict[str, str]:
    status = supabase_status()
    if status is None:
        step("Starting local Supabase (the first start downloads a few GB)")
        run(["supabase", "start", "-x", SUPABASE_EXCLUDE])
        status = supabase_status()
    if status is None:
        raise Fail("Local Supabase didn't start; see the output above.")
    return status


def compose_env(status: dict[str, str]) -> dict[str, str]:
    """Values docker-compose.yml interpolates: local Supabase keys, file watching mode."""
    url = status["API_URL"]
    env = {
        "SUPABASE_URL": url,
        # The backend container reaches the host's Supabase through Docker's host alias.
        "SUPABASE_INTERNAL_URL": url.replace("127.0.0.1", "host.docker.internal").replace(
            "localhost", "host.docker.internal"
        ),
        "SUPABASE_PUBLISHABLE_KEY": status["PUBLISHABLE_KEY"],
        "SUPABASE_SECRET_KEY": status["SECRET_KEY"],
    }
    if IS_WIN:
        # File change events don't cross from Windows into containers: poll instead.
        env["WATCH_POLLING"] = "true"
    return env


# --------------------------------------------------------------------------- commands


def cmd_setup(args: argparse.Namespace) -> None:
    step("Tools")
    for name in DEV_TOOLS:
        ensure_tool(name)
    ensure_docker_running()

    step("GitHub (to receive the team's shared .env)")
    try:
        ensure_gh_auth()
        ensure_own_github_key()
    except Fail as e:
        warn(f"skipped: {e}")

    step("Backend dependencies (uv; downloads Python if needed)")
    run([uv(), "sync"], cwd=BACKEND)

    step("Frontend dependencies (npm) and Playwright's Chromium")
    run(["npm", "ci", "--no-audit", "--no-fund"], cwd=FRONTEND)
    run(
        ["npx", "playwright", "install", *(["--with-deps"] if IS_LINUX else []), "chromium"],
        cwd=FRONTEND,
    )

    step(".env")
    existed = ENV_FILE.exists()
    added = sync_env()
    if not existed:
        ok("created .env from .env.example")
    elif added:
        ok(f"added missing keys: {', '.join(added)}")
    else:
        ok(".env has every key from .env.example")
    if ENV_SHARED.exists() and not args.no_pull:
        try:
            env_pull()
        except Fail as e:
            warn(str(e).replace("\n", "\n      "))

    status = ensure_supabase()
    ok("local Supabase is running")

    step("Dev containers")
    run(["docker", "compose", "build"], env=compose_env(status))

    env = parse_env(ENV_FILE.read_text(encoding="utf-8"))
    print(f"\n{green('Setup done.')} LLM: {llm_summary(env)}\n")
    print("Next:")
    print("  ./hack env fill     fill in .env (or ./hack env pull for the team's shared values)")
    print("  ./hack dev          start the app on http://localhost:5173")


def cmd_dev(args: argparse.Namespace) -> None:
    ensure_tool("docker", install=False)
    ensure_tool("supabase", install=False)
    ensure_docker_running()
    added = sync_env()
    if added:
        warn(f".env: added missing keys {', '.join(added)}")
    env_values = parse_env(ENV_FILE.read_text(encoding="utf-8"))
    status = ensure_supabase()
    studio = status.get("STUDIO_URL", "http://127.0.0.1:54323")
    inbox = status.get("MAILPIT_URL") or status.get("INBUCKET_URL", "http://127.0.0.1:54324")
    print(f"""
  App          {bold("http://localhost:5173")}
  API docs     http://localhost:5173/api/docs
  Supabase     Studio {studio}  ·  test inbox {inbox}
  LLM          {llm_summary(env_values)}
  Stop         Ctrl+C (Supabase keeps running; ./hack stop stops it too)
""")
    sys.exit(run_foreground(["docker", "compose", "up", "--build"], env=compose_env(status)))


def cmd_stop(args: argparse.Namespace) -> None:
    # Compose checks the file's required variables even for `down`; any value will do.
    placeholders = dict.fromkeys(
        [
            "SUPABASE_URL",
            "SUPABASE_INTERNAL_URL",
            "SUPABASE_PUBLISHABLE_KEY",
            "SUPABASE_SECRET_KEY",
        ],
        "unused",
    )
    run(["docker", "compose", "down"], env=placeholders, check=False)
    run(["supabase", "stop"], check=False)


def lint() -> None:
    if stale := stale_skills():
        raise Fail(f".claude/skills is out of date ({', '.join(stale)}): run ./hack skills")
    step("Lint backend (ruff)")
    run([uv(), "run", "ruff", "check", "."], cwd=BACKEND)
    run([uv(), "run", "ruff", "format", "--check", "."], cwd=BACKEND)
    step("Lint frontend (eslint, tsc)")
    run(["npm", "run", "lint"], cwd=FRONTEND)
    run(["npm", "run", "typecheck"], cwd=FRONTEND)


def backend_tests(extra: list[str]) -> None:
    status = ensure_supabase()
    step("Backend tests (pytest, with local Supabase)")
    env = {
        "SUPABASE_URL": status["API_URL"],
        "SUPABASE_SECRET_KEY": status["SECRET_KEY"],
        "RUN_SUPABASE_TESTS": "1",
    }
    run([uv(), "run", "pytest", *extra], cwd=BACKEND, env=env)


def e2e_tests(extra: list[str]) -> None:
    status = ensure_supabase()
    step("Browser tests (Playwright)")
    env = {
        "E2E_SUPABASE_URL": status["API_URL"],
        "E2E_SUPABASE_PUBLISHABLE_KEY": status["PUBLISHABLE_KEY"],
        "E2E_SUPABASE_SECRET_KEY": status["SECRET_KEY"],
    }
    run(["npx", "playwright", "test", *extra], cwd=FRONTEND, env=env)


def cmd_lint(args: argparse.Namespace) -> None:
    lint()


def cmd_format(args: argparse.Namespace) -> None:
    run([uv(), "run", "ruff", "check", "--fix", "."], cwd=BACKEND)
    run([uv(), "run", "ruff", "format", "."], cwd=BACKEND)
    run(["npm", "run", "format"], cwd=FRONTEND)


def cmd_test(args: argparse.Namespace) -> None:
    backend_tests(args.rest)


def cmd_e2e(args: argparse.Namespace) -> None:
    e2e_tests(args.rest)


def cmd_check(args: argparse.Namespace) -> None:
    lint()
    backend_tests([])
    e2e_tests([])
    print(f"\n{green('All checks passed.')}")


def cmd_skills(args: argparse.Namespace) -> None:
    changed = sync_skills()
    ok(
        f"copied to .claude/skills: {', '.join(changed)}"
        if changed
        else ".claude/skills is up to date"
    )


def cmd_db(args: argparse.Namespace) -> None:
    if args.action == "new":
        if not args.name:
            raise Fail("Name the migration: ./hack db new add_projects")
        run(["supabase", "migration", "new", args.name])
    elif args.action == "reset":
        run(["supabase", "db", "reset"])
    elif args.action == "studio":
        status = ensure_supabase()
        print(status.get("STUDIO_URL", "http://127.0.0.1:54323"))


def cmd_env(args: argparse.Namespace) -> None:
    action = args.action or "show"
    if action == "pull":
        env_pull()
        return
    if action == "share":
        env_share()
        return
    added = sync_env()
    if added and action == "show":
        ok(f"added missing keys to .env: {', '.join(added)}")
    if action == "fill":
        env_fill()
    env_show()


def env_show() -> None:
    values = parse_env(ENV_FILE.read_text(encoding="utf-8"))
    width = max(map(len, values), default=0)
    print()
    for key, value in values.items():
        print(f"  {key.ljust(width)}  {mask(key, value)}")
    print(f"\n  LLM provider: {llm_summary(values)}")
    tracing = values.get("LANGFUSE_PUBLIC_KEY") and values.get("LANGFUSE_SECRET_KEY")
    print(f"  Langfuse:     {green('on') if tracing else dim('off (optional)')}")
    print("\n  Supabase keys aren't in .env: ./hack dev reads them from the local stack.")


def env_fill() -> None:
    print("Fill in empty values. Enter skips; secrets aren't echoed.")
    values = parse_env(ENV_FILE.read_text(encoding="utf-8"))
    updates: dict[str, str] = {}
    for key, value in values.items():
        if value:
            continue
        prompt = f"  {key}: "
        answer = (getpass.getpass(prompt) if is_secret(key) else input(prompt)).strip()
        if answer:
            updates[key] = answer
    if updates:
        write_env_values(updates)
        ok(f"saved {', '.join(updates)}")
    if ENV_SHARED.exists() or updates:
        print(dim("  Share them with your team: ./hack env share"))


def env_share() -> None:
    ensure_tool("gh")
    ensure_tool("age")
    ensure_gh_auth()
    ensure_own_github_key()  # so you can decrypt your own share
    if not ENV_FILE.exists():
        raise Fail("No .env to share yet: ./hack env fill")
    repo = github_repo()
    logins = output(
        ["gh", "api", f"repos/{repo}/collaborators", "--paginate", "-q", ".[].login"]
    ).split()
    step(f"Encrypting .env for the collaborators of {repo}")
    recipients: list[str] = []
    without: list[str] = []
    for login in logins:
        keys = github_ssh_keys(login)
        recipients += keys
        if keys:
            ok(f"{login} ({len(keys)} SSH key{'s' if len(keys) != 1 else ''})")
        else:
            without.append(login)
    for login in without:
        warn(
            f"{login} has no SSH key on GitHub and can't decrypt "
            "(they can run: gh ssh-key add ~/.ssh/id_ed25519.pub)"
        )
    if not recipients:
        raise Fail("Nobody has an SSH key on GitHub, so there's no one to encrypt for.")
    fd, recipients_file = tempfile.mkstemp(suffix=".txt")
    try:
        with os.fdopen(fd, "w") as f:
            f.write("\n".join(recipients) + "\n")
        run(
            [
                "age",
                "--encrypt",
                "--armor",
                "-R",
                recipients_file,
                "-o",
                str(ENV_SHARED),
                str(ENV_FILE),
            ]
        )
    finally:
        os.unlink(recipients_file)
    run(["git", "add", ".env.age"])
    if run(["git", "diff", "--cached", "--quiet", "--", ".env.age"], check=False).returncode == 0:
        ok(".env.age is unchanged")
        return
    run(["git", "commit", "-m", "Update shared .env", "--", ".env.age"])
    print(f"\n{green('Committed .env.age.')} Push it, then teammates run: ./hack env pull")


def env_pull() -> None:
    if not ENV_SHARED.exists():
        raise Fail("There's no .env.age yet. A teammate with the values runs: ./hack env share")
    ensure_tool("age")
    if which("gh"):
        try:
            ensure_gh_auth()
            ensure_own_github_key()
        except Fail as e:
            warn(str(e))
    identities = ssh_identities()
    if not identities:
        raise Fail(
            "No SSH key in ~/.ssh (id_ed25519 or id_rsa). Create one and add it to GitHub:\n"
            "  ssh-keygen -t ed25519\n  gh ssh-key add ~/.ssh/id_ed25519.pub\n"
            "then ask a teammate to run ./hack env share"
        )
    step("Decrypting the team .env (.env.age) with your SSH key")
    cmd = ["age", "--decrypt"]
    for path in identities:
        cmd += ["-i", str(path)]
    result = run([*cmd, str(ENV_SHARED)], capture=True, check=False)
    if result.returncode != 0:
        raise Fail(
            "Your SSH key can't decrypt .env.age: it was shared before your key was on GitHub,\n"
            "or you aren't a collaborator yet. Ask a teammate to run ./hack env share,\n"
            "then git pull."
        )
    sync_env()
    shared = parse_env(result.stdout)
    changed = write_env_values(shared)
    ok(f"updated {', '.join(changed)}" if changed else ".env already matches the team's values")


def cmd_deploy(args: argparse.Namespace) -> None:
    step("Tools")
    for name in DEPLOY_TOOLS:
        ensure_tool(name)
    ensure_gh_auth()
    repo = github_repo()

    tfvars = INFRA / "terraform.tfvars"
    if not tfvars.exists():
        example = (INFRA / "terraform.tfvars.example").read_text(encoding="utf-8")
        example = re.sub(r"(?m)^github_repository\s*=.*$", f'github_repository = "{repo}"', example)
        tfvars.write_text(example, encoding="utf-8")
        raise Fail(
            "Created infra/terraform.tfvars. Fill it in (each value says where to get it),\n"
            "then run ./hack deploy again."
        )
    env_values = parse_env(ENV_FILE.read_text(encoding="utf-8")) if ENV_FILE.exists() else {}
    if "none" in llm_summary(env_values) or "empty" in llm_summary(env_values):
        warn(f"LLM: {llm_summary(env_values)}. The deployed app gets the values from .env.")

    tf_env = {"GITHUB_TOKEN": output(["gh", "auth", "token"]), "TF_VAR_github_repository": repo}
    step("Terraform: Supabase project, Hetzner server, DNS, GitHub secrets")
    run(["terraform", f"-chdir={INFRA}", "init", "-input=false"], env=tf_env)
    run(
        ["terraform", f"-chdir={INFRA}", "apply", *(["-auto-approve"] if args.yes else [])],
        env=tf_env,
    )

    url = output(["terraform", f"-chdir={INFRA}", "output", "-raw", "url"], env=tf_env)
    step("Deploying the app (GitHub Actions)")
    if (
        run(["git", "rev-parse", "--verify", "origin/main"], capture=True, check=False).returncode
        != 0
    ):
        raise Fail(
            "main isn't on GitHub yet. Push it (git push -u origin main): that starts the deploy."
        )
    run(["gh", "workflow", "run", "ci.yml", "--ref", "main", "--repo", repo])
    print(f"""
{green("Infrastructure is ready.")} The pipeline now tests, builds and deploys main (~5 min):
  watch it     gh run watch --repo {repo}
  then open    {bold(url)}
Every push to main deploys again. After changing .env, run ./hack deploy to update production.
""")


def cmd_destroy(args: argparse.Namespace) -> None:
    ensure_tool("terraform")
    ensure_gh_auth()
    tf_env = {
        "GITHUB_TOKEN": output(["gh", "auth", "token"]),
        "TF_VAR_github_repository": github_repo(),
    }
    run(["terraform", f"-chdir={INFRA}", "destroy"], env=tf_env)


def cmd_doctor(args: argparse.Namespace) -> None:
    """Report tool versions and project state without changing anything."""
    step("Tools")
    for name, tool in TOOLS.items():
        version = tool_version(tool)
        label = f"{name} {fmt_version(version)}" if version else f"{name} missing"
        if version and version >= tool.min_version:
            ok(f"{label}  {dim(tool.why)}")
        else:
            warn(f"{label}  {dim(tool.why)}")
    print(f"    {dim(f'python {sys.version.split()[0]} (uv-managed) · {sys.platform}')}")
    step("Project")
    if ENV_FILE.exists():
        values = parse_env(ENV_FILE.read_text(encoding="utf-8"))
        _, appendix = missing_env_blocks(ENV_EXAMPLE.read_text(encoding="utf-8"), values)
        if appendix:
            warn(".env is missing keys from .env.example: run ./hack env")
        else:
            ok(".env exists")
        print(f"    LLM: {llm_summary(values)}")
    else:
        warn(".env missing: run ./hack setup")
    if which("supabase"):
        if supabase_status():
            ok("local Supabase running")
        else:
            warn("local Supabase stopped (./hack dev starts it)")


COMMANDS = {
    "setup": (
        cmd_setup,
        "install tools and dependencies, create .env, start Supabase (re-runnable)",
    ),
    "env": (
        cmd_env,
        "show .env | fill: prompt for empty values | share/pull: team .env via GitHub SSH keys",
    ),
    "dev": (cmd_dev, "run the app with hot reload on local Supabase"),
    "stop": (cmd_stop, "stop the app and local Supabase"),
    "check": (cmd_check, "lint + backend tests + browser tests (what CI runs)"),
    "lint": (cmd_lint, "ruff, eslint, tsc"),
    "format": (cmd_format, "auto-format backend and frontend"),
    "test": (cmd_test, "backend tests against local Supabase (extra args go to pytest)"),
    "e2e": (cmd_e2e, "Playwright browser tests (extra args go to playwright, e.g. --ui)"),
    "skills": (cmd_skills, "copy agent skills from .agents/skills to .claude/skills (Claude Code)"),
    "db": (cmd_db, "new <name>: migration file | reset: rebuild local DB | studio: print URL"),
    "deploy": (cmd_deploy, "create/update production with Terraform, then deploy main"),
    "destroy": (cmd_destroy, "tear production down (Terraform destroy)"),
    "doctor": (cmd_doctor, "show tool versions and project state, change nothing"),
}


def build_parser() -> argparse.ArgumentParser:
    prog = r".\hack" if IS_WIN else "./hack"
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Everything you need to work on this project.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"First time: {prog} setup, then {prog} env fill (or pull), then {prog} dev",
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")
    for name, (_, text) in COMMANDS.items():
        p = sub.add_parser(name, help=text, description=text)
        if name == "setup":
            p.add_argument("--no-pull", action="store_true", help="don't decrypt .env.age")
        if name == "env":
            p.add_argument("action", nargs="?", choices=["show", "fill", "share", "pull"])
        if name == "db":
            p.add_argument("action", choices=["new", "reset", "studio"])
            p.add_argument("name", nargs="?")
        if name == "deploy":
            p.add_argument("--yes", action="store_true", help="skip Terraform's confirmation")
        if name in ("test", "e2e"):
            p.add_argument("rest", nargs=argparse.REMAINDER)
    sub.add_parser("help", help="show this help")
    return parser


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command in (None, "help"):
        parser.print_help()
        return 0
    try:
        COMMANDS[args.command][0](args)
    except Fail as e:
        print(f"\n{red('✗')} {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
