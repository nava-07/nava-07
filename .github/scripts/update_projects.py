
import os
import sys
import time
import requests

from html import escape
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ==================================================
# CONFIGURATION
# ==================================================

USERNAME = "nava-07"
PROFILE_REPO = "nava-07"

README_PATH = "README.md"

START_MARKER = "<!-- AUTO-PROJECTS:START -->"
END_MARKER = "<!-- AUTO-PROJECTS:END -->"

FEATURED_HEADING = "## 🚀 Featured Projects"

API_URL = "https://api.github.com"

TOKEN = os.getenv("GITHUB_TOKEN")

# ==================================================
# HTTP SESSION AND RETRY CONFIGURATION
# ==================================================

session = requests.Session()

retry_strategy = Retry(
    total=4,
    connect=4,
    read=4,
    backoff_factor=2,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"],
    respect_retry_after_header=True
)

adapter = HTTPAdapter(max_retries=retry_strategy)

session.mount("https://", adapter)

HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "Navaneeth-GitHub-Project-Updater"
}

if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"

session.headers.update(HEADERS)


# ==================================================
# FETCH PUBLIC REPOSITORIES
# ==================================================

def get_public_repositories():

    repositories = []
    page = 1

    print("\nConnecting to GitHub API...")

    while True:

        print(f"Fetching repository page {page}...")

        response = session.get(
            f"{API_URL}/users/{USERNAME}/repos",
            params={
                "type": "public",
                "sort": "updated",
                "direction": "desc",
                "per_page": 100,
                "page": page
            },
            timeout=30
        )

        if response.status_code in (403, 429):

            remaining = response.headers.get(
                "X-RateLimit-Remaining",
                "Unknown"
            )

            reset = response.headers.get(
                "X-RateLimit-Reset",
                "Unknown"
            )

            print("\nGitHub API access restricted.")
            print("Rate limit remaining:", remaining)
            print("Rate limit reset timestamp:", reset)
            print("Response:", response.text[:1000])

            raise RuntimeError(
                "GitHub API rate limit or access restriction."
            )

        if response.status_code == 401:

            raise RuntimeError(
                "GitHub authentication failed. "
                "Check your GITHUB_TOKEN."
            )

        response.raise_for_status()

        batch = response.json()

        if not batch:
            break

        repositories.extend(batch)

        print(f"Received {len(batch)} repositories.")

        if len(batch) < 100:
            break

        page += 1

    # Filter repositories

    eligible = []

    for repo in repositories:

        if repo["name"].lower() == PROFILE_REPO.lower():
            continue

        if repo.get("fork", False):
            continue

        if repo.get("archived", False):
            continue

        if repo.get("disabled", False):
            continue

        if repo.get("private", False):
            continue

        eligible.append(repo)

    # Sort by latest update

    eligible.sort(
        key=lambda repo: repo.get("updated_at", ""),
        reverse=True
    )

    return eligible


# ==================================================
# GENERATE INDIVIDUAL PROJECT CARDS
# ==================================================

def generate_project_card(repo):

    name = escape(repo["name"])

    url = escape(
        repo["html_url"],
        quote=True
    )

    description = escape(
        repo.get("description")
        or "Explore this project and its implementation."
    )

    language = escape(
        repo.get("language") or "Various"
    )

    stars = repo.get("stargazers_count", 0)

    forks = repo.get("forks_count", 0)

    card = f"""
<td width="50%" valign="top">

<h3>
<a href="{url}">🚀 {name}</a>
</h3>

<p>{description}</p>

<p>
<strong>Language:</strong> {language}
</p>

<p>
⭐ <strong>{stars} Stars</strong>
&nbsp; · &nbsp;
🍴 <strong>{forks} Forks</strong>
</p>

<p>
<a href="{url}">View Project →</a>
</p>

</td>
"""

    return card


# ==================================================
# GENERATE ALL PROJECT CARDS
# ==================================================

