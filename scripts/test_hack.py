"""Unit tests for the pure parts of scripts/hack.py: uv run --with pytest pytest scripts"""

import shutil
import subprocess

import pytest

import hack

EXAMPLE = """\
# Header comment
# --- LLM ---
LLM_PROVIDER=auto
# Partner key
ANTHROPIC_API_KEY=

# --- Langfuse ---
LANGFUSE_BASE_URL=https://cloud.langfuse.com
"""


def test_parse_env_handles_comments_quotes_and_duplicates():
    text = '# c\n\nA=1\nexport B="two words"\nC=x=y\nnot a line\nA=3\r\nD=\n'
    assert hack.parse_env(text) == {"A": "3", "B": "two words", "C": "x=y", "D": ""}


def test_missing_keys_are_appended_with_their_comments():
    added, appendix = hack.missing_env_blocks(EXAMPLE, {"LLM_PROVIDER": "openai"})
    assert added == ["ANTHROPIC_API_KEY", "LANGFUSE_BASE_URL"]
    assert "# Partner key\nANTHROPIC_API_KEY=" in appendix
    assert "LLM_PROVIDER" not in appendix


def test_nothing_missing_means_no_appendix():
    assert hack.missing_env_blocks(EXAMPLE, hack.parse_env(EXAMPLE)) == ([], "")


def test_sync_env_creates_then_only_appends(tmp_path, monkeypatch):
    example, env = tmp_path / ".env.example", tmp_path / ".env"
    example.write_text(EXAMPLE)
    monkeypatch.setattr(hack, "ENV_EXAMPLE", example)
    monkeypatch.setattr(hack, "ENV_FILE", env)

    hack.sync_env()
    assert env.read_text() == EXAMPLE

    env.write_text("ANTHROPIC_API_KEY=sk-mine\nEXTRA=kept\n")
    assert hack.sync_env() == ["LLM_PROVIDER", "LANGFUSE_BASE_URL"]
    values = hack.parse_env(env.read_text())
    assert values["ANTHROPIC_API_KEY"] == "sk-mine"  # never overwritten
    assert values["EXTRA"] == "kept"
    assert values["LLM_PROVIDER"] == "auto"


def test_update_env_text_replaces_in_place_and_appends_new_keys():
    text, changed = hack.update_env_text("# keep\nA=1\nB=2\n", {"B": "3", "C": "4", "A": "1"})
    assert text == "# keep\nA=1\nB=3\nC=4\n"
    assert changed == ["B", "C"]


def test_parse_version():
    assert hack.parse_version("Docker version 29.8.2, build 7fc2dff") == (29, 8, 2)
    assert hack.parse_version("v24.2.0") == (24, 2, 0)
    assert hack.parse_version("Terraform v1.14.9\non darwin_arm64") == (1, 14, 9)
    assert hack.parse_version("2.101.0") >= (2, 50)
    assert hack.parse_version("nothing") is None


def test_llm_summary_mirrors_backend_auto_detection():
    assert "anthropic" in hack.llm_summary({"ANTHROPIC_API_KEY": "k", "OPENAI_API_KEY": "k"})
    assert "openai" in hack.llm_summary({"OPENAI_API_KEY": "k"})
    assert "gemini" in hack.llm_summary({"GOOGLE_API_KEY": "k"})
    assert "none" in hack.llm_summary({})
    assert "empty" in hack.llm_summary({"LLM_PROVIDER": "openai"})


def test_compose_env_points_the_container_at_the_host(monkeypatch):
    monkeypatch.setattr(hack, "IS_WIN", False)
    status = {"API_URL": "http://127.0.0.1:54321", "PUBLISHABLE_KEY": "p", "SECRET_KEY": "s"}
    env = hack.compose_env(status)
    assert env["SUPABASE_URL"] == "http://127.0.0.1:54321"
    assert env["SUPABASE_INTERNAL_URL"] == "http://host.docker.internal:54321"
    assert "WATCH_POLLING" not in env
    monkeypatch.setattr(hack, "IS_WIN", True)
    assert hack.compose_env(status)["WATCH_POLLING"] == "true"


