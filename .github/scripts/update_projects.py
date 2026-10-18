
import json
import os
import urllib.request
from pathlib import Path

# ================= CONFIGURATION =================

USERNAME = "nava-07"
README_PATH = Path("README.md")

START_MARKER = "<!-- AUTO-PROJECTS:START -->"
END_MARKER = "<!-- AUTO-PROJECTS:END -->"

# GitHub Actions provides this token automatically.
TOKEN = os.environ.get("GITHUB_TOKEN")

if not TOKEN:
    raise RuntimeError("GITHUB_TOKEN environment variable is missing.")


# ================= FETCH REPOSITORIES =================

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


# ================= FORMAT PROJECT LIST =================

def escape_markdown(value):
    """Keep generated Markdown fields on one line."""
    return (
        str(value or "")
        .replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("\r", " ")
        .replace("\n", " ")
        .strip()
    )


def build_project_list(repositories):
    # Exclude the profile repository, forks, and archived projects.
    projects = [
        repo for repo in repositories
        if not repo.get("private", False)
        and not repo.get("fork", False)
        and not repo.get("archived", False)
        and repo["name"].lower() != USERNAME.lower()
    ]

    # Sort alphabetically for a consistent profile.
    projects.sort(key=lambda repo: repo["name"].lower())

    lines = []

    for repo in projects:
        name = escape_markdown(repo["name"])
        description = escape_markdown(repo.get("description"))
        language = escape_markdown(repo.get("language"))
        stars = repo.get("stargazers_count", 0)
        url = repo["html_url"]

        if not description:
            description = "No description added yet."

        if not language:
            language = "Not specified"

        lines.append(
            f"- 📦 **[{name}]({url})** — {description}  \n"
            f"  💻 `{language}` · ⭐ {stars}"
        )

    if not lines:
        return "_No public repositories found yet._"

    return "\n\n".join(lines)


# ================= UPDATE README =================

def update_readme(project_list):
    if not README_PATH.exists():
        raise FileNotFoundError("README.md was not found.")

    readme = README_PATH.read_text(encoding="utf-8")

    if readme.count(START_MARKER) != 1:
        raise ValueError(
            "README.md must contain exactly one AUTO-PROJECTS:START marker."
        )

    if readme.count(END_MARKER) != 1:
        raise ValueError(
            "README.md must contain exactly one AUTO-PROJECTS:END marker."
        )

    start = readme.index(START_MARKER) + len(START_MARKER)
    end = readme.index(END_MARKER)

    if start >= end:
        raise ValueError("The project markers are in the wrong order.")

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
    print("README.md updated successfully.")


# ================= MAIN =================

def main():
    repositories = fetch_repositories()
    project_list = build_project_list(repositories)
    update_readme(project_list)

    print(
        f"Processed {len(repositories)} public repositories "
        f"for {USERNAME}."
    )


if __name__ == "__main__":
    main()
