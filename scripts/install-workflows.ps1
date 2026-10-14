# Copies the GitHub Actions workflows from jan-releases\templates into place.
#   jan-releases\.github\workflows\catalog.yml
#   <app>\.github\workflows\release-android.yml   (APP_ID / APP_NAME filled in)
#
# Run from anywhere:
#   powershell -ExecutionPolicy Bypass -File C:\Users\JLAURENCE\Documents\Programming\jan-releases\scripts\install-workflows.ps1
#
# To add a new app later, add one Install-AppWorkflow line at the bottom and run it again.
# Existing workflow files are overwritten.

param(
    [string]$Root = "C:\Users\JLAURENCE\Documents\Programming"
)

$ErrorActionPreference = "Stop"
$repo = Split-Path $PSScriptRoot -Parent          # ...\jan-releases
$templates = Join-Path $repo "templates"
$utf8NoBom = New-Object System.Text.UTF8Encoding $false

function Write-Workflow([string]$Path, [string]$Text) {
    New-Item -ItemType Directory -Force (Split-Path $Path -Parent) | Out-Null
    [System.IO.File]::WriteAllText($Path, $Text, $utf8NoBom)
    Write-Host "wrote $Path"
}

function Install-AppWorkflow([string]$AppDir, [string]$AppId, [string]$AppName, [string]$WorkDir = ".") {
    if (-not (Test-Path (Join-Path $AppDir ".git"))) {
        Write-Warning "$AppDir is not a git repo yet; writing the workflow anyway."
    }
    $text = [System.IO.File]::ReadAllText((Join-Path $templates "release-android.yml"))
    $text = $text -replace '(?m)^  APP_ID: CHANGE_ME', "  APP_ID: $AppId"
    $text = $text -replace '(?m)^  APP_NAME: CHANGE_ME', "  APP_NAME: $AppName"
    if ($WorkDir -ne ".") {
        $text = $text -replace '(?m)^        working-directory: \.(\s)', "        working-directory: $WorkDir`$1"
    }
    if ($text -match 'CHANGE_ME') { throw "Template placeholders not replaced for $AppId" }
    Write-Workflow (Join-Path $AppDir ".github\workflows\release-android.yml") $text
}

# Release feed: catalog builder
Write-Workflow (Join-Path $repo ".github\workflows\catalog.yml") `
    ([System.IO.File]::ReadAllText((Join-Path $templates "catalog.yml")))

# Apps (id must match jan-releases\apps.json)
Install-AppWorkflow (Join-Path $Root "AppHub")   "apphub"   "AppHub"
Install-AppWorkflow (Join-Path $Root "Hydrobot") "hydrobot" "HYDROBOT"
Install-AppWorkflow (Join-Path $Root "400nm")        "nm400"     "400nm"       "_400nm"
Install-AppWorkflow (Join-Path $Root "Kamurulan")    "kamurulan" "Kamurulan"   "KamurulanMobile"
Install-AppWorkflow (Join-Path $Root "DualNBackApp") "dualnback" "Dual N-Back" "dual_n_back"
