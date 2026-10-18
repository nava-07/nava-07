import os
import re
import sys
import requests
from html import escape

USERNAME = "nava-07"
PROFILE_REPO = "nava-07"
README_PATH = "README.md"

START_MARKER = "<!-- AUTO-PROJECTS:START -->"
END_MARKER = "<!-- AUTO-PROJECTS:END -->"

API_URL = "https://api.github.com"
TOKEN = os.getenv("GITHUB_TOKEN")

HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"


def get_public_repositories():
    repositories = []
    page = 1

    while True:
        response = requests.get(
            f"{API_URL}/users/{USERNAME}/repos",
            headers=HEADERS,
            params={
                "type": "public",
                "sort": "updated",
                "per_page": 100,
                "page": page,
            },
            timeout=30,
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


def get_readme_description(repo):
    owner = repo["owner"]["login"]
    name = repo["name"]

    response = requests.get(
        f"{API_URL}/repos/{owner}/{name}/readme",
        headers={
            **HEADERS,
            "Accept": "application/vnd.github.raw+json",
        },
        timeout=30,
    )

    if response.status_code != 200:
        return repo.get("description") or "Explore this repository."

    content = response.text

    # Remove images, HTML, links, headings, and Markdown formatting.
    content = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", content)
    content = re.sub(r"<[^>]+>", " ", content)
    content = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", content)
    content = re.sub(r"```.*?```", "", content, flags=re.DOTALL)
    content = re.sub(r"`([^`]+)`", r"\1", content)
    content = re.sub(r"^\s{0,3}#{1,6}\s*", "", content, flags=re.MULTILINE)
    content = re.sub(r"[*_~>#]", "", content)
    content = re.sub(r"\s+", " ", content).strip()

    if not content:
        return repo.get("description") or "Explore this repository."

    description = content[:180].rsplit(" ", 1)[0]

    if len(content) > 180:
        description += "..."

    return description


def generate_project_cards(repositories):
    if not repositories:
        return (
            "<p align='center'>"
            "No public projects found yet."
            "</p>"
        )

    cards = []

    for repo in repositories:
        name = escape(repo["name"])
        url = escape(repo["html_url"], quote=True)
        description = escape(get_readme_description(repo))
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
  <p><a href="{url}">View Repository →</a></p>
</td>
"""
        cards.append(card)

    rows = []

    for index in range(0, len(cards), 2):
        first_card = cards[index]
        second_card = (
            cards[index + 1]
            if index + 1 < len(cards)
            else "<td width='50%'></td>"
        )

        rows.append(f"<tr>\n{first_card}\n{second_card}\n</tr>")

    return (
        '<table width="100%">\n'
        + "\n".join(rows)
        + "\n</table>"
    )


def update_readme(project_cards):
    if not os.path.exists(README_PATH):
        raise FileNotFoundError(f"{README_PATH} was not found.")

    with open(README_PATH, "r", encoding="utf-8") as file:
        readme = file.read()

    if readme.count(START_MARKER) != 1:
        raise ValueError(
            f"README.md must contain exactly one {START_MARKER} marker."
        )

    if readme.count(END_MARKER) != 1:
        raise ValueError(
            f"README.md must contain exactly one {END_MARKER} marker."
        )

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

    print(f"Found {len(repositories)} public projects.")

    project_cards = generate_project_cards(repositories)
    update_readme(project_cards)

    print("README.md updated with project cards only.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
