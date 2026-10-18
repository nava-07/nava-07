
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

# ==================================================
# CONFIGURATION
# ==================================================

USERNAME = "nava-07"
PROFILE_REPO = "nava-07"
README_PATH = "README.md"

START_MARKER = "<!-- AUTO-PROJECTS:START -->"
END_MARKER = "<!-- AUTO-PROJECTS:END -->"

API_BASE = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN", "")


# ==================================================
# GITHUB API REQUEST
# ==================================================

def github_get(url, accept="application/vnd.github+json"):
    """Fetch data from GitHub with basic retry handling."""

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
                print("GitHub API access or rate limit error.")
                raise

            if attempt == 2:
                raise

            time.sleep(attempt + 1)

        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise

            time.sleep(attempt + 1)

    raise RuntimeError(f"Unable to fetch: {url}")


# ==================================================
# FETCH REPOSITORIES
# ==================================================

def fetch_repositories():
    """Fetch all eligible public repositories for the user."""

    repositories = []
    page = 1

    while True:
        url = (
            f"{API_BASE}/users/{USERNAME}/repos"
            f"?type=public&sort=updated&per_page=100&page={page}"
        )

        print(f"Fetching repository page {page}...")

        data = json.loads(github_get(url).decode("utf-8"))

        if not data:
            break

        repositories.extend(data)

        if len(data) < 100:
            break

        page += 1

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

    print(f"Eligible public repositories: {len(eligible)}")

    return eligible


# ==================================================
# GET DESCRIPTION FROM EACH REPOSITORY README
# ==================================================

def clean_markdown(text):
    """Remove common Markdown formatting from a description."""

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
    """Extract the first useful README paragraph."""

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
            f"Warning: README unavailable for "
            f"{repo['name']}: HTTP {error.code}"
        )
        return fallback

    except (urllib.error.URLError, TimeoutError) as error:
        print(f"Warning: README request failed for {repo['name']}: {error}")
        return fallback

    content = re.sub(r"<!--.*?-->", " ", content, flags=re.DOTALL)
    content = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", content)

    for paragraph in re.split(r"\n\s*\n", content):
        lines = []

        for line in paragraph.splitlines():
            line = line.strip()

            if not line or line.startswith("#"):
                continue

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


# ==================================================
# GENERATE PROJECT CARDS
# ==================================================

def generate_project_cards(repositories):
    """Create two-column project cards from real repositories."""

    if not repositories:
        return (
            "<p>No eligible public repositories found. "
            "Check your public repositories on GitHub.</p>"
        )

    cards = ["<table>"]

    for index in range(0, len(repositories), 2):
        cards.append("<tr>")

        current_row = repositories[index:index + 2]

        for repo in current_row:
            name = html.escape(repo.get("name", "Project"))
            url = html.escape(repo.get("html_url", ""), quote=True)

            description = fetch_readme_description(repo)
            description = html.escape(description)

            language = html.escape(repo.get("language") or "Other")
            stars = repo.get("stargazers_count", 0)
            forks = repo.get("forks_count", 0)

            cards.append(
                f"""
<td width="50%" valign="top">
  <h3>🚀 <a href="{url}">{name}</a></h3>
  <p>{description}</p>
  <p>
    <sub>💻 {language} &nbsp; ⭐ {stars} &nbsp; 🍴 {forks}</sub>
  </p>
</td>
"""
            )

        if len(current_row) == 1:
            cards.append('<td width="50%" valign="top"></td>')

        cards.append("</tr>")

    cards.append("</table>")

    return "\n".join(cards)


# ==================================================
# UPDATE ONLY THE MARKED README SECTION
# ==================================================

def update_readme(project_cards):
    """Replace the section between markers without moving other content."""

    if not os.path.isfile(README_PATH):
        raise FileNotFoundError(
            f"{README_PATH} not found. Run from the repository root."
        )

    with open(README_PATH, "r", encoding="utf-8") as file:
        readme = file.read()

    # Require exactly one marker of each kind.
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

    if end < start:
        raise ValueError(
            "The project markers are in the wrong order."
        )

    # Replace only the content between markers.
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

    print("Project cards inserted directly into the marked section.")


# ==================================================
# MAIN
# ==================================================

def main():
    print("=" * 50)
    print("GitHub Dynamic Project Updater")
    print(f"Account: {USERNAME}")
    print("=" * 50)

    try:
        repositories = fetch_repositories()
        project_cards = generate_project_cards(repositories)
        update_readme(project_cards)

        print("SUCCESS: README project section updated.")

    except Exception as error:
        print(f"FAILED: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
