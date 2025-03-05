import os

# Change the current working directory to the 'CrawlGitHub' folder
os.chdir("C:\\Users\\mjpa\\ProgrammierProjekte\\CrawlGitHub\\")

# Run the first script to fetch starred repository URLs
os.system("python fetch_starred_repos.py")

# Run the second script to generate repository information markdown files
os.system("python generate_repo_info.py")
