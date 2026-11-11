
import os
import sys
import requests
from html import escape
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USERNAME = "nava-07"
PROFILE_REPO = "nava-07"
README_PATH = "README.md"

START_MARKER = "<!-- AUTO-PROJECTS:START -->"
END_MARKER = "<!-- AUTO-PROJECTS:END -->"

API_URL = "https://api.github.com"

TOKEN = os.getenv("GITHUB_TOKEN")

session = requests.Session()

retry_strategy = Retry(
    total=4,
    backoff_factor=2,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"]
)

adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("https://", adapter)

HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"

session.headers.update(HEADERS)


def get_public_repositories():
    repositories = []
    page = 1

    while True:
        response = session.get(
            f"{API_URL}/users/{USERNAME}/repos",
            params={
                "type": "public",
                "sort": "updated",
                "per_page": 100,
                "page": page
            },
            timeout=30
        )

        response.raise_for_status()
        batch = response.json()

        if not batch:
            break

        repositories.extend(batch)

        if len(batch) < 100:
            break

        page += 1

    return [
        repo for repo in repositories
        if repo["name"].lower() != PROFILE_REPO.lower()
        and not repo.get("fork", False)
        and not repo.get("archived", False)
        and not repo.get("disabled", False)
        and not repo.get("private", False)
    ]


def generate_project_cards(repositories):
    if not repositories:
        return """
<p align="center">
  No public projects found yet.
</p>
"""

    cards = []

    for repo in repositories:
        name = escape(repo["name"])
        url = escape(repo["html_url"], quote=True)
        description = escape(
            repo.get("description") or "Explore this project and its implementation."
        )
        language = escape(repo.get("language") or "Various")
        stars = repo.get("stargazers_count", 0)

        card = f"""
<td width="50%" valign="top">
  <h3>
    <a href="{url}">{name}</a>
  </h3>
  <p>{description}</p>
  <p>
    <strong>Language:</strong> {language}
    &nbsp;·&nbsp;
    <strong>Stars:</strong> ⭐ {stars}
  </p>
  <p>
    <a href="{url}">View Repository →</a>
  </p>
</td>
"""
        cards.append(card)

    rows = []

    for index in range(0, len(cards), 2):
        first = cards[index]
        second = (
            cards[index + 1]
            if index + 1 < len(cards)
            else "<td width='50%'></td>"
        )

        rows.append(f"<tr>\n{first}\n{second}\n</tr>")

    return (
        '<table width="100%">\n'
        + "\n".join(rows)
        + "\n</table>"
    )


def update_readme(project_cards):
    if not os.path.exists(README_PATH):
        raise FileNotFoundError("README.md was not found.")

    with open(README_PATH, "r", encoding="utf-8") as file:
        readme = file.read()

    if readme.count(START_MARKER) != 1:
        raise ValueError("START marker must appear exactly once.")

    if readme.count(END_MARKER) != 1:
        raise ValueError("END marker must appear exactly once.")

    start = readme.index(START_MARKER) + len(START_MARKER)
    end = readme.index(END_MARKER)

    if start > end:
        raise ValueError("Project markers are in the wrong order.")

    updated_readme = (
        readme[:start]
        + "\n\n"
        + project_cards
        + "\n\n"
        + readme[end:]
    )

    with open(README_PATH, "w", encoding="utf-8") as file:
        file.write(updated_readme)


def main():
    print("Fetching public repositories...")

    repositories = get_public_repositories()

    print(f"Found {len(repositories)} eligible repositories.")

    project_cards = generate_project_cards(repositories)

    update_readme(project_cards)

    print("SUCCESS: Featured projects updated.")


if __name__ == "__main__":
    try:
        main()
    except requests.RequestException as error:
        print(f"GitHub API ERROR: {error}", file=sys.stderr)
        sys.exit(1)
    except Exception as error:
        print(f"UPDATE ERROR: {error}", file=sys.stderr)
        sys.exit(1)
