#!/usr/bin/env python3
"""
Plex Missing Subtitles Downloader

Downloads missing subtitles for media in your Plex library using OpenSubtitles API.
Focuses on movies and TV shows that don't have subtitles in specified languages.
"""

import os
import sys
import argparse
import logging
import time
import requests
from pathlib import Path
from typing import List, Set, Optional, Dict
from plexapi.server import PlexServer
from plexapi.video import Movie, Episode
from dotenv import load_dotenv
from dataclasses import dataclass, field
from datetime import datetime

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class DownloadedSubtitle:
    """Record of a downloaded subtitle."""
    media_title: str
    media_type: str  # 'movie' or 'episode'
    language: str
    subtitle_file: str
    rating: float
    download_count: int
    release_name: str
    uploader: str
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class OpenSubtitlesAPI:
    """OpenSubtitles API v1 client with rate limiting."""

    BASE_URL = "https://api.opensubtitles.com/api/v1"

    def __init__(
            self,
            api_key: str,
            username: str = None,
            password: str = None,
            user_agent: str = "PlexSubDownloader v1.0"
    ):
        """
        Initialize OpenSubtitles API client.

        Args:
            api_key: OpenSubtitles API key
            username: OpenSubtitles username (for downloads)
            password: OpenSubtitles password (for downloads)
            user_agent: User agent string (required by API)
        """
        self.api_key = api_key
        self.username = username
        self.password = password
        self.user_agent = user_agent
        self.jwt_token = None
        self.token_expiry = None
        self.headers = {
            "Api-Key": api_key,
            "User-Agent": user_agent,
            "Content-Type": "application/json"
        }
        self.last_request_time = 0
        self.min_request_interval = 1.0  # Minimum 1 second between requests
        self.remaining_downloads = None

    def _wait_for_rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            sleep_time = self.min_request_interval - elapsed
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    def _handle_rate_limit_error(self, response: requests.Response) -> bool:
        """
        Handle rate limit errors from API.

        Returns:
            True if should retry, False otherwise
        """
        if response.status_code == 429:
            retry_after = response.headers.get('Retry-After')
            if retry_after:
                wait_time = int(retry_after)
                logger.warning(f"Rate limit exceeded. Waiting {wait_time} seconds...")
                time.sleep(wait_time)
                return True
            else:
                logger.error("Rate limit exceeded with no Retry-After header")
                return False
        return False

    def login(self) -> bool:
        """
        Authenticate and obtain JWT token for downloads.

        Returns:
            True if login successful, False otherwise
        """
        if not self.username or not self.password:
            logger.warning("No username/password provided. Downloads will not be available.")
            return False

        logger.info("Logging in to OpenSubtitles...")
        self._wait_for_rate_limit()

        try:
            response = requests.post(
                f"{self.BASE_URL}/login",
                headers=self.headers,
                json={
                    "username": self.username,
                    "password": self.password
                },
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                self.jwt_token = data.get('token')
                logger.info("Successfully logged in")
                return True
            elif response.status_code == 401:
                logger.error("Invalid username or password")
                return False
            else:
                logger.error(f"Login failed: {response.status_code} - {response.text}")
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"Login request failed: {e}")
            return False

    def search_subtitles(
            self,
            query: str = None,
            imdb_id: str = None,
            tmdb_id: str = None,
            languages: str = "en",
            movie_hash: str = None,
            file_size: int = None,
            season_number: int = None,
            episode_number: int = None
    ) -> Optional[List[Dict]]:
        """
        Search for subtitles.

        Args:
            query: Movie or TV show name
            imdb_id: IMDB ID (without 'tt' prefix)
            tmdb_id: TMDB ID
            languages: Comma-separated language codes (e.g., "en,es")
            movie_hash: OpenSubtitles movie hash
            file_size: File size in bytes
            season_number: Season number for TV shows
            episode_number: Episode number for TV shows

        Returns:
            List of subtitle results or None on error
        """
        self._wait_for_rate_limit()

        params = {
            "languages": languages,
        }

        if query:
            params["query"] = query
        if imdb_id:
            params["imdb_id"] = imdb_id
        if tmdb_id:
            params["tmdb_id"] = tmdb_id
        if movie_hash:
            params["moviehash"] = movie_hash
        if file_size:
            params["moviebytesize"] = file_size
        if season_number is not None:
            params["season_number"] = season_number
        if episode_number is not None:
            params["episode_number"] = episode_number

        try:
            response = requests.get(
                f"{self.BASE_URL}/subtitles",
                headers=self.headers,
                params=params,
                timeout=30
            )

            if self._handle_rate_limit_error(response):
                # Retry once after rate limit wait
                response = requests.get(
                    f"{self.BASE_URL}/subtitles",
                    headers=self.headers,
                    params=params,
                    timeout=30
                )

            if response.status_code == 200:
                data = response.json()
                return data.get('data', [])
            elif response.status_code == 401:
                logger.error("Invalid API key")
                return None
            elif response.status_code == 406:
                logger.debug("No subtitles found")
                return []
            else:
                logger.error(f"API error: {response.status_code} - {response.text}")
                return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return None

    def download_subtitle(self, file_id: int) -> Optional[bytes]:
        """
        Download a subtitle file.

        Args:
            file_id: OpenSubtitles file ID

        Returns:
            Subtitle content as bytes or None on error
        """
        # Ensure we're logged in
        if not self.jwt_token:
            if not self.login():
                logger.error("Cannot download - not logged in")
                return None

        # Check daily download limit
        if self.remaining_downloads is not None and self.remaining_downloads <= 0:
            logger.error("Daily download limit reached")
            return None

        self._wait_for_rate_limit()

        # Create headers with JWT token
        download_headers = self.headers.copy()
        download_headers["Authorization"] = f"Bearer {self.jwt_token}"

        try:
            # Request download link
            response = requests.post(
                f"{self.BASE_URL}/download",
                headers=download_headers,
                json={"file_id": file_id},
                timeout=30
            )

            if self._handle_rate_limit_error(response):
                # Retry once after rate limit wait
                response = requests.post(
                    f"{self.BASE_URL}/download",
                    headers=download_headers,
                    json={"file_id": file_id},
                    timeout=30
                )

            if response.status_code == 200:
                data = response.json()
                download_link = data.get('link')
                self.remaining_downloads = data.get('remaining', self.remaining_downloads)

                if download_link:
                    # Download the actual subtitle file
                    sub_response = requests.get(download_link, timeout=30)
                    if sub_response.status_code == 200:
                        logger.debug(f"Remaining downloads: {self.remaining_downloads}")
                        return sub_response.content
                    else:
                        logger.error(f"Failed to download subtitle file: {sub_response.status_code}")
                        return None
            elif response.status_code == 401:
                logger.error("Invalid token - trying to re-login")
                self.jwt_token = None
                if self.login():
                    # Retry download with new token
                    return self.download_subtitle(file_id)
                return None
            elif response.status_code == 406:
                logger.error("Download limit reached or subtitle unavailable")
                return None
            else:
                logger.error(f"Download API error: {response.status_code} - {response.text}")
                return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Download request failed: {e}")
            return None

        return None


