import requests
from bs4 import BeautifulSoup
from datetime import datetime
import os
import json
import re

# Set the working directory
working_directory = "C:\\Users\\mjpa\\Documents\\Obsidian\\70-79 Quellen\\78_GitHub"
os.chdir(working_directory)

# Read the URLs from the file
with open("78.01_CrawlGitHubURLs.md", "r") as f:
    urls = [url.strip() for url in f.readlines() if url.strip()]

# Process each URL
for i, github_url in enumerate(urls, start=2):
    # Send an HTTP request to the GitHub URL
    response = requests.get(github_url)

    # Check if the request was successful
    if response.status_code == 200:
        # Parse the HTML content of the page
        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract the required information
        stars = soup.select_one('.Link--muted[href$="stargazers"] strong').text.strip()
        watchers = soup.select_one('.Link--muted[href$="watchers"] strong').text.strip()
        forks = soup.select_one('.Link--muted[href$="forks"] strong').text.strip()


        # Get the contributors count
        api_url = f"https://api.github.com/repos/{github_url.split('/')[-2]}/{github_url.split('/')[-1]}/contributors"
        headers = {"Accept": "application/vnd.github+json"}
        contributors_response = requests.get(api_url, headers=headers)

        if contributors_response.status_code == 200:
            contributors_data = json.loads(contributors_response.text)
            contributors = len(contributors_data)
        else:
            contributors = "Error"


        # Get the repository name
        repo_name = github_url.split("/")[-1]

        # Find the existing markdown file with the repo name
        existing_files = [file for file in os.listdir() if re.search(rf"78\.\d{{2}}_{repo_name}\.md", file)]
        if existing_files:
            markdown_file = existing_files[0]
        else:
            markdown_file = f"78.{str(i).zfill(2)}_{repo_name}.md"
            
        # Open the markdown file in append mode
        with open(markdown_file, "a") as f:
            # Write the table header if the file doesn't exist
            if not existing_files:
                f.write("| Date       | Watchers | Forks | Stars | Contributors |\n")
                f.write("|------------|-------|----------|--------------|-------|\n")

            # Write the extracted data to the table
            f.write(f"| {datetime.now().strftime('%Y-%m-%d')} | {watchers} | {forks} | {stars} | {contributors} |\n")

        print(f"Data has been added to the markdown table for {repo_name}.")
    else:
        print("Error while fetching the GitHub page.")
