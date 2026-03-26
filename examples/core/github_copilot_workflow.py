# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Joseph Webber <joseph.webber@me.com>
"""
GitHub Copilot-Enhanced Development Workflow.

This example demonstrates how agentic-brain complements GitHub Copilot
for AI-assisted development tasks:

- PR description generation from commits/diffs
- Code review with AI-powered analysis
- Issue triage and labeling
- Commit message suggestions

Works alongside GitHub Copilot - we handle the automation,
Copilot handles the code generation.

Usage:
    export GITHUB_TOKEN=ghp_xxxxxxxxxxxx
    python examples/core/github_copilot_workflow.py

Requirements:
    pip install agentic-brain[github]
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any

from agentic_brain import Chatbot, LLMRouter, RouterConfig


@dataclass
class GitHubConfig:
    """GitHub API configuration."""

    token: str
    owner: str = ""
    repo: str = ""
    base_url: str = "https://api.github.com"

    @classmethod
    def from_env(cls) -> GitHubConfig:
        """Load config from environment."""
        token = os.getenv("GITHUB_TOKEN", "")
        if not token:
            raise ValueError("GITHUB_TOKEN environment variable required")
        return cls(
            token=token,
            owner=os.getenv("GITHUB_OWNER", ""),
            repo=os.getenv("GITHUB_REPO", ""),
        )


class GitHubHelper:
    """
    GitHub API helper for AI-assisted development workflows.

    Complements GitHub Copilot by handling automation tasks:
    - PR description generation
    - Code review analysis
    - Issue triage
    - Commit message suggestions
    """

    def __init__(self, config: GitHubConfig) -> None:
        """Initialize with GitHub configuration."""
        self.config = config
        self._headers = {
            "Authorization": f"Bearer {config.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def get_pull_request(self, owner: str, repo: str, pr_number: int) -> dict:
        """Fetch PR details from GitHub API."""
        import aiohttp

        url = f"{self.config.base_url}/repos/{owner}/{repo}/pulls/{pr_number}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self._headers) as resp:
                if resp.status != 200:
                    raise ValueError(f"GitHub API error: {resp.status}")
                return await resp.json()

    async def get_pr_diff(self, owner: str, repo: str, pr_number: int) -> str:
        """Fetch PR diff for code review."""
        import aiohttp

        url = f"{self.config.base_url}/repos/{owner}/{repo}/pulls/{pr_number}"
        headers = {**self._headers, "Accept": "application/vnd.github.v3.diff"}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    raise ValueError(f"GitHub API error: {resp.status}")
                return await resp.text()

    async def get_commits(
        self, owner: str, repo: str, pr_number: int
    ) -> list[dict[str, Any]]:
        """Fetch commits in a PR."""
        import aiohttp

        url = f"{self.config.base_url}/repos/{owner}/{repo}/pulls/{pr_number}/commits"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self._headers) as resp:
                if resp.status != 200:
                    raise ValueError(f"GitHub API error: {resp.status}")
                return await resp.json()

    async def get_issue(self, owner: str, repo: str, issue_number: int) -> dict:
        """Fetch issue details."""
        import aiohttp

        url = f"{self.config.base_url}/repos/{owner}/{repo}/issues/{issue_number}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self._headers) as resp:
                if resp.status != 200:
                    raise ValueError(f"GitHub API error: {resp.status}")
                return await resp.json()

    async def list_issues(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        labels: str = "",
        limit: int = 10,
    ) -> list[dict]:
        """List repository issues."""
        import aiohttp

        url = f"{self.config.base_url}/repos/{owner}/{repo}/issues"
        params = {"state": state, "per_page": limit}
        if labels:
            params["labels"] = labels

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self._headers, params=params) as resp:
                if resp.status != 200:
                    raise ValueError(f"GitHub API error: {resp.status}")
                return await resp.json()


class CopilotWorkflow:
    """
    AI-assisted development workflow that complements GitHub Copilot.

    While Copilot handles code generation in your editor, this workflow
    handles the broader development automation:

    - Generating PR descriptions from commits
    - AI-powered code review
    - Issue triage and labeling
    - Commit message suggestions

    Usage:
        workflow = CopilotWorkflow.create()

        # Generate PR description
        description = await workflow.generate_pr_description(
            owner="myorg",
            repo="myrepo",
            pr_number=42
        )

        # Review code changes
        review = await workflow.review_pull_request(
            owner="myorg",
            repo="myrepo",
            pr_number=42
        )
    """

    def __init__(
        self,
        github: GitHubHelper,
        llm: LLMRouter,
        chatbot: Chatbot | None = None,
    ) -> None:
        """Initialize workflow with GitHub and LLM clients."""
        self.github = github
        self.llm = llm
        self.chatbot = chatbot or Chatbot(name="copilot-workflow")

    @classmethod
    def create(cls) -> CopilotWorkflow:
        """Factory method to create workflow with default config."""
        config = GitHubConfig.from_env()
        github = GitHubHelper(config)
        llm = LLMRouter(
            RouterConfig(
                default_model="llama3.1:8b",  # Works great locally
            )
        )
        return cls(github=github, llm=llm)

    async def generate_pr_description(
        self,
        owner: str,
        repo: str,
        pr_number: int,
    ) -> str:
        """
        Generate a professional PR description from commits and diff.

        Analyzes the commits and code changes to produce a clear,
        well-structured PR description suitable for code review.
        """
        # Fetch PR data
        pr = await self.github.get_pull_request(owner, repo, pr_number)
        commits = await self.github.get_commits(owner, repo, pr_number)
        diff = await self.github.get_pr_diff(owner, repo, pr_number)

        # Truncate diff if too large
        max_diff_chars = 8000
        if len(diff) > max_diff_chars:
            diff = diff[:max_diff_chars] + "\n... (truncated)"

        # Build context
        commit_messages = "\n".join(
            f"- {c['commit']['message'].split(chr(10))[0]}" for c in commits[:10]
        )

        prompt = f"""Generate a professional PR description for this pull request.

