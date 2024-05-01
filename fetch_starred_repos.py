import requests
import os

# Set the working directory
working_directory = "C:\\Users\\mjpa\\Documents\\Obsidian\\20-29_Input\\23_Schriftliches\\23.03_Code"
os.chdir(working_directory)

# Define the GitHub API URL and headers
api_url = "https://api.github.com/users/lightningralf/starred"
# Retrieve the GitHub PAT set in environment variables
github_pat = os.environ.get("GITHUB_PAT")
if not github_pat:
    print("GITHUB_PAT environment variable not found.")
    exit(1)

headers = {"Authorization": f"token {github_pat}"}

# Fetch the starred repositories
starred_repos = []
page = 1
while True:
    paginated_url = f"{api_url}?page={page}&per_page=100"
    response = requests.get(paginated_url, headers=headers)
    if response.status_code != 200:
        print(f"Failed to fetch data: {response.status_code} - {response.text}")
        break

    json_data = response.json()
    if not json_data:
        print("No more data returned by the API.")
        break

    starred_repos.extend([repo["html_url"] for repo in json_data])
    print(f"Fetched page {page} with {len(json_data)} items.")
    page += 1

# Save the repository URLs to the file
with open("23.03.01_CrawlGitHubURLs.md", "w") as f:
    for repo_url in starred_repos:
        f.write(repo_url + "\n")

print("Starred repository URLs have been saved to the 23.03.01_CrawlGitHubURLs.md file.")