def test_mask_hides_secrets_only():
    assert hack.mask("LLM_PROVIDER", "anthropic") == "anthropic"
    assert "sk-ant-api03" not in hack.mask("ANTHROPIC_API_KEY", "sk-ant-api03-abcdefghijkl")


def test_every_command_has_help():
    parser = hack.build_parser()
    for name in hack.COMMANDS:
        assert parser.parse_args([name] + (["new"] if name == "db" else [])).command == name


@pytest.mark.skipif(not (shutil.which("age") and shutil.which("ssh-keygen")), reason="needs age")
def test_env_share_then_pull_round_trip(tmp_path, monkeypatch):
    """Real age encryption to a GitHub-style SSH key; GitHub API and git are faked."""
    home = tmp_path / "home"
    (home / ".ssh").mkdir(parents=True)
    key = home / ".ssh" / "id_ed25519"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
    monkeypatch.setattr(hack.Path, "home", lambda: home)

    for name, attr in [
        (".env.example", "ENV_EXAMPLE"),
        (".env", "ENV_FILE"),
        (".env.age", "ENV_SHARED"),
    ]:
        monkeypatch.setattr(hack, attr, tmp_path / name)
    hack.ENV_EXAMPLE.write_text(EXAMPLE)
    hack.ENV_FILE.write_text("ANTHROPIC_API_KEY=sk-team\nLLM_PROVIDER=auto\n")

    keys = {"alice": [key.with_suffix(".pub").read_text().strip()], "bob": []}
    monkeypatch.setattr(hack, "ensure_tool", lambda *a, **k: None)
    monkeypatch.setattr(hack, "ensure_gh_auth", lambda: None)
    monkeypatch.setattr(hack, "ensure_own_github_key", lambda: None)
    monkeypatch.setattr(hack, "github_repo", lambda: "team/app")
    monkeypatch.setattr(hack, "github_ssh_keys", lambda login: keys[login])
    real_run, git_calls = hack.run, []

    def fake_run(cmd, **kw):
        if cmd[:2] == ["gh", "api"]:
            return subprocess.CompletedProcess(cmd, 0, "alice\nbob\n", "")
        if cmd[0] == "git":
            git_calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 1 if cmd[1] == "diff" else 0, "", "")
        return real_run(cmd, **kw)

    monkeypatch.setattr(hack, "run", fake_run)

    hack.env_share()
    assert "BEGIN AGE ENCRYPTED FILE" in hack.ENV_SHARED.read_text()
    assert "sk-team" not in hack.ENV_SHARED.read_text()
    assert ["git", "commit", "-m", "Update shared .env", "--", ".env.age"] in git_calls

    # A teammate with an older .env pulls: shared values win, local-only keys stay.
    hack.ENV_FILE.write_text("ANTHROPIC_API_KEY=\nMY_LOCAL=1\n")
    hack.env_pull()
    values = hack.parse_env(hack.ENV_FILE.read_text())
    assert values["ANTHROPIC_API_KEY"] == "sk-team"
    assert values["MY_LOCAL"] == "1"
    assert values["LANGFUSE_BASE_URL"] == "https://cloud.langfuse.com"  # synced from example


def test_claude_skills_copy_is_current():
    # Fails when a skill in .agents/skills changed without ./hack skills.
    assert hack.stale_skills() == []


def test_sync_skills_mirrors_and_removes(tmp_path, monkeypatch):
    src, dst = tmp_path / "src", tmp_path / "dst"
    (src / "a").mkdir(parents=True)
    (src / "a" / "SKILL.md").write_text("---\nname: a\n---\n")
    (dst / "old").mkdir(parents=True)
    (dst / "old" / "SKILL.md").write_text("gone")
    monkeypatch.setattr(hack, "SKILLS_SRC", src)
    monkeypatch.setattr(hack, "SKILLS_CLAUDE", dst)

    assert hack.stale_skills() == ["a/SKILL.md", "old/SKILL.md"]
    hack.sync_skills()
    assert hack.stale_skills() == []
    assert not (dst / "old").exists()
    assert "Generated" in (dst / "README.md").read_text()
