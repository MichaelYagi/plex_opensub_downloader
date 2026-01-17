# Plex Selenium Subtitle Downloader - Setup Guide

This is a complete rewrite that automates the Plex web UI using Selenium to download subtitles.

## Why Selenium?

The Plex API method wasn't working reliably (500 errors), so this script automates what you would do manually:
1. Opens Plex in a browser
2. Navigates to each movie/show
3. Clicks the subtitle dropdown
4. Clicks "Search"
5. Selects the subtitle with the most stars
6. Downloads it

## Installation

### 1. Install Python dependencies

```bash
pip install -r requirements_selenium.txt
```

### 2. Install ChromeDriver

**On Mac:**
```bash
brew install chromedriver
```

**On Linux/WSL2:**
```bash
# Download ChromeDriver
wget https://chromedriver.storage.googleapis.com/LATEST_RELEASE
LATEST=$(cat LATEST_RELEASE)
wget https://chromedriver.storage.googleapis.com/${LATEST}/chromedriver_linux64.zip
unzip chromedriver_linux64.zip
sudo mv chromedriver /usr/local/bin/
sudo chmod +x /usr/local/bin/chromedriver
```

**On Windows:**
- Download from https://chromedriver.chromium.org/
- Add to PATH

### 3. Verify ChromeDriver works

```bash
chromedriver --version
```

## Configuration

Your existing `.env` file works:

```bash
PLEX_URL=http://192.168.0.199:32400
PLEX_TOKEN=your-token-here
SUBTITLE_LANGUAGES=en
```

## Usage

### Basic Usage

```bash
# Download subtitles for Movies library (shows browser)
python selenium_downloader.py --library "Movies" --max-downloads 10

# Download for TV Shows
python selenium_downloader.py --library "TV Shows" --max-downloads 5
```

### Headless Mode (No Browser Window)

```bash
# Run without showing browser (faster, good for automation)
python selenium_downloader.py --library "Movies" --max-downloads 10 --headless
```

### Filter by Type

```bash
# Only movies
python selenium_downloader.py --library "Movies" --type movie --max-downloads 10

# Only episodes
python selenium_downloader.py --library "TV Shows" --type episode --max-downloads 5
```

### Multiple Languages

```bash
python selenium_downloader.py --library "Movies" --languages en es --max-downloads 10
```

## How It Works

1. **Connects to Plex API** - Gets list of items missing subtitles
2. **Opens Chrome browser** - Authenticates using your Plex token
3. **For each item missing subtitles:**
   - Navigates to the item's page
   - Clicks the "Subtitles" dropdown
   - Clicks "Search"
   - Finds all subtitle results
   - Counts the stars on each subtitle
   - Selects and downloads the one with the most stars
4. **Generates report** - Shows what succeeded/failed

## Example Output

```
2026-01-17 11:00:00 - __main__ - INFO - Connected to Plex server: M1 Mac Mini
2026-01-17 11:00:00 - __main__ - INFO - Target languages: en
============================================================
Processing library: Movies
Max downloads: 10
============================================================

Found 416 items to scan
2026-01-17 11:00:05 - __main__ - INFO - Chrome WebDriver initialized
2026-01-17 11:00:10 - __main__ - INFO - Successfully logged into Plex

[1/416] Needs subtitles
============================================================
Processing: Inception
URL: http://192.168.0.199:32400/web/index.html#!/server/.../details?key=/library/metadata/123
============================================================
2026-01-17 11:00:15 - __main__ - INFO - Navigating to item page...
2026-01-17 11:00:18 - __main__ - INFO - Looking for subtitle button...
2026-01-17 11:00:19 - __main__ - INFO - Found subtitle button
2026-01-17 11:00:19 - __main__ - INFO - Clicking subtitle button...
2026-01-17 11:00:21 - __main__ - INFO - Looking for Search option...
2026-01-17 11:00:21 - __main__ - INFO - Found search button
2026-01-17 11:00:21 - __main__ - INFO - Clicking Search...
2026-01-17 11:00:24 - __main__ - INFO - Looking for subtitle results...
2026-01-17 11:00:24 - __main__ - INFO - Found 8 subtitle results
2026-01-17 11:00:24 - __main__ - INFO - Selecting subtitle with 5 stars
2026-01-17 11:00:26 - __main__ - INFO - ✓ Successfully downloaded subtitle for Inception
```

## Generated Report

After running, you'll get a report like:

```
================================================================================
SUBTITLE DOWNLOAD REPORT (SELENIUM)
================================================================================
Total processed: 10
Successful: 8
Failed: 2
Generated: 2026-01-17 11:15:30
================================================================================

SUCCESSFUL DOWNLOADS (8)
--------------------------------------------------------------------------------

Inception
  Type: movie
  Rating: 5 stars
  Timestamp: 2026-01-17 11:00:26

The Matrix
  Type: movie
  Rating: 4 stars
  Timestamp: 2026-01-17 11:02:15

FAILED DOWNLOADS (2)
--------------------------------------------------------------------------------

Some Obscure Movie
  Type: movie
  Error: No subtitle results found
  URL: http://192.168.0.199:32400/web/index.html#!/server/.../details?key=/library/metadata/999
```

## Troubleshooting

### "ChromeDriver not found"
```bash
# Install ChromeDriver (see Installation section above)
```

### "Failed to initialize Chrome WebDriver"
```bash
# Make sure Chrome browser is installed
# On Mac: brew install google-chrome
# On Linux: sudo apt-get install chromium-browser
```

### Plex UI changed / buttons not found
The script tries multiple selectors, but if Plex changes their UI significantly, you may need to:
1. Run without `--headless` to see what's happening
2. Check the error messages
3. Update the selectors in the script

### Browser opens but nothing happens
- Check your `PLEX_TOKEN` is correct
- Make sure you can access Plex at the URL in your browser manually

## Performance

- **With GUI (no --headless):** ~15-30 seconds per item
- **Headless mode:** ~10-20 seconds per item
- Downloading 10 subtitles takes approximately 3-5 minutes

## Advantages Over API Method

✅ Works when Plex API gives 500 errors  
✅ Selects highest-rated subtitles  
✅ Uses Plex's own search (same as manual)  
✅ No OpenSubtitles API credentials needed  
✅ Handles Plex authentication automatically  

## Disadvantages

❌ Slower than direct API (15-30s vs 2-5s per item)  
❌ Requires ChromeDriver installation  
❌ Breaks if Plex UI changes significantly  
❌ Uses more resources (runs full browser)  

## Recommendation

Use this Selenium method when:
- The API method gives errors
- You want the highest-rated subtitles
- You don't mind it being slower
- You're running interactively (can watch progress)

Use the original API method when:
- You have filesystem access (running on Plex server)
- You want speed
- You want to download hundreds of subtitles