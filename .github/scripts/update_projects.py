
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
    """Fetch data from GitHub's REST API."""
    headers = {
        "Accept": accept,
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "nava-07-profile-project-updater",
    }

    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"

    request = urllib.request.Request(url, headers=headers)

    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def get_repositories():
    """Fetch all pages of public repositories."""
    repositories = []
    page = 1

    while True:
        url = (
            f"{API_BASE}/users/{USERNAME}/repos"
            f"?type=public&sort=updated&per_page=100&page={page}"
        )

        page_data = json.loads(github_get(url).decode("utf-8"))

        if not page_data:
            break

        repositories.extend(page_data)

        if len(page_data) < 100:
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


def clean_markdown(text):
    """Turn Markdown content into readable plain text."""
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"`{1,3}([^`]+)`{1,3}", r"\1", text)
    text = re.sub(r"[*_~]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def get_readme_description(repo):
    """Use the first useful README paragraph, or repository description."""
    fallback = repo.get("description") or "No description provided."
    url = f"{API_BASE}/repos/{USERNAME}/{repo['name']}/readme"

    try:
        raw_content = github_get(url, "application/vnd.github.raw+json")
        content = raw_content.decode("utf-8", errors="replace")

    except urllib.error.HTTPError as error:
        if error.code in (404, 409):
            return fallback
        raise

    except (urllib.error.URLError, TimeoutError):
        return fallback

    # Find the first meaningful paragraph, skipping headings and badges.
    paragraphs = re.split(r"\n\s*\n", content)

    for paragraph in paragraphs:
        lines = []

        for line in paragraph.splitlines():
            line = line.strip()

            if not line:
                continue

            if line.startswith("#") or line.startswith("!["):
                continue

            if line.startswith("<") and line.endswith(">"):
                continue

            if line.startswith("[!["):
                continue

            lines.append(line)

        description = clean_markdown(" ".join(lines))

        if len(description) >= 25:
            if len(description) > 240:
                description = description[:237].rsplit(" ", 1)[0] + "..."
            return description

    return fallback


def build_project_table(repositories):
    """Build a Markdown table from the repositories."""
    if not repositories:
        return (
            "No eligible public repositories found yet. "
            "Publish a public project to display it here."
        )

    rows = [
        "| Project | Description | Language | Stars |",
        "|---|---|---|---:|",
    ]

    for repo in repositories:
        name = repo.get("name", "Unnamed")
        url = repo.get("html_url", "")
        language = repo.get("language") or "Not specified"
        stars = repo.get("stargazers_count", 0)

        description = get_readme_description(repo)

        # Prevent table formatting from breaking.
        name = name.replace("|", "\\|").replace("[", "\\[")
        description = description.replace("|", "\\|").replace("\n", " ")
        language = language.replace("|", "\\|")

        rows.append(
            f"| [{name}]({url}) | {description} | {language} | {stars} |"
        )

    return "\n".join(rows)


def update_readme(project_table):
    """Replace only the auto-generated project section."""
    if not os.path.isfile(README_PATH):
        raise FileNotFoundError(f"Cannot find {README_PATH}")

    with open(README_PATH, "r", encoding="utf-8") as file:
        readme = file.read()

    if START_MARKER not in readme or END_MARKER not in readme:
        raise ValueError(
            "Missing project markers. Check README.md for "
            "AUTO-PROJECTS:START and AUTO-PROJECTS:END."
        )

    start = readme.index(START_MARKER) + len(START_MARKER)
    end = readme.index(END_MARKER)

    if end < start:
        raise ValueError("Project markers are in the wrong order.")

    new_section = "\n\n" + project_table + "\n"
    updated_readme = readme[:start] + new_section + readme[end:]

    if updated_readme == readme:
        print("Project section is already up to date.")
        return

    with open(README_PATH, "w", encoding="utf-8") as file:
        file.write(updated_readme)

    print("Successfully updated README.md.")


def main():
    print(f"Fetching public repositories for {USERNAME}...")

    repositories = get_repositories()
    print(f"Found {len(repositories)} eligible repositories.")

    project_table = build_project_table(repositories)
    update_readme(project_table)


if __name__ == "__main__":
    main()