class PlexSubtitleDownloader:
    """Downloads missing subtitles for Plex media items."""

    def __init__(
            self,
            plex_url: str,
            plex_token: str,
            opensubtitles_api_key: str,
            opensubtitles_username: str = None,
            opensubtitles_password: str = None,
            languages: List[str] = None
    ):
        """
        Initialize the subtitle downloader.

        Args:
            plex_url: Plex server URL
            plex_token: Plex authentication token
            opensubtitles_api_key: OpenSubtitles API key
            opensubtitles_username: OpenSubtitles username (required for downloads)
            opensubtitles_password: OpenSubtitles password (required for downloads)
            languages: List of language codes (e.g., ['en', 'es'])
        """
        self.plex = PlexServer(plex_url, plex_token)
        self.api = OpenSubtitlesAPI(
            opensubtitles_api_key,
            opensubtitles_username,
            opensubtitles_password
        )
        self.languages = languages or ['en']
        self.download_report: List[DownloadedSubtitle] = []

        logger.info(f"Connected to Plex server: {self.plex.friendlyName}")
        logger.info(f"Target languages: {', '.join(self.languages)}")

        # Login to OpenSubtitles
        if opensubtitles_username and opensubtitles_password:
            self.api.login()
        else:
            logger.warning("No OpenSubtitles credentials provided. Downloads will not work.")

    def get_existing_subtitle_languages(self, item) -> Set[str]:
        """Get language codes of existing subtitles for a media item."""
        existing_langs = set()

        for stream in item.subtitleStreams():
            if stream.languageCode:
                # Normalize to 2-letter codes
                lang_code = stream.languageCode.lower()
                if len(lang_code) == 3:
                    # Convert common 3-letter codes to 2-letter
                    conversions = {'eng': 'en', 'spa': 'es', 'fra': 'fr', 'deu': 'de', 'ita': 'it', 'por': 'pt'}
                    lang_code = conversions.get(lang_code, lang_code[:2])
                existing_langs.add(lang_code)

        return existing_langs

    def needs_subtitles(self, item) -> Set[str]:
        """
        Check which target languages are missing subtitles.

        Returns:
            Set of missing language codes
        """
        existing = self.get_existing_subtitle_languages(item)
        missing = set(self.languages) - existing
        return missing

    def get_media_path(self, item) -> Optional[Path]:
        """Get the file path for a media item."""
        try:
            if hasattr(item, 'media') and item.media:
                if item.media[0].parts:
                    file_path = item.media[0].parts[0].file
                    return Path(file_path)
        except Exception as e:
            logger.error(f"Error getting media path: {e}")
        return None

    def get_subtitle_path(self, media_path: Path, language: str, forced: bool = False) -> Path:
        """Generate subtitle file path."""
        suffix = f".{language}"
        if forced:
            suffix += ".forced"
        suffix += ".srt"
        return media_path.with_suffix(suffix)

    def subtitle_exists(self, media_path: Path, language: str) -> bool:
        """Check if subtitle file already exists on disk."""
        subtitle_path = self.get_subtitle_path(media_path, language)
        return subtitle_path.exists()

    def download_subtitles_for_item(self, item) -> int:
        """
        Download missing subtitles for a single item.

        Returns:
            Number of subtitles downloaded
        """
        media_path = self.get_media_path(item)
        if not media_path:
            logger.warning(f"Could not get path for: {item.title}")
            return 0

        if not media_path.exists():
            logger.warning(f"File not found: {media_path}")
            return 0

        # Get missing languages (not in Plex metadata)
        missing = self.needs_subtitles(item)

        # Also check if subtitle files exist on disk
        missing = {lang for lang in missing if not self.subtitle_exists(media_path, lang)}

        if not missing:
            return 0

        item_name = f"{item.title}"
        media_type = "movie"
        if isinstance(item, Episode):
            item_name = f"{item.grandparentTitle} - S{item.seasonNumber:02d}E{item.index:02d} - {item.title}"
            media_type = "episode"

        logger.info(f"Downloading subtitles for: {item_name}")
        logger.info(f"  Missing languages: {', '.join(missing)}")

        downloaded_count = 0

        # Prepare search parameters
        search_params = {
            "languages": ",".join(missing),
            "file_size": media_path.stat().st_size
        }

        # Add IMDB ID if available (preferred)
        try:
            for guid in item.guids:
                if guid.id.startswith('imdb://'):
                    imdb_id = guid.id.replace('imdb://tt', '')
                    search_params["imdb_id"] = imdb_id
                    break
                elif guid.id.startswith('tmdb://'):
                    tmdb_id = guid.id.replace('tmdb://', '')
                    search_params["tmdb_id"] = tmdb_id
                    break
        except:
            pass

        # Add episode info for TV shows
        if isinstance(item, Episode):
            search_params["season_number"] = item.seasonNumber
            search_params["episode_number"] = item.index
            if not search_params.get("imdb_id") and not search_params.get("tmdb_id"):
                search_params["query"] = item.grandparentTitle
        else:
            if not search_params.get("imdb_id") and not search_params.get("tmdb_id"):
                search_params["query"] = item.title

        # Search for subtitles
        logger.info(f"  Searching for subtitles...")
        results = self.api.search_subtitles(**search_params)

        if results is None:
            logger.error(f"  ✗ Search failed")
            return 0

        if not results:
            logger.info(f"  ✗ No subtitles found")
            return 0

        logger.info(f"  Found {len(results)} subtitle option(s)")

        # Download best subtitle for each missing language
        for lang in missing:
            # Find subtitles for this language
            lang_results = [r for r in results if r.get('attributes', {}).get('language') == lang]

            if not lang_results:
                logger.info(f"  ✗ No {lang} subtitles found")
                continue

            # Sort by rating first, then download count
            # Rating is more important for quality
            lang_results.sort(
                key=lambda x: (
                    x.get('attributes', {}).get('ratings', 0),
                    x.get('attributes', {}).get('download_count', 0)
                ),
                reverse=True
            )

            best = lang_results[0]
            attrs = best.get('attributes', {})
            file_id = attrs.get('files', [{}])[0].get('file_id')
            rating = attrs.get('ratings', 0.0)
            download_count = attrs.get('download_count', 0)
            release_name = attrs.get('release', 'Unknown')
            uploader = attrs.get('uploader', {}).get('name', 'Unknown')

            if not file_id:
                logger.warning(f"  ✗ No file ID for {lang} subtitle")
                continue

            logger.info(f"  Downloading {lang} subtitle (Rating: {rating:.1f}, Downloads: {download_count})...")
            content = self.api.download_subtitle(file_id)

            if content:
                # Save subtitle file
                subtitle_path = self.get_subtitle_path(media_path, lang)

                try:
                    with open(subtitle_path, 'wb') as f:
                        f.write(content)
                    logger.info(f"  ✓ Saved: {subtitle_path.name}")
                    downloaded_count += 1

                    # Add to download report
                    self.download_report.append(DownloadedSubtitle(
                        media_title=item_name,
                        media_type=media_type,
                        language=lang,
                        subtitle_file=str(subtitle_path),
                        rating=rating,
                        download_count=download_count,
                        release_name=release_name,
                        uploader=uploader
                    ))

                except Exception as e:
                    logger.error(f"  ✗ Failed to save subtitle: {e}")
            else:
                logger.warning(f"  ✗ Failed to download {lang} subtitle")

        return downloaded_count

    def generate_report(self) -> str:
        """Generate a detailed report of downloaded subtitles."""
        if not self.download_report:
            return "No subtitles were downloaded."

        report_lines = [
            "\n" + "=" * 80,
            "SUBTITLE DOWNLOAD REPORT",
            "=" * 80,
            f"Total subtitles downloaded: {len(self.download_report)}",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 80,
            ""
        ]

        # Group by media type
        movies = [s for s in self.download_report if s.media_type == 'movie']
        episodes = [s for s in self.download_report if s.media_type == 'episode']

        if movies:
            report_lines.append(f"\nMOVIES ({len(movies)} subtitles)")
            report_lines.append("-" * 80)
            for sub in movies:
                report_lines.append(f"\n{sub.media_title}")
                report_lines.append(f"  Language: {sub.language.upper()}")
                report_lines.append(f"  Rating: {sub.rating:.1f}/10")
                report_lines.append(f"  Downloads: {sub.download_count:,}")
                report_lines.append(f"  Release: {sub.release_name}")
                report_lines.append(f"  Uploader: {sub.uploader}")
                report_lines.append(f"  File: {Path(sub.subtitle_file).name}")
                report_lines.append(f"  Timestamp: {sub.timestamp}")

        if episodes:
            report_lines.append(f"\n\nTV EPISODES ({len(episodes)} subtitles)")
            report_lines.append("-" * 80)
            for sub in episodes:
                report_lines.append(f"\n{sub.media_title}")
                report_lines.append(f"  Language: {sub.language.upper()}")
                report_lines.append(f"  Rating: {sub.rating:.1f}/10")
                report_lines.append(f"  Downloads: {sub.download_count:,}")
                report_lines.append(f"  Release: {sub.release_name}")
                report_lines.append(f"  Uploader: {sub.uploader}")
                report_lines.append(f"  File: {Path(sub.subtitle_file).name}")
                report_lines.append(f"  Timestamp: {sub.timestamp}")

        # Summary statistics
        report_lines.append("\n" + "=" * 80)
        report_lines.append("SUMMARY STATISTICS")
        report_lines.append("=" * 80)

        avg_rating = sum(s.rating for s in self.download_report) / len(self.download_report)
        total_downloads = sum(s.download_count for s in self.download_report)

        report_lines.append(f"Average subtitle rating: {avg_rating:.1f}/10")
        report_lines.append(f"Total community downloads: {total_downloads:,}")

        # Language breakdown
        lang_counts = {}
        for sub in self.download_report:
            lang_counts[sub.language] = lang_counts.get(sub.language, 0) + 1

        report_lines.append("\nLanguage breakdown:")
        for lang, count in sorted(lang_counts.items()):
            report_lines.append(f"  {lang.upper()}: {count}")

        report_lines.append("=" * 80)

        return "\n".join(report_lines)

    def save_report(self, output_file: str = "subtitle_download_report.txt"):
        """Save the report to a file."""
        report = self.generate_report()
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report)
        logger.info(f"\nReport saved to: {output_file}")

    def process_library(
            self,
            library_name: str,
            media_type: str = None,
            max_downloads: int = None
    ) -> dict:
        """
        Process a Plex library and download missing subtitles.

        Args:
            library_name: Name of the Plex library
            media_type: Filter by 'movie' or 'episode', or None for all
            max_downloads: Maximum number of subtitles to download (None = unlimited)

        Returns:
            Dictionary with statistics
        """
        try:
            library = self.plex.library.section(library_name)
        except Exception as e:
            logger.error(f"Could not find library '{library_name}': {e}")
            return {}

        logger.info(f"\n{'=' * 60}")
        logger.info(f"Processing library: {library_name}")
        if max_downloads:
            logger.info(f"Max downloads: {max_downloads}")
        logger.info(f"{'=' * 60}\n")

        stats = {
            'total': 0,
            'needs_subtitles': 0,
            'downloaded': 0,
            'errors': 0,
            'skipped': 0
        }

        # Get all items
        items = []
        if media_type == 'movie' or library.type == 'movie':
            items = library.all()
            stats['total'] = len(items)
        elif media_type == 'episode' or library.type == 'show':
            # Get all episodes from all shows
            for show in library.all():
                for episode in show.episodes():
                    items.append(episode)
            stats['total'] = len(items)
        else:
            logger.warning(f"Unsupported library type: {library.type}")
            return stats

        logger.info(f"Found {len(items)} items to scan")

        # Process each item
        total_downloaded = 0
        for i, item in enumerate(items, 1):
            # Check if we've hit the download limit
            if max_downloads and total_downloaded >= max_downloads:
                stats['skipped'] = len(items) - i + 1
                logger.info(
                    f"\nReached download limit of {max_downloads}. Skipping remaining {stats['skipped']} items.")
                break

            try:
                missing = self.needs_subtitles(item)

                if missing:
                    stats['needs_subtitles'] += 1
                    logger.info(f"\n[{i}/{stats['total']}] Processing item...")

                    downloaded = self.download_subtitles_for_item(item)
                    if downloaded > 0:
                        stats['downloaded'] += downloaded
                        total_downloaded += downloaded
                else:
                    logger.debug(f"[{i}/{stats['total']}] Skipping {item.title} - has all subtitles")
            except Exception as e:
                logger.error(f"Error processing item {i}: {e}")
                stats['errors'] += 1

        # Print summary
        logger.info(f"\n{'=' * 60}")
        logger.info(f"Summary for {library_name}:")
        logger.info(f"  Total items scanned: {stats['total']}")
        logger.info(f"  Items needing subtitles: {stats['needs_subtitles']}")
        logger.info(f"  Subtitles downloaded: {stats['downloaded']}")
        if stats['skipped']:
            logger.info(f"  Items skipped (limit reached): {stats['skipped']}")
        logger.info(f"  Errors: {stats['errors']}")
        logger.info(f"{'=' * 60}\n")

        return stats

    def process_all_libraries(
            self,
            media_type: str = None,
            max_downloads: int = None
    ) -> dict:
        """Process all movie and TV show libraries."""
        total_stats = {
            'total': 0,
            'needs_subtitles': 0,
            'downloaded': 0,
            'errors': 0,
            'skipped': 0
        }

        total_downloaded = 0
        for library in self.plex.library.sections():
            if library.type in ['movie', 'show']:
                # Calculate remaining download budget
                remaining = None
                if max_downloads:
                    remaining = max_downloads - total_downloaded
                    if remaining <= 0:
                        logger.info(f"Skipping library '{library.title}' - download limit reached")
                        continue

                stats = self.process_library(library.title, media_type, remaining)
                for key in total_stats:
                    total_stats[key] += stats.get(key, 0)

                total_downloaded = total_stats['downloaded']

        return total_stats


