param(
    [Parameter(Mandatory = $true)]
    [int]$Batch,

    [int]$BatchSize = 150,

    [switch]$DryRun,

    [switch]$DedupeStarredFile,

    [switch]$CreateReadmePlaceholders
)

if ($Batch -lt 1) {
    throw "Batch must be >= 1"
}

$startNumber = 1 + (($Batch - 1) * $BatchSize)
$batchLabel = "{0:D2}" -f $Batch
$reportDir = "docs/migration"

New-Item -ItemType Directory -Path $reportDir -Force | Out-Null

$reportSuffix = if ($DryRun) { "-dry" } else { "" }
$reportPath = "$reportDir/batch-$batchLabel$reportSuffix.json"

$args = @(
    "run",
    "python",
    "tools/migrate_repo_notes.py",
    "--start-number", "$startNumber",
    "--limit", "$BatchSize",
    "--report", "$reportPath"
)

if ($DryRun) {
    $args += "--dry-run"
}

if ($DedupeStarredFile) {
    $args += "--dedupe-starred-file"
}

if ($CreateReadmePlaceholders) {
    $args += "--create-readme-placeholders"
}

Write-Host "Running migration batch $Batch (start=$startNumber, limit=$BatchSize, dryRun=$DryRun, placeholders=$CreateReadmePlaceholders)"
uv @args
