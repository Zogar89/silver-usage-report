from pathlib import Path


def test_agent_prompt_template_defines_privacy_and_preview_contract():
    prompt = Path("mcp_server/prompts/agent-assisted-import.md").read_text(encoding="utf-8")

    assert "Do not upload prompts" in prompt
    assert "Do not upload responses" in prompt
    assert "Do not upload API keys" in prompt
    assert "preview before submit" in prompt
    assert "UsageReportRow" in prompt
    assert "confidence" in prompt
