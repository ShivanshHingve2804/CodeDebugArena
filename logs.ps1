$ErrorActionPreference = 'Stop'
$envFile = Join-Path $PSScriptRoot '.env'
$composeFile = Join-Path $PSScriptRoot 'docker-compose.yml'

if (-not (Test-Path -LiteralPath $envFile)) {
    throw 'No .env file found. Run .\start.ps1 to create it and start the app.'
}

docker compose --env-file $envFile -f $composeFile logs --tail 80 --follow
if ($LASTEXITCODE -ne 0) {
    throw 'Could not read the app logs. Check that Docker Desktop is running.'
}