def generate_project_cards(repositories):

    if not repositories:

        return """
<div align="center">

### No eligible public projects found yet.

Check your public repositories and GitHub API access.

</div>
"""

    cards = []

    print("\nGenerating project cards...\n")

    for repo in repositories:

        print("Creating:", repo["name"])

        cards.append(
            generate_project_card(repo)
        )

    rows = []

    for index in range(0, len(cards), 2):

        first_card = cards[index]

        if index + 1 < len(cards):

            second_card = cards[index + 1]

        else:

            second_card = """
<td width="50%"></td>
"""

        rows.append(
            f"""
<tr>
{first_card}
{second_card}
</tr>
"""
        )

    project_html = (
        '<table width="100%" border="0">\n'
        + "\n".join(rows)
        + "\n</table>"
    )

    return project_html


# ==================================================
# VALIDATE README STRUCTURE
# ==================================================

def validate_readme(readme):

    if readme.count(START_MARKER) != 1:

        raise ValueError(
            "AUTO-PROJECTS START marker must appear exactly once."
        )

    if readme.count(END_MARKER) != 1:

        raise ValueError(
            "AUTO-PROJECTS END marker must appear exactly once."
        )

    start_position = readme.index(START_MARKER)

    end_position = readme.index(END_MARKER)

    if start_position >= end_position:

        raise ValueError(
            "Project markers are in the wrong order."
        )

    if FEATURED_HEADING not in readme[:start_position]:

        raise ValueError(
            "Featured Projects heading must appear before the markers."
        )

    # Ensure the project section is at the bottom.

    content_after_markers = readme[
        end_position + len(END_MARKER):
    ]

    if content_after_markers.strip():

        raise ValueError(
            "Featured Projects markers must be at the bottom "
            "of README.md. Move them after all other sections."
        )

    return start_position, end_position


# ==================================================
# UPDATE README
# ==================================================

def update_readme(project_cards):

    print("\nReading README.md...")

    if not os.path.exists(README_PATH):

        raise FileNotFoundError(
            "README.md was not found."
        )

    with open(
        README_PATH,
        "r",
        encoding="utf-8"
    ) as file:

        readme = file.read()

    start_position, end_position = validate_readme(
        readme
    )

    start = (
        start_position
        + len(START_MARKER)
    )

    updated_readme = (
        readme[:start]
        + "\n\n"
        + project_cards
        + "\n\n"
        + readme[end_position:]
    )

    if updated_readme == readme:

        print("README already contains the latest project cards.")

        return

    with open(
        README_PATH,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(updated_readme)

    print("README.md successfully updated.")


# ==================================================
# MAIN FUNCTION
# ==================================================

def main():

    print("=" * 55)
    print(" NAVANEETH P - GITHUB PROJECT AUTOMATION")
    print("=" * 55)

    repositories = get_public_repositories()

    print("\nTotal public repositories fetched:", len(repositories))

    print("Eligible projects:", len(repositories))

    if repositories:

        print("\nEligible projects:")

        for index, repo in enumerate(repositories, 1):

            print(
                f"{index}. {repo['name']} "
                f"| {repo.get('language') or 'Various'} "
                f"| ⭐ {repo.get('stargazers_count', 0)}"
            )

    project_cards = generate_project_cards(
        repositories
    )

    update_readme(project_cards)

    print("\n" + "=" * 55)
    print("SUCCESS: FEATURED PROJECTS UPDATED")
    print("=" * 55)


# ==================================================
# ERROR HANDLING
# ==================================================

if __name__ == "__main__":

    try:

        main()

    except requests.RequestException as error:

        print(
            "\nGITHUB NETWORK/API ERROR:",
            str(error),
            file=sys.stderr
        )

        sys.exit(1)

    except Exception as error:

        print(
            "\nPROJECT UPDATE FAILED:",
            str(error),
            file=sys.stderr
        )

        sys.exit(1)
