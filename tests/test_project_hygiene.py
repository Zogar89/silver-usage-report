from pathlib import Path


def test_github_actions_ci_runs_tests_and_docker_build():
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "python -m pytest" in workflow
    assert "docker compose build" in workflow
    assert "python-version: '3.13'" in workflow


def test_candidate_collector_does_not_require_binary_build():
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")

    assert "pyinstaller" not in pyproject.lower()
    assert 'silver-usage-collector = "cli.main:main"' in pyproject
    assert not Path(".github/workflows/collector.yml").exists()
    assert not Path("app/web/static/downloads/silver-usage-collector.exe").exists()


def test_python_package_discovery_is_explicit():
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")

    assert "[tool.setuptools.packages.find]" in pyproject
    assert 'include = ["app*", "cli*"]' in pyproject
    assert 'exclude = ["tests*", "docs*", "packaging*"]' in pyproject


def test_dockerignore_excludes_local_state_and_databases():
    dockerignore = Path(".dockerignore").read_text(encoding="utf-8")

    assert ".git" in dockerignore
    assert ".pytest_cache" in dockerignore
    assert "*.db" in dockerignore
    assert "__pycache__" in dockerignore


def test_docker_compose_defines_web_and_db_healthchecks():
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "healthcheck:" in compose
    assert "pg_isready" in compose
    assert "http://127.0.0.1:8000/health" in compose
    assert "condition: service_healthy" in compose
