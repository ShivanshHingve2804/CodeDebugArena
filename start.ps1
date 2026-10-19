$ErrorActionPreference = 'Stop'

$projectDir = $PSScriptRoot
$envFile = Join-Path $projectDir '.env'
$composeFile = Join-Path $projectDir 'docker-compose.yml'
$url = 'http://127.0.0.1:8000'

function New-AccessToken {
    $bytes = New-Object byte[] 48
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($bytes)
    }
    finally {
        $generator.Dispose()
    }

    return [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
}

if (-not (Test-Path -LiteralPath $composeFile)) {
    throw "docker-compose.yml was not found in $projectDir"
}

if (-not (Test-Path -LiteralPath $envFile)) {
    $token = New-AccessToken
    @(
        "CDA_ACCESS_TOKEN=$token"
        'CDA_ALLOWED_HOSTS=localhost,127.0.0.1'
        'BIND_ADDRESS=127.0.0.1'
        'PORT=8000'
    ) | Set-Content -LiteralPath $envFile -Encoding ascii
    Write-Host 'Created a private .env file with a random dashboard access token.'
}

$tokenLine = Get-Content -LiteralPath $envFile | Where-Object { $_ -match '^CDA_ACCESS_TOKEN=(.+)$' } | Select-Object -First 1
if (-not $tokenLine) {
    throw "CDA_ACCESS_TOKEN is missing or blank in $envFile. Add a non-empty value and run this script again."
}
$token = $tokenLine -replace '^CDA_ACCESS_TOKEN=', ''

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    $dockerInfoOutput = & docker info 2>&1
    $dockerInfoExitCode = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
}
if ($dockerInfoExitCode -ne 0) {
    throw 'Docker is not available. Start Docker Desktop, wait until it says it is running, then run .\start.ps1 again.'
}

Write-Host 'Building and starting CodeDebugArena...'
docker compose --env-file $envFile -f $composeFile up --build -d
if ($LASTEXITCODE -ne 0) {
    throw 'Docker Compose could not start the app. Run .\logs.ps1 to see the container logs.'
}

Write-Host 'Waiting for the dashboard health check...'
$healthy = $false
for ($attempt = 0; $attempt -lt 60; $attempt++) {
    try {
        $response = Invoke-WebRequest -Uri "$url/health" -UseBasicParsing -TimeoutSec 2
        if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300) {
            $healthy = $true
            break
        }
    }
    catch {
        Start-Sleep -Seconds 2
    }
}

if (-not $healthy) {
    Write-Warning 'The dashboard did not become healthy in two minutes. Container logs follow:'
    docker compose --env-file $envFile -f $composeFile logs --tail 80
    throw 'Startup did not finish successfully. Fix the reported issue, then run .\start.ps1 again.'
}

Write-Host ''
Write-Host "Dashboard: $url"
Write-Host 'Dashboard access token (enter this on the dashboard):'
Write-Host $token
Write-Host ''
Write-Host 'Stop the app with .\stop.ps1. View status with .\status.ps1.'
Start-Process $url

