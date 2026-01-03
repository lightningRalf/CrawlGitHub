param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Args
)

uv run crawl-github @Args
