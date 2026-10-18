
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

USERNAME = "nava-07"
PROFILE_REPO = "nava-07"
README_PATH = "README.md"

START_MARKER = "<!-- AUTO-PROJECTS:START -->"
END_MARKER = "<!-- AUTO-PROJECTS:END -->"

API_BASE = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN", "")


# --------------------------------------------------
# GITHUB API
# --------------------------------------------------

def github_get(url, accept="application/vnd.github+json"):
    """Fetch data from the GitHub API with error handling."""

    headers = {
        "Accept": accept,
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "nava-07-profile-project-updater",
    }

    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"

    request = urllib.request.Request(url, headers=headers)

    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()

        except urllib.error.HTTPError as error:
            if error.code == 403:
                remaining = error.headers.get("X-RateLimit-Remaining")
                if remaining == "0":
                    reset = error.headers.get("X-RateLimit-Reset")
                    print(
                        "GitHub API rate limit reached. "
                        f"Reset timestamp: {reset}"
                    )
            raise

        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(attempt + 1)

    raise RuntimeError(f"Could not fetch {url}")


# --------------------------------------------------
# FETCH PUBLIC REPOSITORIES
# --------------------------------------------------

def fetch_repositories():
    """Fetch all eligible public repositories, including pagination."""

    repositories = []
    page = 1

    while True:
        url = (
            f"{API_BASE}/users/{USERNAME}/repos"
            f"?type=public&sort=updated&per_page=100&page={page}"
        )

        print(f"Fetching repositories page {page}...")

        data = json.loads(github_get(url).decode("utf-8"))

        if not data:
            break

        repositories.extend(data)

        if len(data) < 100:
            break

        page += 1

    # Exclude the profile repository, forks, archived and disabled repos.
    eligible = [
        repo for repo in repositories
        if repo.get("name", "").lower() != PROFILE_REPO.lower()
        and not repo.get("fork", False)
        and not repo.get("archived", False)
        and not repo.get("disabled", False)
        and not repo.get("private", True)
    ]

    # Display recently updated projects first.
    eligible.sort(
        key=lambda repo: repo.get("updated_at", ""),
        reverse=True,
    )

    print(f"Found {len(eligible)} eligible public repositories.")

    return eligible


# --------------------------------------------------
# EXTRACT README DESCRIPTION
# --------------------------------------------------

def clean_markdown(text):
    """Convert README Markdown into readable plain text."""

    text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"`{1,3}([^`]+)`{1,3}", " ", text)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[*_~]", "", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def fetch_readme_description(repo):
    """Use the first meaningful README paragraph or repo description."""

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
            f"Warning: README fetch failed for "
            f"{repo['name']}: HTTP {error.code}"
        )
        return fallback

    except (urllib.error.URLError, TimeoutError) as error:
        print(f"Warning: Could not fetch README for {repo['name']}: {error}")
        return fallback

    # Remove HTML comments and image Markdown before parsing paragraphs.
    content = re.sub(r"<!--.*?-->", " ", content, flags=re.DOTALL)
    content = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", content)

    paragraphs = re.split(r"\n\s*\n", content)

    for paragraph in paragraphs:
        lines = []

        for line in paragraph.splitlines():
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            # Skip badge-only lines.
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


# --------------------------------------------------
# GENERATE PROJECT CARDS
# --------------------------------------------------

def generate_project_cards(repositories):
    """Generate a two-column HTML table of actual repositories."""

    if not repositories:
        return (
            "_No eligible public repositories found. "
            "Check that your repositories are public._"
        )

    output = [
        '<table>',
    ]

    for index in range(0, len(repositories), 2):
        output.append("<tr>")

        row_repositories = repositories[index:index + 2]

        for repo in row_repositories:
            name = html.escape(repo.get("name", "Project"))
            url = html.escape(repo.get("html_url", ""), quote=True)

            description = fetch_readme_description(repo)
            description = html.escape(description)

            language = html.escape(repo.get("language") or "Other")
            stars = repo.get("stargazers_count", 0)
            forks = repo.get("forks_count", 0)

            output.append(
                f"""
<td width="50%" valign="top">
  <h3>
    🚀 <a href="{url}">{name}</a>
  </h3>
  <p>{description}</p>
  <p>
    <sub>
      💻 {language}
      &nbsp; ⭐ {stars}
      &nbsp; 🍴 {forks}
    </sub>
  </p>
</td>
"""
            )

        if len(row_repositories) == 1:
            output.append('<td width="50%" valign="top"></td>')

        output.append("</tr>")

    output.append("</table>")

    return "\n".join(output)


# --------------------------------------------------
# UPDATE README
# --------------------------------------------------

def update_readme(project_cards):
    """Replace content between the README project markers."""

    if not os.path.isfile(README_PATH):
        raise FileNotFoundError(
            f"{README_PATH} not found. Run this script from the repository root."
        )

    with open(README_PATH, "r", encoding="utf-8") as file:
        readme = file.read()

    if START_MARKER not in readme or END_MARKER not in readme:
        raise ValueError(
            "Project markers are missing from README.md.\n"
            f"Add these exact markers:\n{START_MARKER}\n{END_MARKER}"
        )

    start = readme.index(START_MARKER) + len(START_MARKER)
    end = readme.index(END_MARKER)

    if end < start:
        raise ValueError(
            "The project markers are in the wrong order."
        )

    new_section = "\n\n" + project_cards + "\n\n"

    updated_readme = (
        readme[:start]
        + new_section
        + readme[end:]
    )

    if updated_readme == readme:
        print("README project section is already up to date.")
        return

    with open(README_PATH, "w", encoding="utf-8") as file:
        file.write(updated_readme)

    print("Successfully updated README.md with project cards.")


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():
    print("=" * 50)
    print(f"GitHub Project Updater: {USERNAME}")
    print("=" * 50)

    try:
        repositories = fetch_repositories()
        project_cards = generate_project_cards(repositories)
        update_readme(project_cards)

        print("Project update completed successfully.")

    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
