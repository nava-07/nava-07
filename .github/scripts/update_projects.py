
import html
import json
import os
import re
import urllib.error
import urllib.request

USERNAME = "nava-07"
PROFILE_REPO = "nava-07"
README_PATH = "README.md"

START_MARKER = "<!-- AUTO-PROJECTS:START -->"
END_MARKER = "<!-- AUTO-PROJECTS:END -->"

API_BASE = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN", "")


def github_get(url, accept="application/vnd.github+json"):
    headers = {
        "Accept": accept,
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "nava-07-project-updater",
    }

    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"

    request = urllib.request.Request(url, headers=headers)

    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def fetch_repositories():
    repositories = []
    page = 1

    while True:
        url = (
            f"{API_BASE}/users/{USERNAME}/repos"
            f"?type=public&sort=updated&per_page=100&page={page}"
        )

        data = json.loads(github_get(url).decode("utf-8"))

        if not data:
            break

        repositories.extend(data)

        if len(data) < 100:
            break

        page += 1

    return [
        repo for repo in repositories
        if repo.get("name", "").lower() != PROFILE_REPO.lower()
        and not repo.get("fork", False)
        and not repo.get("archived", False)
        and not repo.get("disabled", False)
        and not repo.get("private", True)
    ]


def fetch_readme_description(repo):
    fallback = repo.get("description") or "No description available."

    url = f"{API_BASE}/repos/{USERNAME}/{repo['name']}/readme"

    try:
        raw = github_get(url, "application/vnd.github.raw+json")
        content = raw.decode("utf-8", errors="replace")

    except urllib.error.HTTPError as error:
        if error.code in (404, 409):
            return fallback
        raise

    except (urllib.error.URLError, TimeoutError):
        return fallback

    content = re.sub(r"<!--.*?-->", " ", content, flags=re.DOTALL)
    content = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", content)

    for paragraph in re.split(r"\n\s*\n", content):
        lines = []

        for line in paragraph.splitlines():
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            if "shields.io/" in line or "badgen.net/" in line:
                continue

            if line.startswith("<") or line.startswith("[!["):
                continue

            lines.append(line)

        description = " ".join(lines)
        description = re.sub(r"<[^>]+>", " ", description)
        description = re.sub(
            r"\[([^\]]+)\]\([^)]*\)", r"\1", description
        )
        description = re.sub(r"`([^`]+)`", r"\1", description)
        description = re.sub(r"[*_~]", "", description)
        description = re.sub(r"\s+", " ", description).strip()

        if len(description) >= 20:
            if len(description) > 220:
                description = description[:217].rsplit(" ", 1)[0] + "..."
            return description

    return fallback


def generate_project_cards(repositories):
    if not repositories:
        return "_No eligible public repositories found._"

    rows = ['<table>']

    for index in range(0, len(repositories), 2):
        rows.append("<tr>")

        for repo in repositories[index:index + 2]:
            name = html.escape(repo.get("name", "Project"))
            url = html.escape(repo.get("html_url", ""), quote=True)
            description = html.escape(fetch_readme_description(repo))
            language = html.escape(repo.get("language") or "Other")
            stars = repo.get("stargazers_count", 0)

            rows.append(f"""
<td width="50%" valign="top">
  <h3><a href="{url}">🚀 {name}</a></h3>
  <p>{description}</p>
  <p><sub>💻 {language} · ⭐ {stars}</sub></p>
</td>
""")

        if len(repositories[index:index + 2]) == 1:
            rows.append('<td width="50%"></td>')

        rows.append("</tr>")

    rows.append("</table>")
    return "\n".join(rows)


def update_readme(project_cards):
    with open(README_PATH, "r", encoding="utf-8") as file:
        readme = file.read()

    if START_MARKER not in readme or END_MARKER not in readme:
        raise ValueError("Project markers are missing from README.md.")

    start = readme.index(START_MARKER) + len(START_MARKER)
    end = readme.index(END_MARKER)

    if end < start:
        raise ValueError("Project markers are in the wrong order.")

    updated = (
        readme[:start]
        + "\n\n"
        + project_cards
        + "\n\n"
        + readme[end:]
    )

    with open(README_PATH, "w", encoding="utf-8") as file:
        file.write(updated)

    print("Project cards generated successfully.")


def main():
    print(f"Fetching repositories for {USERNAME}...")

    repositories = fetch_repositories()
    print(f"Found {len(repositories)} eligible public repositories.")

    cards = generate_project_cards(repositories)
    update_readme(cards)


if __name__ == "__main__":
    main()
