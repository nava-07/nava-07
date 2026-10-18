
import json
import os
import urllib.request
from pathlib import Path

USERNAME = "nava-07"
README_PATH = Path("README.md")

START_MARKER = "<!-- AUTO-PROJECTS:START -->"
END_MARKER = "<!-- AUTO-PROJECTS:END -->"

TOKEN = os.environ.get("GITHUB_TOKEN")

if not TOKEN:
    raise RuntimeError("GITHUB_TOKEN is missing.")


def fetch_repositories():
    repositories = []
    page = 1

    while True:
        url = (
            f"https://api.github.com/users/{USERNAME}/repos"
            f"?type=owner&sort=updated&per_page=100&page={page}"
        )

        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {TOKEN}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "GitHub-Profile-Updater",
            },
        )

        with urllib.request.urlopen(request, timeout=30) as response:
            batch = json.load(response)

        if not batch:
            break

        repositories.extend(batch)

        if len(batch) < 100:
            break

        page += 1

    return repositories


def escape_markdown(value):
    return (
        str(value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("|", "\\|")
        .replace("\r", " ")
        .replace("\n", " ")
        .strip()
    )


def build_project_list(repositories):
    # Show all public, owned, non-archived repositories.
    # Exclude only the profile README repository itself.
    projects = [
        repo for repo in repositories
        if not repo.get("private", False)
        and not repo.get("fork", False)
        and not repo.get("archived", False)
        and repo["name"].lower() != USERNAME.lower()
    ]

    projects.sort(
        key=lambda repo: repo["name"].lower()
    )

    if not projects:
        return "_No public project repositories found yet._"

    lines = [
        "| Repository | Description | Language | Stars |",
        "|---|---|---|---:|",
    ]

    for repo in projects:
        name = escape_markdown(repo["name"])
        description = escape_markdown(
            repo.get("description") or "No description added yet."
        )
        language = escape_markdown(
            repo.get("language") or "Not specified"
        )
        stars = repo.get("stargazers_count", 0)
        url = repo["html_url"]

        lines.append(
            f"| [{name}]({url}) | {description} | "
            f"{language} | ⭐ {stars} |"
        )

    return "\n".join(lines)


def update_readme(project_list):
    if not README_PATH.exists():
        raise FileNotFoundError("README.md not found.")

    readme = README_PATH.read_text(encoding="utf-8")

    if readme.count(START_MARKER) != 1:
        raise ValueError(
            "README must contain exactly one AUTO-PROJECTS:START marker."
        )

    if readme.count(END_MARKER) != 1:
        raise ValueError(
            "README must contain exactly one AUTO-PROJECTS:END marker."
        )

    start = readme.index(START_MARKER) + len(START_MARKER)
    end = readme.index(END_MARKER)

    if start >= end:
        raise ValueError("Project markers are in the wrong order.")

    updated_readme = (
        readme[:start]
        + "\n\n"
        + project_list
        + "\n\n"
        + readme[end:]
    )

    if updated_readme == readme:
        print("Project list is already up to date.")
        return

    README_PATH.write_text(updated_readme, encoding="utf-8")
    print("README updated successfully.")


def main():
    repositories = fetch_repositories()
    project_list = build_project_list(repositories)
    update_readme(project_list)

    print(f"Fetched {len(repositories)} public repositories.")
    print("Profile project list generation completed.")


if __name__ == "__main__":
    main()
