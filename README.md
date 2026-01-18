# Plex Info

A comprehensive Python utility for analyzing your Plex library with detailed media information, quality analysis, statistics, and health checks.

## Features

### 📊 **Library Analysis**
- List all items with complete details including:
  - File path and size
  - Video quality (4K, 1080p, 720p, SD)
  - Video codec (H.264, H.265/HEVC, AV1)
  - Audio codec (AAC, DTS, Dolby Digital)
  - Watch status and view counts
  - Subtitle information (languages, formats, external/embedded)
  - Direct Plex web URLs

### 🔍 **Quality Analysis** (`--quality`)
- Resolution distribution (4K, 1080p, 720p, SD)
- Video codec distribution
- Audio codec distribution
- Percentage breakdowns

### 📈 **Statistics** (`--stats`)
- Watch statistics (watched vs unwatched)
- Content by year (top 10)
- Content by genre (top 10)
- Content ratings breakdown
- Total library size and runtime

### 🏥 **Health Checks** (`--health`)
- Missing metadata (no summary/year)
- Low quality content (SD only)
- Missing subtitles
- Very large files (>50GB)
- Never watched items

### 💻 **System Information** (`--system`)
- Plex server details (version, platform)
- Library statistics (item counts, total sizes)
- Local client information

## Requirements

- Python 3.7+
- Plex Media Server
- Plex authentication token

## Installation

1. Clone or download this repository

2. Install dependencies:
```bash
pip install -r requirements.txt
```

Dependencies:
- `plexapi>=4.15.0` - Plex API client
- `python-dotenv>=1.0.0` - Environment variable management
- `psutil>=5.9.0` - System information
- `gputil` (optional) - GPU information

3. Create a `.env` file in the same directory:
```env
PLEX_URL=http://192.168.0.199:32400
PLEX_TOKEN=your_plex_token_here
```

### Getting Your Plex Token

1. Open Plex Web App
2. Play any media item
3. Click the "..." menu → "Get Info"
4. Click "View XML"
5. Look in the URL bar for `X-Plex-Token=xxxxx`
6. Copy the token value

## Usage

### List All Available Libraries

Show all libraries on your Plex server:

```bash
python plex_info.py
```

### List Library Items

Show all items in a library with complete details:

```bash
# Movies
python plex_info.py --library "Movies"

# TV Shows (shows episodes)
python plex_info.py --library "TV Shows"
```

Each item displays:
- Title and rating key
- File path on server
- Plex web URL
- File size
- Video quality and codecs
- Watch status
- Subtitle details

### List Only Missing Subtitles

Filter to show only items without subtitles:

```bash
python plex_info.py --library "Movies" --list-missing
```

### Quality Analysis

Analyze video quality and codec distribution:

```bash
python plex_info.py --library "Movies" --quality
```

Shows:
- Resolution distribution (4K: 38 (9.1%), 1080p: 245 (58.9%), etc.)
- Video codec distribution (H264, HEVC, AV1)
- Audio codec distribution (AAC, DTS, Dolby Digital)

### Library Statistics

Get comprehensive library statistics:

```bash
python plex_info.py --library "Movies" --stats
```

Shows:
- Total items, size, and runtime
- Watched vs unwatched counts
- Top 10 years
- Top 10 genres
- Content rating breakdown

### Health Check

Identify potential issues in your library:

```bash
python plex_info.py --library "Movies" --health
```

Identifies:
- Items with missing metadata
- Low quality (SD) content
- Items without subtitles
- Very large files (>50GB)
- Never watched content

### System Information

View Plex server and library information:

```bash
python plex_info.py --system
```

Shows:
- Remote Plex server details
- Library statistics (counts and total sizes)
- Local client information

### Advanced Options

Filter by media type:
```bash
python plex_info.py --library "Movies" --type movie
```

Save output to custom file:
```bash
python plex_info.py --library "Movies" --output my_report.txt
```

Enable verbose logging:
```bash
python plex_info.py --library "Movies" --verbose
```

## Command Line Flags

