
import os
import sys
import requests

from html import escape
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ==========================================
# CONFIGURATION
# ==========================================

USERNAME = "nava-07"
PROFILE_REPO = "nava-07"

README_PATH = "README.md"

START_MARKER = "<!-- AUTO-PROJECTS:START -->"
END_MARKER = "<!-- AUTO-PROJECTS:END -->"

API_URL = "https://api.github.com"

TOKEN = os.getenv("GITHUB_TOKEN")

# ==========================================
# SESSION AND RETRY CONFIGURATION
# ==========================================

session = requests.Session()

retry_strategy = Retry(
    total=4,
    connect=4,
    read=4,
    backoff_factor=2,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"]
)

adapter = HTTPAdapter(max_retries=retry_strategy)

session.mount("https://", adapter)

HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28"
}

if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"

session.headers.update(HEADERS)


# ==========================================
# FETCH PUBLIC REPOSITORIES
# ==========================================

def get_public_repositories():

    repositories = []
    page = 1

    print("\nFetching GitHub repositories...\n")

    while True:

        print(f"Fetching page {page}...")

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

        if response.status_code == 403:
            raise RuntimeError(
                "GitHub API rate limit or access restriction. "
                "Check GITHUB_TOKEN and API rate-limit headers."
            )

        response.raise_for_status()

        batch = response.json()

        if not batch:
            break

        repositories.extend(batch)

        if len(batch) < 100:
            break

        page += 1

    # Filter unwanted repositories

    eligible_repositories = [

        repo for repo in repositories

        if repo["name"].lower() != PROFILE_REPO.lower()

        and not repo.get("fork", False)

        and not repo.get("archived", False)

        and not repo.get("disabled", False)

        and not repo.get("private", False)

    ]

    # Keep newest updated repositories first

    eligible_repositories.sort(
        key=lambda repo: repo.get("updated_at", ""),
        reverse=True
    )

    return eligible_repositories


# ==========================================
# GENERATE PROJECT CARD
# ==========================================

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


# ==========================================
# GENERATE ALL PROJECT CARDS
# ==========================================

def generate_project_cards(repositories):

    if not repositories:

        return """
<div align="center">

### No public projects found yet.

Check your public repositories and GitHub API access.

</div>
"""

    cards = []

    for repo in repositories:

        print(f"Generating card: {repo['name']}")

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

        row = f"""
<tr>
{first_card}
{second_card}
</tr>
"""

        rows.append(row)

    project_html = (
        '<table width="100%" border="0">\n'
        + "\n".join(rows)
        + "\n</table>"
    )

    return project_html


# ==========================================
# UPDATE README PROJECT SECTION
# ==========================================

def update_readme(project_cards):

    print("\nUpdating README.md...")

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

    # Validate markers

    if readme.count(START_MARKER) != 1:

        raise ValueError(
            "START marker must appear exactly once."
        )

    if readme.count(END_MARKER) != 1:

        raise ValueError(
            "END marker must appear exactly once."
        )

    start = (
        readme.index(START_MARKER)
        + len(START_MARKER)
    )

    end = readme.index(END_MARKER)

    if start > end:

        raise ValueError(
            "Project markers are in the wrong order."
        )

    # Replace only the content between markers

    updated_readme = (
        readme[:start]
        + "\n\n"
        + project_cards
        + "\n\n"
        + readme[end:]
    )

    with open(
        README_PATH,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(updated_readme)

    print("README project section updated successfully.")


# ==========================================
# MAIN FUNCTION
# ==========================================

def main():

    print("=" * 55)

    print(" NAVANEETH P - GITHUB PROJECT AUTOMATION ")

    print("=" * 55)

    repositories = get_public_repositories()

    print(
        f"\nTotal eligible public repositories: "
        f"{len(repositories)}"
    )

    if repositories:

        print("\nAvailable projects:\n")

        for repo in repositories:

            print(
                f"  - {repo['name']} "
                f"({repo.get('language') or 'Various'})"
            )

    project_cards = generate_project_cards(
        repositories
    )

    update_readme(project_cards)

    print("\n" + "=" * 55)

    print("SUCCESS: FEATURED PROJECTS UPDATED")

    print("=" * 55)


# ==========================================
# ERROR HANDLING
# ==========================================

if __name__ == "__main__":

    try:

        main()

    except requests.RequestException as error:

        print(
            f"\nGITHUB API ERROR: {error}",
            file=sys.stderr
        )

        sys.exit(1)

    except Exception as error:

        print(
            f"\nUPDATE ERROR: {error}",
            file=sys.stderr
        )

        sys.exit(1)
