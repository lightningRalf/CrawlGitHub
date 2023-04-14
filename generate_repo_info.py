import requests
from datetime import datetime
import os
import re

def get_readme_url(github_url, default_branch):
    readme_url = github_url.replace("github.com", "raw.githubusercontent.com") + f"/{default_branch}/README.md"
    return readme_url

# Set the working directory
working_directory = "C:\\Users\\mjpa\\Documents\\Obsidian\\70-79 Quellen\\78_GitHub"
os.chdir(working_directory)

# Read the URLs from the file
with open("78.01_CrawlGitHubURLs.md", "r") as f:
    urls = [url.strip() for url in f.readlines() if url.strip()]

# Process each URL
for i, github_url in enumerate(urls, start=1):
    # Get the API URL for the GitHub repository
    api_url = github_url.replace("https://github.com", "https://api.github.com/repos")

    # Send an HTTP request to the GitHub API URL
    response = requests.get(api_url)

    if response.status_code == 200:
        repo_data = response.json()

        # Extract the required information
        repo_name = repo_data["name"]
        repo_description = repo_data["description"] or "No description found"
        stars = repo_data["stargazers_count"]
        watching = repo_data["subscribers_count"]
        forks = repo_data["forks_count"]
        default_branch = repo_data["default_branch"]
        contributors_url = repo_data["contributors_url"]
        releases_url = repo_data["releases_url"].replace("{/id}", "")

        # Get the contributors count
        contributors_response = requests.get(contributors_url)
        if contributors_response.status_code == 200:
            contributors_data = contributors_response.json()
            contributors = len(contributors_data)
        else:
            contributors = "Error"

        # Get the latest release
        releases_response = requests.get(releases_url)
        if releases_response.status_code == 200:
            releases_data = releases_response.json()
            latest_release = releases_data[0]["tag_name"] if releases_data else "No release found"
        else:
            latest_release = "Error"

        # Find the existing markdown file with the repo name
        existing_files = [file for file in os.listdir() if re.search(rf"78\.\d{{2}}_{repo_name}\.md", file)]
        if existing_files:
            markdown_file = existing_files[0]
        else:
            markdown_file = f"78.{str(i).zfill(2)}_{repo_name}.md"

        # Open the markdown file in append mode
        with open(markdown_file, "a", encoding="utf-8") as f:
            # Check if the file is empty
            if os.stat(markdown_file).st_size == 0:
                # Write the repo description and URL
                f.write(f"## [{repo_description}]({github_url})\n")
                
                # Add the iframe with the README.md
                readme_url = get_readme_url(github_url, default_branch)
                f.write(f"\n## README\n")
                f.write(f'<iframe width="100%" height="800" src="{readme_url}" ></iframe>\n')
                
                # Write the table header
                f.write(f"\n##Overview\n")
                f.write("| Date       | Watchers | Forks | Stars | Contributors | Latest Release |\n")
                f.write("|------------|----------|-------|-------|--------------|----------------|\n")

            # Write the extracted data to the table
            f.write(f"| {datetime.now().strftime('%Y-%m-%d')} | {stars} | {watching} | {contributors} | {forks} | {latest_release} |\n")

        print(f"Data has been added to the markdown table for {repo_name}.")
    else:
        print("Error while fetching the GitHub page.")