| Flag | Description |
|------|-------------|
| `--library "NAME"` | Library name to analyze (e.g., "Movies", "TV Shows") |
| `--list-missing` | Show only items missing subtitles |
| `--quality` | Analyze video quality and codec distribution |
| `--stats` | Show general statistics (watch counts, genres, years) |
| `--health` | Check library health and identify issues |
| `--system` | Display Plex server and library information |
| `--type {movie\|episode}` | Filter by media type |
| `--output FILE` | Output file for report (default: library_subtitles.txt) |
| `--verbose` | Enable verbose logging |
| `--help` | Show help message with all available options |

## Example Workflows

### Complete Library Audit
```bash
# 1. List all libraries
python plex_info.py

# 2. Check quality distribution
python plex_info.py --library "Movies" --quality

# 3. Get detailed statistics
python plex_info.py --library "Movies" --stats

# 4. Run health check
python plex_info.py --library "Movies" --health

# 5. Find items missing subtitles
python plex_info.py --library "Movies" --list-missing
```

### Find Content to Upgrade
```bash
# Find SD content that could be upgraded
python plex_info.py --library "Movies" --health

# See quality breakdown
python plex_info.py --library "Movies" --quality
```

### Track Watch Progress
```bash
# See what hasn't been watched
python plex_info.py --library "Movies" --stats

# Get detailed view with watch status
python plex_info.py --library "Movies"
```

### Manage Storage
```bash
# Find very large files
python plex_info.py --library "Movies" --health

# See total library size
python plex_info.py --system
```

## Example Output

### Library Listing
```
1. Captain Marvel
   Rating Key: 644
   File Path: /media/Movies/Captain Marvel (2019)/Captain Marvel (2019) - 1080p.mkv
   URL: http://192.168.0.199:32400/web/index.html#!/server/.../details?key=/library/metadata/644
   File Size: 15.42 GB
   Quality: 1080p | Video: H264 | Audio: AAC
   Watched: ✓ Yes (Views: 3)
   Last Viewed: 2025-12-15 20:30:45
   Subtitles: YES
   Languages: EN, ES
   Streams:
     • English (EN) - srt - English [EMBEDDED]
     • Spanish (ES) - srt - Spanish (Latin America) [EXTERNAL]
```

### Quality Analysis
```
RESOLUTION DISTRIBUTION
--------------------------------------------------------------------------------
1080p          :   245 (58.9%)
720p           :   123 (29.6%)
4K             :    38 ( 9.1%)
SD             :    10 ( 2.4%)

VIDEO CODEC DISTRIBUTION
--------------------------------------------------------------------------------
H264           :   312 (75.0%)
HEVC           :    94 (22.6%)
AV1            :    10 ( 2.4%)
```

### Health Check
```
LIBRARY HEALTH CHECK - Movies
================================================================================

MISSING SUBTITLES: 70 items
--------------------------------------------------------------------------------
1. Avatar
2. The Batman
3. Inception
... and 67 more

NEVER WATCHED: 142 items
--------------------------------------------------------------------------------
1. Movie Title 1
2. Movie Title 2
... and 140 more
```

## Troubleshooting

### "Could not find library"
- Ensure the library name matches exactly (case-sensitive)
- Use quotes around library names with spaces: `--library "TV Shows"`
- Run `python plex_info.py` without arguments to see available libraries

### "PLEX_TOKEN is required"
- Create a `.env` file with your Plex token
- Or pass it directly: `--plex-token YOUR_TOKEN`

### Connection errors
- Verify your Plex server is running
- Check the PLEX_URL in your `.env` file
- Ensure you can access Plex Web from the same machine

### Slow performance
- Large libraries (1000+ items) may take a few minutes to scan
- Use `--verbose` to see progress
- Quality/stats/health checks are slower as they analyze each item

## File Structure

```
.
├── plex_info.py           # Main script
├── requirements.txt       # Python dependencies
├── .env                   # Your Plex credentials (create this)
└── README.md             # This file
```

## Output Files

Reports are saved to the current directory:
- `library_subtitles.txt` - Default output file
- Custom filename via `--output` flag

Reports contain all displayed information for later reference.

## Notes

- The tool is **read-only** - it never modifies your Plex library
- System info shows local client stats, not remote Plex server hardware
- File paths are from the Plex server's perspective
- URLs open items directly in Plex web interface
- Episode counts are shown for TV libraries, not show counts

## License

MIT License - Feel free to use and modify as needed.

## Contributing

Found a bug or want a feature? Please open an issue or submit a pull request!