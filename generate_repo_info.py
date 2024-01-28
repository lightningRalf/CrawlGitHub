import requests
from datetime import datetime
import os
import re
import backoff

@backoff.on_exception(backoff.expo, requests.exceptions.RequestException, max_tries=5)
def get_readme_url(github_url, default_branch):
    readme_url = github_url.replace("github.com", "raw.githubusercontent.com") + f"/{default_branch}/README.md"
    return readme_url

# Set the working directory
working_directory = "C:\\Users\\mjpa\\Documents\\Obsidian\\20-29_Input\\23_Schriftliches\\23.03_Code"
os.chdir(working_directory)

# Read the URLs from the file
with open("23.03.01_CrawlGitHubURLs.md", "r") as f:
    urls = [url.strip() for url in f.readlines() if url.strip()]

# Process each URL
for i, github_url in enumerate(urls, start=2):

    # Get the API URL for the GitHub repository
    api_url = github_url.replace("https://github.com", "https://api.github.com/repos")
    # set in CMD: `setx GITHUB_PAT "APITOKENHERE"`
    github_pat = os.environ["GITHUB_PAT"]
    headers = {"Authorization": f"token {github_pat}"}
    response = requests.get(api_url, headers=headers)
    
    
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
        contributors_response = requests.get(contributors_url, headers=headers)
        if contributors_response.status_code == 200:
            contributors_data = contributors_response.json()
            contributors = len(contributors_data)
        else:
            contributors = "Error"

        # Get the latest release
        releases_response = requests.get(releases_url, headers=headers)
        if releases_response.status_code == 200:
            releases_data = releases_response.json()
            latest_release = releases_data[0]["tag_name"] if releases_data else "No release found"
        else:
            latest_release = "Error"

        # Find the existing markdown file with the repo name
        existing_files = [file for file in os.listdir() if re.search(rf"23.03\.\d{{2,3}}_{repo_name}\.md", file)]
        
        if existing_files:
            markdown_file = existing_files[0]
        else:
            # Get the highest existing number and add 1
            existing_numbers = [int(re.search(r"23.03\.(\d{2,3})_", file).group(1)) for file in os.listdir() if re.search(r"23.03\.\d{2,3}_", file)]
            next_number = max(existing_numbers) + 1
            markdown_file = f"23.03.{next_number:03}_{repo_name}.md"

        # Open the markdown file in append mode
        with open(markdown_file, "a", encoding="utf-8") as f:
            # Check if the file is empty
            if os.stat(markdown_file).st_size == 0:
                # Write the repo description and URL
                f.write(f"## [{repo_description}]({github_url})\n")
                
                # Add the iframe with the README.md
                readme_url = get_readme_url(github_url, default_branch)
                f.write(f"\n## README\n\n")
                f.write(f'<iframe width="100%" height="800" src="{github_url}" ></iframe>\n')
                
                # Write the table header
                f.write(f"\n## Overview\n\n")
                f.write("| Date       | Watchers | Forks | Stars | Contributors | Latest Release |\n")
                f.write("|------------|----------|-------|-------|--------------|----------------|\n")

            # Write the extracted data to the table
            f.write(f"| {datetime.now().strftime('%Y-%m-%d')} | {watching} | {forks}  | {stars} | {contributors} | {latest_release} |\n")

        print(f"Data has been added to the markdown table for {repo_name}.")
    else:
        print(f"Error while fetching the GitHub page: {github_url} (status code: {response.status_code})")
        print(f"Error message: {response.json()}") # Print the error message
