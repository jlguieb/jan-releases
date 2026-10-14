# jan-releases

Public release feed for Jan's Android apps. **No source code lives here.**
Each app's private repo builds a signed APK on a version tag and publishes it
here; `catalog.json` is rebuilt automatically and AppHub reads it.

```
app repo: push tag v1.2.0
  -> .github/workflows/release-android.yml builds + signs the APK
  -> release "hydrobot-v1.2.0" created here (APK + versionCode + sha256)
  -> .github/workflows/catalog.yml rebuilds catalog.json
  -> AppHub shows "Update"
```

Catalog URL used by AppHub:
`https://raw.githubusercontent.com/jlguieb/jan-releases/main/catalog.json`

Everything in this repo is public, including the APKs. Don't publish an app
here that must stay private.

## One-time setup

### 1. Create this repo (public)

Workflow files live in `templates\` and are put in place by a script (it also
installs the release workflow into AppHub and Hydrobot):

```powershell
cd C:\Users\JLAURENCE\Documents\Programming\jan-releases
powershell -ExecutionPolicy Bypass -File .\scripts\install-workflows.ps1
git init -b main
git add .
git commit -m "Release feed: apps.json, catalog builder, catalog workflow"
gh repo create jlguieb/jan-releases --public --source . --push
```

### 2. Create the release token (once, shared by all app repos)

GitHub > Settings > Developer settings > Fine-grained tokens > Generate new token:
- Repository access: **Only select repositories > jan-releases**
- Permissions: **Contents: Read and write**
- Expiration: up to 1 year. Put a reminder in your calendar to renew it; when it
  expires, releases fail at the "Publish to jan-releases" step.

Copy the token. It goes into each app repo as `RELEASES_TOKEN` (step 3).

### 3. Per app: signing key + secrets

One upload key per app. **Back up the .jks file and its password outside the
laptop (e.g. Google Drive + password manager). If you lose it, every phone
must uninstall the app before it can take another update.**

```powershell
$keytool = "C:\Program Files\Android\Android Studio\jbr\bin\keytool.exe"
New-Item -ItemType Directory -Force "$env:USERPROFILE\keys" | Out-Null
& $keytool -genkeypair -v -keystore "$env:USERPROFILE\keys\hydrobot-upload.jks" `
  -keyalg RSA -keysize 2048 -validity 10000 -alias upload
```
Use the same password for the keystore and the key (the default PKCS12 format
uses one password for both).

Then, from the app's folder (needs the GitHub CLI, `winget install GitHub.cli`, then `gh auth login`):

```powershell
cd C:\Users\JLAURENCE\Documents\Programming\Hydrobot
[Convert]::ToBase64String([IO.File]::ReadAllBytes("$env:USERPROFILE\keys\hydrobot-upload.jks")) | gh secret set ANDROID_KEYSTORE_BASE64
gh secret set ANDROID_KEY_ALIAS --body upload
gh secret set ANDROID_KEYSTORE_PASSWORD   # prompts for the value
gh secret set ANDROID_KEY_PASSWORD        # same password
gh secret set RELEASES_TOKEN              # paste the token from step 2
```

### 4. Per app: workflow + catalog entry

1. Add an `Install-AppWorkflow` line for the app at the bottom of
   `scripts\install-workflows.ps1` (id, display name, and the subfolder holding
   pubspec.yaml if it isn't the repo root, e.g. Kamurulan: `KamurulanMobile`), then run the script.
2. Make sure `android/app/build.gradle.kts` has the release `signingConfigs` block
   (copy it from Hydrobot) and a final `applicationId`.
3. Add the app to `apps.json` here (id must equal `APP_ID`, package must equal
   `applicationId`). Commit and push; the catalog rebuilds.

## Releasing a version

```powershell
# in the app repo
# 1. bump pubspec.yaml: version: 1.2.0+5   (the +number must go up every release)
git commit -am "Release 1.2.0"
git tag v1.2.0
git push; git push origin v1.2.0
```
Beta: `version: 1.3.0-beta.1+6`, tag `v1.3.0-beta.1`. Only phones with
"Get beta versions" ticked in AppHub see it.

Watch it: app repo > Actions > Release Android, then this repo > Actions > Build catalog.
About 6 to 10 minutes from tag to "Update" in AppHub.

## Web apps

Add to `apps.json`; AppHub shows an Open button:
```json
{ "id": "leatherwallet", "name": "Leather Wallet", "type": "web", "url": "https://<your-site>", "description": "..." }
```

## Icons and store details (optional)

Put a 192x192 PNG in `icons/<id>.png` and add `"icon": "icons/<id>.png"` to the app's entry.

Other optional fields AppHub shows on the app's page:
```json
"developer": "Impedence",
"category": "IoT",
"minSdk": 24,
"screenshots": ["screenshots/hydrobot-1.png", "screenshots/hydrobot-2.png"]
```
Screenshots are portrait PNG/JPG files in this repo (paths) or full URLs.
The last 10 releases of each app are added to the catalog as `history`.

## Pull a bad release

Delete the release on GitHub (or mark it pre-release). The catalog rebuilds and
AppHub offers the previous version only to phones that don't have it yet.
Phones can't downgrade, so the fix for a bad version is a new, higher version.

## Test the catalog builder locally

```powershell
python scripts\build_catalog.py --releases-file tests\releases.json --out $env:TEMP\catalog.json
```
