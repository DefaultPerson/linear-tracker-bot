from __future__ import annotations

import re
from datetime import datetime
from typing import List, Optional

import httpx

LINEAR_API_URL = "https://api.linear.app/graphql"


class LinearClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "LinearClient":
        self.client = httpx.AsyncClient(
            base_url=LINEAR_API_URL,
            headers={
                "Authorization": self.api_key,
                "Content-Type": "application/json",
            },
        )
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self.client is not None:
            await self.client.aclose()

    async def _query(self, query: str, variables: Optional[dict] = None) -> dict:
        assert self.client is not None
        payload = {"query": query, "variables": variables or {}}
        resp = await self.client.post("", json=payload, timeout=30)
        # Try to parse GraphQL response even on non-200 to surface GraphQL errors
        try:
            data = resp.json()
        except Exception:
            resp.raise_for_status()
            # If still no JSON and status OK, return empty
            return {}
        if "errors" in data:
            raise RuntimeError(f"Linear API error: {data['errors']}")
        if resp.status_code != 200:
            raise RuntimeError(f"Linear API HTTP {resp.status_code}: {data}")
        return data.get("data", {})

    async def get_in_progress_issues(
        self,
        team_id: Optional[str] = None,
        team_keys: Optional[List[str]] = None,
        include_unstarted: bool = False,
    ) -> List[dict]:
        # Build state filter based on include_unstarted flag
        if include_unstarted:
            state_filter = 'state: { type: { in: ["started", "unstarted"] } }'
        else:
            state_filter = 'state: { type: { eq: "started" } }'

        if team_id:
            query = f"""
            query($teamId: String) {{
              issues(
                filter: {{
                  {state_filter}
                  team: {{ id: {{ eq: $teamId }} }}
                }},
                first: 100
              ) {{
                nodes {{ id title url assignee {{ name }} state {{ name type }} team {{ key id }} }}
              }}
            }}
            """
            variables = {"teamId": team_id}
        else:
            query = f"""
            query {{
              issues(
                filter: {{
                  {state_filter}
                }},
                first: 100
              ) {{
                nodes {{ id title url assignee {{ name }} state {{ name type }} team {{ key id }} }}
              }}
            }}
            """
            variables = {}
        data = await self._query(query, variables)
        nodes = data["issues"]["nodes"]
        if team_keys:
            keys = set(team_keys)
            nodes = [n for n in nodes if (n.get("team") or {}).get("key") in keys]
        return nodes

    async def get_done_issues_since(
        self,
        since: datetime,
        team_id: Optional[str] = None,
        team_keys: Optional[List[str]] = None,
    ) -> List[dict]:
        iso = since.isoformat()
        if team_id:
            query = """
            query($teamId: String, $since: DateTimeOrDuration!) {
              issues(
                filter: {
                  state: { type: { eq: "completed" } }
                  completedAt: { gte: $since }
                  team: { id: { eq: $teamId } }
                },
                first: 100
              ) {
                nodes { id title url assignee { name } state { name type } completedAt team { key id } }
              }
            }
            """
            variables = {"teamId": team_id, "since": iso}
        else:
            query = """
            query($since: DateTimeOrDuration!) {
              issues(
                filter: {
                  state: { type: { eq: "completed" } }
                  completedAt: { gte: $since }
                },
                first: 100
              ) {
                nodes { id title url assignee { name } state { name type } completedAt team { key id } }
              }
            }
            """
            variables = {"since": iso}
        data = await self._query(query, variables)
        nodes = data["issues"]["nodes"]
        if team_keys:
            keys = set(team_keys)
            nodes = [n for n in nodes if (n.get("team") or {}).get("key") in keys]
        return nodes

    async def get_issues_updated_since(
        self,
        since: datetime,
        team_id: Optional[str] = None,
        team_keys: Optional[List[str]] = None,
    ) -> List[dict]:
        iso = since.isoformat()
        # Include attachments for GitHub link detection, createdAt for new issue detection
        issue_fields = """
            id title url assignee { name } state { name type }
            createdAt updatedAt team { key id }
            attachments { nodes { url title } }
        """
        if team_id:
            query = f"""
            query($teamId: String, $since: DateTimeOrDuration!) {{
              issues(
                filter: {{
                  updatedAt: {{ gte: $since }}
                  team: {{ id: {{ eq: $teamId }} }}
                }},
                orderBy: updatedAt,
                first: 200
              ) {{
                nodes {{ {issue_fields} }}
              }}
            }}
            """
            variables = {"teamId": team_id, "since": iso}
        else:
            query = f"""
            query($since: DateTimeOrDuration!) {{
              issues(
                filter: {{
                  updatedAt: {{ gte: $since }}
                }},
                orderBy: updatedAt,
                first: 200
              ) {{
                nodes {{ {issue_fields} }}
              }}
            }}
            """
            variables = {"since": iso}
        data = await self._query(query, variables)
        nodes = data["issues"]["nodes"]
        if team_keys:
            keys = set(team_keys)
            nodes = [n for n in nodes if (n.get("team") or {}).get("key") in keys]
        return nodes


def map_assignee_to_mention(name: Optional[str], mapping: dict) -> str:
    if not name:
        return ""
    tg = mapping.get(name)
    return f"@{tg}" if tg else name


GITHUB_ISSUE_PATTERN = re.compile(r"https?://github\.com/[^/]+/[^/]+/issues/\d+")


def extract_github_issue_link(issue: dict) -> Optional[str]:
    """Extract first GitHub issue URL from issue attachments."""
    attachments = (issue.get("attachments") or {}).get("nodes") or []
    for att in attachments:
        url = att.get("url") or ""
        if GITHUB_ISSUE_PATTERN.match(url):
            return url
    return None
