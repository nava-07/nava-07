
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

# =====================================================
# CONFIGURATION
# =====================================================

USERNAME = "nava-07"
PROFILE_REPO = "nava-07"
README_PATH = "README.md"

START_MARKER = "<!-- AUTO-PROJECTS:START -->"
END_MARKER = "<!-- AUTO-PROJECTS:END -->"

API_BASE = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN", "")


# =====================================================
# GITHUB API
# =====================================================

def github_get(url, accept="application/vnd.github+json"):
    """Fetch data from the GitHub API."""

    headers = {
        "Accept": accept,
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "nava-07-project-updater",
    }

    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"

    request = urllib.request.Request(url, headers=headers)

    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()

        except urllib.error.HTTPError as error:
            if error.code in (404, 409):
                raise

            if error.code == 403:
                print(
                    "GitHub API access denied or rate limit exceeded.",
                    file=sys.stderr,
                )
                raise

            if attempt == 2:
                raise

            time.sleep(attempt + 1)

        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise

            time.sleep(attempt + 1)

    raise RuntimeError(f"Failed to fetch {url}")


# =====================================================
# FETCH ALL PUBLIC REPOSITORIES
# =====================================================

def fetch_repositories():
    """Fetch eligible public repositories, including pagination."""

    repositories = []
    page = 1

    while True:
        url = (
            f"{API_BASE}/users/{USERNAME}/repos"
            f"?type=public&sort=updated&per_page=100&page={page}"
        )

        print(f"Fetching repositories: page {page}")

        data = json.loads(github_get(url).decode("utf-8"))

        if not data:
            break

        repositories.extend(data)

        if len(data) < 100:
            break

        page += 1

    # Exclude the profile repository, forks and archived repositories.
    eligible = [
        repo for repo in repositories
        if repo.get("name", "").lower() != PROFILE_REPO.lower()
        and not repo.get("fork", False)
        and not repo.get("archived", False)
        and not repo.get("disabled", False)
        and not repo.get("private", True)
    ]

    eligible.sort(
        key=lambda repo: repo.get("updated_at", ""),
        reverse=True,
    )

    print(f"Found {len(eligible)} eligible public repositories.")

    for repo in eligible:
        print(f"  - {repo['name']}")

    return eligible


# =====================================================
# README DESCRIPTION EXTRACTION
# =====================================================

def clean_markdown(text):
    """Convert Markdown content into readable plain text."""

    text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"`{1,3}([^`]+)`{1,3}", r"\1", text)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[*_~]", "", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def fetch_readme_description(repo):
    """Get the first meaningful paragraph from the repository README."""

    fallback = repo.get("description") or "No description provided."

    url = (
        f"{API_BASE}/repos/{USERNAME}/"
        f"{repo['name']}/readme"
    )

    try:
        raw = github_get(
            url,
            accept="application/vnd.github.raw+json",
        )

        content = raw.decode("utf-8", errors="replace")

    except urllib.error.HTTPError as error:
        if error.code in (404, 409):
            return fallback

        print(
            f"README error for {repo['name']}: HTTP {error.code}"
        )
        return fallback

    except (urllib.error.URLError, TimeoutError) as error:
        print(f"README request failed for {repo['name']}: {error}")
        return fallback

    # Remove comments and images before extracting text.
    content = re.sub(r"<!--.*?-->", " ", content, flags=re.DOTALL)
    content = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", content)

    paragraphs = re.split(r"\n\s*\n", content)

    for paragraph in paragraphs:
        lines = []

        for line in paragraph.splitlines():
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            # Ignore common badge-only lines.
            if (
                "shields.io/" in line
                or "badgen.net/" in line
                or line.startswith("[![")
            ):
                continue

            if line.startswith("<") and line.endswith(">"):
                continue

            lines.append(line)

        description = clean_markdown(" ".join(lines))

        if len(description) >= 20:
            if len(description) > 220:
                description = (
                    description[:217].rsplit(" ", 1)[0] + "..."
                )

            return description

    return fallback


# =====================================================
# GENERATE PROJECT CARDS
# =====================================================

def generate_project_cards(repositories):
    """Create two-column cards from real repository information."""

    if not repositories:
        return (
            "<p>No eligible public repositories found. "
            "Check that your projects are public.</p>"
        )

    output = ["<table>"]

    for index in range(0, len(repositories), 2):
        output.append("<tr>")

        current_row = repositories[index:index + 2]

        for repo in current_row:
            name = html.escape(repo.get("name", "Project"))
            url = html.escape(repo.get("html_url", ""), quote=True)

            description = html.escape(
                fetch_readme_description(repo)
            )

            language = html.escape(repo.get("language") or "Other")
            stars = repo.get("stargazers_count", 0)

            output.append(
                f"""
<td width="50%" valign="top">
  <h3>🚀 <a href="{url}">{name}</a></h3>
  <p>{description}</p>
  <p><sub>💻 {language} &nbsp; ⭐ {stars}</sub></p>
</td>
"""
            )

        if len(current_row) == 1:
            output.append('<td width="50%" valign="top"></td>')

        output.append("</tr>")

    output.append("</table>")

    return "\n".join(output)


# =====================================================
# UPDATE README IN PLACE
# =====================================================

def update_readme(project_cards):
    """Replace only the content between the project markers."""

    if not os.path.isfile(README_PATH):
        raise FileNotFoundError(
            "README.md not found. Run this script from the "
            "root of your nava-07 profile repository."
        )

    with open(README_PATH, "r", encoding="utf-8") as file:
        readme = file.read()

    if readme.count(START_MARKER) != 1:
        raise ValueError(
            "README.md must contain exactly one "
            "AUTO-PROJECTS:START marker."
        )

    if readme.count(END_MARKER) != 1:
        raise ValueError(
            "README.md must contain exactly one "
            "AUTO-PROJECTS:END marker."
        )

    start = readme.index(START_MARKER) + len(START_MARKER)
    end = readme.index(END_MARKER)

    if end < start:
        raise ValueError("Project markers are in the wrong order.")

    # Replace the section in its existing position.
    updated_readme = (
        readme[:start]
        + "\n\n"
        + project_cards
        + "\n\n"
        + readme[end:]
    )

    if updated_readme == readme:
        print("Project section is already up to date.")
        return

    with open(README_PATH, "w", encoding="utf-8") as file:
        file.write(updated_readme)

    print("README.md updated successfully.")
    print("Project cards were inserted between the markers.")


# =====================================================
# MAIN
# =====================================================

def main():
    print("=" * 55)
    print("DYNAMIC GITHUB PROJECT UPDATER")
    print(f"GitHub account: {USERNAME}")
    print("=" * 55)

    try:
        repositories = fetch_repositories()

        project_cards = generate_project_cards(repositories)

        update_readme(project_cards)

        print("SUCCESS: Project list generated.")

    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