**PR Title:** {pr['title']}
**Branch:** {pr['head']['ref']} → {pr['base']['ref']}

**Commits:**
{commit_messages}

**Code Changes (diff):**
```diff
{diff}
```

Write a clear PR description with:
1. **Summary** - What this PR does (2-3 sentences)
2. **Changes** - Bullet points of key changes
3. **Testing** - How to test these changes
4. **Notes** - Any reviewer notes or considerations

Keep it concise and professional."""

        response = await self.llm.chat(prompt)
        return response.content

    async def review_pull_request(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        focus_areas: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Perform AI-powered code review on a pull request.

        Analyzes code changes for:
        - Potential bugs or issues
        - Security concerns
        - Performance implications
        - Code style and best practices

        Returns structured review with comments and suggestions.
        """
        diff = await self.github.get_pr_diff(owner, repo, pr_number)
        pr = await self.github.get_pull_request(owner, repo, pr_number)

        # Truncate diff if too large
        max_diff_chars = 12000
        if len(diff) > max_diff_chars:
            diff = diff[:max_diff_chars] + "\n... (truncated)"

        focus_str = ""
        if focus_areas:
            focus_str = f"\n**Focus areas:** {', '.join(focus_areas)}"

        prompt = f"""Review this pull request code changes.

**PR:** {pr['title']}
**Files changed:** {pr['changed_files']}
**Additions:** +{pr['additions']} **Deletions:** -{pr['deletions']}
{focus_str}

**Diff:**
```diff
{diff}
```

Provide a code review with:
1. **Summary** - Overall assessment (approve/request changes/comment)
2. **Issues** - Any bugs, security issues, or problems found (with line references)
3. **Suggestions** - Improvements or best practices to consider
4. **Positives** - Good things about this PR

Be constructive and specific. Reference line numbers where relevant."""

        response = await self.llm.chat(prompt)

        return {
            "pr_number": pr_number,
            "title": pr["title"],
            "review": response.content,
            "model": response.model,
            "tokens_used": response.tokens_used,
        }

    async def triage_issue(
        self,
        owner: str,
        repo: str,
        issue_number: int,
    ) -> dict[str, Any]:
        """
        Analyze and triage a GitHub issue.

        Suggests:
        - Labels to apply
        - Priority level
        - Potential assignees (based on file paths mentioned)
        - Related issues or duplicates
        """
        issue = await self.github.get_issue(owner, repo, issue_number)

        prompt = f"""Analyze this GitHub issue and suggest triage actions.

**Title:** {issue['title']}
**Author:** {issue['user']['login']}
**Created:** {issue['created_at']}

**Body:**
{issue.get('body', 'No description provided.')}

Provide:
1. **Type** - bug, feature, documentation, question, etc.
2. **Priority** - critical, high, medium, low
3. **Labels** - Suggested labels to apply
4. **Summary** - One-line summary of the issue
5. **Next Steps** - Recommended actions

Be concise and actionable."""

        response = await self.llm.chat(prompt)

        return {
            "issue_number": issue_number,
            "title": issue["title"],
            "triage": response.content,
            "current_labels": [l["name"] for l in issue.get("labels", [])],
        }

    async def suggest_commit_message(
        self,
        diff: str,
        style: str = "conventional",
    ) -> str:
        """
        Generate a commit message from a diff.

        Styles:
        - conventional: feat(scope): description
        - simple: Clear description of changes
        - detailed: Multi-line with body
        """
        # Truncate diff if too large
        max_chars = 6000
        if len(diff) > max_chars:
            diff = diff[:max_chars] + "\n... (truncated)"

        style_instructions = {
            "conventional": "Use Conventional Commits format: type(scope): description",
            "simple": "Use a clear, concise single-line message",
            "detailed": "Use a summary line, blank line, then detailed body",
        }

        prompt = f"""Generate a commit message for these changes.

{style_instructions.get(style, style_instructions['conventional'])}

**Diff:**
```diff
{diff}
```

Return ONLY the commit message, no explanation."""

        response = await self.llm.chat(prompt)
        return response.content.strip()