def main():
    parser = argparse.ArgumentParser(
        description='Download missing subtitles for Plex media using OpenSubtitles API'
    )
    parser.add_argument(
        '--plex-url',
        default=os.getenv('PLEX_URL', 'http://localhost:32400'),
        help='Plex server URL (default: from .env or http://localhost:32400)'
    )
    parser.add_argument(
        '--plex-token',
        default=os.getenv('PLEX_TOKEN'),
        help='Plex authentication token (default: from .env)'
    )
    parser.add_argument(
        '--opensubtitles-api-key',
        default=os.getenv('OPENSUBTITLES_API_KEY'),
        help='OpenSubtitles API key (default: from .env)'
    )
    parser.add_argument(
        '--opensubtitles-username',
        default=os.getenv('OPENSUBTITLES_USERNAME'),
        help='OpenSubtitles username (default: from .env)'
    )
    parser.add_argument(
        '--opensubtitles-password',
        default=os.getenv('OPENSUBTITLES_PASSWORD'),
        help='OpenSubtitles password (default: from .env)'
    )
    parser.add_argument(
        '--languages',
        nargs='+',
        default=os.getenv('SUBTITLE_LANGUAGES', 'en').split(','),
        help='Language codes to download (e.g., en es fr)'
    )
    parser.add_argument(
        '--library',
        help='Specific library name to process (default: all)'
    )
    parser.add_argument(
        '--type',
        choices=['movie', 'episode'],
        help='Filter by media type'
    )
    parser.add_argument(
        '--max-downloads',
        type=int,
        help='Maximum number of subtitles to download (default: unlimited)'
    )
    parser.add_argument(
        '--report',
        default='subtitle_download_report.txt',
        help='Output file for download report (default: subtitle_download_report.txt)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate required environment variables
    if not args.plex_token:
        logger.error("PLEX_TOKEN is required. Set it in .env or pass --plex-token")
        sys.exit(1)

    if not args.opensubtitles_api_key:
        logger.error("OPENSUBTITLES_API_KEY is required. Set it in .env or pass --opensubtitles-api-key")
        sys.exit(1)

    if not args.opensubtitles_username or not args.opensubtitles_password:
        logger.error("OPENSUBTITLES_USERNAME and OPENSUBTITLES_PASSWORD are required for downloads")
        sys.exit(1)

    # Initialize downloader
    try:
        downloader = PlexSubtitleDownloader(
            plex_url=args.plex_url,
            plex_token=args.plex_token,
            opensubtitles_api_key=args.opensubtitles_api_key,
            opensubtitles_username=args.opensubtitles_username,
            opensubtitles_password=args.opensubtitles_password,
            languages=args.languages
        )
    except Exception as e:
        logger.error(f"Failed to initialize downloader: {e}")
        sys.exit(1)

    # Process libraries
    try:
        if args.library:
            downloader.process_library(args.library, args.type, args.max_downloads)
        else:
            downloader.process_all_libraries(args.type, args.max_downloads)

        # Generate and display report
        report = downloader.generate_report()
        print(report)

        # Save report to file
        if downloader.download_report:
            downloader.save_report(args.report)

    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
        # Still generate report for what was downloaded
        if downloader.download_report:
            print(downloader.generate_report())
            downloader.save_report(args.report)
        sys.exit(0)
    except Exception as e:
        logger.error(f"Error during processing: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()