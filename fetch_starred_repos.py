import requests
import os

# Set the working directory
working_directory = "C:\\Users\\mjpa\\Documents\\Obsidian\\70-79 Quellen\\78_GitHub"
os.chdir(working_directory)

# Replace these with your GitHub username and personal access token
github_username = "lightningRalf"
access_token = "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"

# Define the GitHub API URL and headers
api_url = f"https://api.github.com/users/{github_username}/starred"
headers = {"Authorization": f"token {access_token}"}

# Fetch the starred repositories
starred_repos = []
page = 1
while True:
    response = requests.get(api_url + f"?page={page}&per_page=100", headers=headers)
    if response.status_code != 200:
        break

    json_data = response.json()
    if not json_data:
        break

    starred_repos.extend([repo["html_url"] for repo in json_data])
    page += 1

# Save the repository URLs to the file
with open("78.01_CrawlGitHubURLs.md", "w") as f:
    for repo_url in starred_repos:
        f.write(repo_url + "\n")

print("Starred repository URLs have been saved to the 78.01_CrawlGitHubURLs.md file.")