async def main() -> None:
    """Demonstrate Copilot-enhanced workflow."""
    print("🤖 GitHub Copilot-Enhanced Workflow Demo")
    print("=" * 50)

    # Check for token
    if not os.getenv("GITHUB_TOKEN"):
        print("\n⚠️  GITHUB_TOKEN not set")
        print("Set it to try the GitHub integration:")
        print("  export GITHUB_TOKEN=ghp_xxxxxxxxxxxx")
        print("\nDemonstrating with mock data instead...\n")

        # Demo with mock diff
        llm = LLMRouter()
        mock_diff = """
diff --git a/src/auth.py b/src/auth.py
index 1234567..abcdefg 100644
--- a/src/auth.py
+++ b/src/auth.py
@@ -10,6 +10,15 @@ def authenticate(username: str, password: str) -> bool:
+    # Add rate limiting
+    if is_rate_limited(username):
+        raise RateLimitError("Too many attempts")
+
     user = get_user(username)
     if not user:
         return False
+
+    # Log authentication attempt
+    log_auth_attempt(username, success=True)
     return verify_password(password, user.password_hash)
"""

        workflow = CopilotWorkflow(
            github=GitHubHelper(GitHubConfig(token="mock")),
            llm=llm,
        )

        print("📝 Generating commit message from diff...")
        message = await workflow.suggest_commit_message(mock_diff)
        print(f"\nSuggested commit message:\n{message}\n")

        return

    # Real workflow with GitHub
    workflow = CopilotWorkflow.create()

    # Example: Generate PR description
    # Uncomment and modify with your repo details:
    #
    # description = await workflow.generate_pr_description(
    #     owner="your-org",
    #     repo="your-repo",
    #     pr_number=123
    # )
    # print(f"Generated PR Description:\n{description}")

    print("✅ Workflow ready!")
    print("\nUsage example:")
    print(
        """
    workflow = CopilotWorkflow.create()
    
    # Generate PR description
    desc = await workflow.generate_pr_description("owner", "repo", 42)
    
    # Review PR
    review = await workflow.review_pull_request("owner", "repo", 42)
    
    # Triage issue  
    triage = await workflow.triage_issue("owner", "repo", 100)
    """
    )


if __name__ == "__main__":
    asyncio.run(main())
