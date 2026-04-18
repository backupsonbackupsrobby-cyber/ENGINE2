param(
    [int]$MaxLogDays = 7,
    [int]$MaxLogTotalMB = 500
)

$root = "C:\ENGINE2"
$logsDir = Join-Path $root "LOGS"
$stateDir = Join-Path $root "STATE"
$summaryDir = Join-Path $root "SUMMARY"

# --- STORM: present moment snapshot ---
$state = [pscustomobject]@{
    timestamp_utc = (Get-Date).ToUniversalTime().ToString("o")
    host          = $env:COMPUTERNAME
    user          = $env:USERNAME
    free_gb_c     = [math]::Round((Get-PSDrive C).Free/1GB,2)
}
$state | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $stateDir "state.json")

# --- COOL: rotate logs ---
$today = Join-Path $logsDir (Get-Date -Format "yyyy-MM-dd")
New-Item -ItemType Directory -Path $today -Force | Out-Null
"[{0}] heartbeat free_gb_c={1}" -f (Get-Date -Format "o"), $state.free_gb_c |
    Add-Content (Join-Path $today "events.log")

# delete logs older than MaxLogDays
Get-ChildItem $logsDir -Directory |
    Where-Object {
        $_.Name -match '^\d{4}-\d{2}-\d{2}$' -and
        ([datetime]$_.Name) -lt (Get-Date).Date.AddDays(-$MaxLogDays)
    } |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# cap total log size
$allLogs = Get-ChildItem $logsDir -Recurse -File -ErrorAction SilentlyContinue
$totalBytes = ($allLogs | Measure-Object Length -Sum).Sum
$maxBytes = $MaxLogTotalMB * 1MB

if ($totalBytes -gt $maxBytes) {
    $toDelete = $allLogs | Sort-Object LastWriteTime
    foreach ($f in $toDelete) {
        $totalBytes -= $f.Length
        Remove-Item $f.FullName -Force -ErrorAction SilentlyContinue
        if ($totalBytes -le $maxBytes) { break }
    }
}

# --- RETURN: daily summary ---
$summary = [pscustomobject]@{
    date        = (Get-Date -Format "yyyy-MM-dd")
    last_utc    = $state.timestamp_utc
    free_gb_c   = $state.free_gb_c
    log_dirs    = (Get-ChildItem $logsDir -Directory | Select-Object -ExpandProperty Name)
}
$summary | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $summaryDir ((Get-Date -Format "yyyy-MM-dd") + ".json"))
