$ErrorActionPreference = 'Stop'
$envFile = Join-Path $PSScriptRoot '.env'
$composeFile = Join-Path $PSScriptRoot 'docker-compose.yml'

if (-not (Test-Path -LiteralPath $envFile)) {
    throw 'No .env file found. Run .\start.ps1 once before stopping the app.'
}

docker compose --env-file $envFile -f $composeFile down
if ($LASTEXITCODE -ne 0) {
    throw 'Docker Compose could not stop the app. Check that Docker Desktop is running.'
}
