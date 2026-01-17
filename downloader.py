#!/usr/bin/env python3
"""
Plex Subtitle Downloader - Selenium UI Automation

Automates the Plex web interface to download subtitles by:
1. Scanning library for items missing subtitles
2. Opening each item's page
3. Clicking the subtitle dropdown
4. Searching for subtitles
5. Selecting the highest-rated subtitle
"""

import os
import sys
import time
import argparse
import logging
from pathlib import Path
from typing import List, Set, Optional
from dotenv import load_dotenv
from dataclasses import dataclass, field
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from plexapi.server import PlexServer
from plexapi.video import Movie, Episode

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
    media_type: str
    language: str
    rating: str
    plex_url: str
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    success: bool = True
    error: str = ""


class PlexSeleniumDownloader:
    """Automates Plex UI to download subtitles using Selenium."""

    def __init__(
            self,
            plex_url: str,
            plex_token: str,
            languages: List[str] = None,
            headless: bool = False
    ):
        """
        Initialize the Selenium-based downloader.

        Args:
            plex_url: Plex server URL
            plex_token: Plex authentication token
            languages: List of language codes
            headless: Run browser in headless mode
        """
        self.plex = PlexServer(plex_url, plex_token)
        self.plex_url = plex_url
        self.plex_token = plex_token
        self.languages = languages or ['en']
        self.headless = headless
        self.driver = None
        self.download_report: List[DownloadedSubtitle] = []

        logger.info(f"Connected to Plex server: {self.plex.friendlyName}")
        logger.info(f"Target languages: {', '.join(self.languages)}")

    def setup_driver(self):
        """Set up the Selenium WebDriver."""
        chrome_options = Options()

        if self.headless:
            chrome_options.add_argument('--headless')

        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')

        # Disable notifications
        prefs = {
            "profile.default_content_setting_values.notifications": 2
        }
        chrome_options.add_experimental_option("prefs", prefs)

        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            logger.info("Chrome WebDriver initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Chrome WebDriver: {e}")
            logger.error("Make sure ChromeDriver is installed: https://chromedriver.chromium.org/")
            sys.exit(1)

    def login_to_plex(self):
        """Navigate to Plex and authenticate using token."""
        try:
            # Navigate to Plex web with token authentication
            web_url = f"{self.plex_url}/web/index.html"
            logger.info(f"Navigating to Plex: {web_url}")
            self.driver.get(web_url)

            # Set authentication token in local storage
            self.driver.execute_script(f"localStorage.setItem('myPlexAccessToken', '{self.plex_token}');")

            # Refresh to apply authentication
            self.driver.refresh()

            # Wait for Plex to load
            logger.info("Waiting for Plex to load...")
            time.sleep(5)

            logger.info("Successfully logged into Plex")

        except Exception as e:
            logger.error(f"Failed to login to Plex: {e}")
            raise

    def get_existing_subtitle_languages(self, item) -> Set[str]:
        """Get language codes of existing subtitles."""
        existing_langs = set()

        for stream in item.subtitleStreams():
            if stream.languageCode:
                lang_code = stream.languageCode.lower()
                if len(lang_code) == 3:
                    conversions = {'eng': 'en', 'spa': 'es', 'fra': 'fr', 'deu': 'de', 'ita': 'it', 'por': 'pt'}
                    lang_code = conversions.get(lang_code, lang_code[:2])
                existing_langs.add(lang_code)
            else:
                # Unlabeled subtitle - assume English
                existing_langs.add('en')

        return existing_langs

    def needs_subtitles(self, item) -> Set[str]:
        """Check which languages are missing subtitles."""
        existing = self.get_existing_subtitle_languages(item)
        missing = set(self.languages) - existing
        return missing

    def download_subtitle_for_item(self, item, plex_item_url: str) -> bool:
        """
        Download subtitle for a single item using Plex UI automation.

        Args:
            item: Plex media item
            plex_item_url: Direct URL to the item in Plex

        Returns:
            True if subtitle was downloaded successfully
        """
        item_name = item.title
        if isinstance(item, Episode):
            item_name = f"{item.grandparentTitle} - S{item.seasonNumber:02d}E{item.index:02d} - {item.title}"

        media_type = "episode" if isinstance(item, Episode) else "movie"

        logger.info(f"\n{'=' * 60}")
        logger.info(f"Processing: {item_name}")
        logger.info(f"URL: {plex_item_url}")

        try:
            # Navigate to the item's page
            logger.info("Navigating to item page...")
            self.driver.get(plex_item_url)
            time.sleep(3)  # Wait for page to load

            # Find and click the subtitle button/dropdown
            logger.info("Looking for subtitle button...")

            # Try multiple selectors as Plex UI can vary
            subtitle_button_selectors = [
                "//button[contains(@class, 'subtitle')]",
                "//button[contains(@aria-label, 'Subtitle')]",
                "//button[contains(@aria-label, 'subtitle')]",
                "//div[contains(@class, 'subtitle')]//button",
                "//*[contains(text(), 'Subtitles')]",
                "//*[contains(text(), 'subtitles')]"
            ]

            subtitle_button = None
            for selector in subtitle_button_selectors:
                try:
                    subtitle_button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    logger.info(f"Found subtitle button with selector: {selector}")
                    break
                except TimeoutException:
                    continue

            if not subtitle_button:
                logger.error("Could not find subtitle button")
                self.download_report.append(DownloadedSubtitle(
                    media_title=item_name,
                    media_type=media_type,
                    language="en",
                    rating="N/A",
                    plex_url=plex_item_url,
                    success=False,
                    error="Subtitle button not found"
                ))
                return False

            # Click the subtitle button
            logger.info("Clicking subtitle button...")
            subtitle_button.click()
            time.sleep(2)

            # Look for "Search" option in the modal
            logger.info("Looking for Search option...")
            search_button_selectors = [
                "//button[contains(text(), 'Search')]",
                "//div[contains(text(), 'Search')]",
                "//*[@role='button' and contains(text(), 'Search')]"
            ]

            search_button = None
            for selector in search_button_selectors:
                try:
                    search_button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    logger.info(f"Found search button with selector: {selector}")
                    break
                except TimeoutException:
                    continue

            if not search_button:
                logger.error("Could not find Search button")
                self.download_report.append(DownloadedSubtitle(
                    media_title=item_name,
                    media_type=media_type,
                    language="en",
                    rating="N/A",
                    plex_url=plex_item_url,
                    success=False,
                    error="Search button not found"
                ))
                return False

            # Click Search
            logger.info("Clicking Search...")
            search_button.click()
            time.sleep(3)  # Wait for search results

            # Find subtitle results with star ratings
            logger.info("Looking for subtitle results...")

            # Look for star ratings or subtitle list items
            subtitle_items = self.driver.find_elements(By.XPATH,
                                                       "//*[contains(@class, 'subtitle-result') or contains(@class, 'SubtitleSearchResult')]")

            if not subtitle_items:
                # Try alternative selectors
                subtitle_items = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'SearchResult')]")

            if not subtitle_items:
                logger.warning("No subtitle results found")
                self.download_report.append(DownloadedSubtitle(
                    media_title=item_name,
                    media_type=media_type,
                    language="en",
                    rating="N/A",
                    plex_url=plex_item_url,
                    success=False,
                    error="No subtitle results found"
                ))
                return False

            logger.info(f"Found {len(subtitle_items)} subtitle results")

            # Find the subtitle with the most stars
            best_subtitle = None
            best_rating = 0

            for idx, item_elem in enumerate(subtitle_items):
                try:
                    # Look for star ratings within this subtitle item
                    stars = item_elem.find_elements(By.XPATH,
                                                    ".//*[contains(@class, 'star') or contains(@class, 'rating')]")

                    # Count filled stars
                    filled_stars = len([s for s in stars if
                                        'filled' in s.get_attribute('class').lower() or 'full' in s.get_attribute(
                                            'class').lower()])

                    if filled_stars > best_rating:
                        best_rating = filled_stars
                        best_subtitle = item_elem

                    logger.debug(f"Subtitle {idx + 1}: {filled_stars} stars")

                except Exception as e:
                    logger.debug(f"Could not get rating for subtitle {idx + 1}: {e}")

            # If we couldn't find ratings, just select the first one
            if not best_subtitle and subtitle_items:
                logger.info("No ratings found, selecting first subtitle")
                best_subtitle = subtitle_items[0]
                best_rating = 0

            if not best_subtitle:
                logger.error("Could not select a subtitle")
                self.download_report.append(DownloadedSubtitle(
                    media_title=item_name,
                    media_type=media_type,
                    language="en",
                    rating="N/A",
                    plex_url=plex_item_url,
                    success=False,
                    error="Could not select subtitle"
                ))
                return False

            logger.info(f"Selecting subtitle with {best_rating} stars")

            # Click the best subtitle (or find download button within it)
            try:
                download_button = best_subtitle.find_element(By.XPATH,
                                                             ".//button[contains(text(), 'Download') or contains(@aria-label, 'Download')]")
                download_button.click()
            except:
                # If no explicit download button, click the subtitle item itself
                best_subtitle.click()

            time.sleep(2)

            logger.info(f"✓ Successfully downloaded subtitle for {item_name}")

            self.download_report.append(DownloadedSubtitle(
                media_title=item_name,
                media_type=media_type,
                language="en",
                rating=f"{best_rating} stars",
                plex_url=plex_item_url,
                success=True
            ))

            return True

        except Exception as e:
            logger.error(f"✗ Failed to download subtitle: {e}")
            self.download_report.append(DownloadedSubtitle(
                media_title=item_name,
                media_type=media_type,
                language="en",
                rating="N/A",
                plex_url=plex_item_url,
                success=False,
                error=str(e)
            ))
            return False

    def process_library(
            self,
            library_name: str,
            media_type: str = None,
            max_downloads: int = None
    ):
        """
        Process a Plex library and download missing subtitles.

        Args:
            library_name: Name of the Plex library
            media_type: Filter by 'movie' or 'episode'
            max_downloads: Maximum number of subtitles to download
        """
        try:
            library = self.plex.library.section(library_name)
        except Exception as e:
            logger.error(f"Could not find library '{library_name}': {e}")
            return

        logger.info(f"\n{'=' * 60}")
        logger.info(f"Processing library: {library_name}")
        if max_downloads:
            logger.info(f"Max downloads: {max_downloads}")
        logger.info(f"{'=' * 60}\n")

        # Get items
        items = []
        if media_type == 'movie' or library.type == 'movie':
            items = library.all()
        elif media_type == 'episode' or library.type == 'show':
            for show in library.all():
                for episode in show.episodes():
                    items.append(episode)

        logger.info(f"Found {len(items)} items to scan")

        # Set up Selenium
        self.setup_driver()
        self.login_to_plex()

        downloaded_count = 0

        try:
            for i, item in enumerate(items, 1):
                # Check download limit
                if max_downloads and downloaded_count >= max_downloads:
                    logger.info(f"\nReached download limit of {max_downloads}")
                    break

                # Check if needs subtitles
                missing = self.needs_subtitles(item)
                if not missing:
                    logger.debug(f"[{i}/{len(items)}] Skipping {item.title} - has subtitles")
                    continue

                # Generate Plex URL
                plex_url = f"{self.plex_url}/web/index.html#!/server/{self.plex.machineIdentifier}/details?key=/library/metadata/{item.ratingKey}"

                # Download subtitle
                logger.info(f"\n[{i}/{len(items)}] Needs subtitles")
                if self.download_subtitle_for_item(item, plex_url):
                    downloaded_count += 1

                # Small delay between items
                time.sleep(2)

        finally:
            # Close browser
            if self.driver:
                logger.info("\nClosing browser...")
                self.driver.quit()

        logger.info(f"\n{'=' * 60}")
        logger.info(f"Summary:")
        logger.info(f"  Total items scanned: {len(items)}")
        logger.info(f"  Subtitles downloaded: {downloaded_count}")
        logger.info(f"{'=' * 60}")

    def generate_report(self) -> str:
        """Generate a detailed report of downloaded subtitles."""
        if not self.download_report:
            return "No subtitles were processed."

        successful = [s for s in self.download_report if s.success]
        failed = [s for s in self.download_report if not s.success]

        report_lines = [
            "\n" + "=" * 80,
            "SUBTITLE DOWNLOAD REPORT (SELENIUM)",
            "=" * 80,
            f"Total processed: {len(self.download_report)}",
            f"Successful: {len(successful)}",
            f"Failed: {len(failed)}",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 80,
            ""
        ]

        if successful:
            report_lines.append(f"\nSUCCESSFUL DOWNLOADS ({len(successful)})")
            report_lines.append("-" * 80)
            for sub in successful:
                report_lines.append(f"\n{sub.media_title}")
                report_lines.append(f"  Type: {sub.media_type}")
                report_lines.append(f"  Rating: {sub.rating}")
                report_lines.append(f"  Timestamp: {sub.timestamp}")

        if failed:
            report_lines.append(f"\n\nFAILED DOWNLOADS ({len(failed)})")
            report_lines.append("-" * 80)
            for sub in failed:
                report_lines.append(f"\n{sub.media_title}")
                report_lines.append(f"  Type: {sub.media_type}")
                report_lines.append(f"  Error: {sub.error}")
                report_lines.append(f"  URL: {sub.plex_url}")

        report_lines.append("\n" + "=" * 80)

        return "\n".join(report_lines)

    def save_report(self, output_file: str = "selenium_download_report.txt"):
        """Save report to file."""
        report = self.generate_report()
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report)
        logger.info(f"\nReport saved to: {output_file}")

    def list_missing_subtitles(self, library_name: str, media_type: str = None):
        """
        List all items missing subtitles without downloading.

        Args:
            library_name: Library name to scan
            media_type: Filter by 'movie' or 'episode'

        Returns:
            List of items missing subtitles
        """
        try:
            library = self.plex.library.section(library_name)
        except Exception as e:
            logger.error(f"Could not find library '{library_name}': {e}")
            return []

        logger.info(f"\nScanning library: {library_name}")
        logger.info(f"{'=' * 60}")

        # Get items
        items = []
        if media_type == 'movie' or library.type == 'movie':
            items = library.all()
        elif media_type == 'episode' or library.type == 'show':
            for show in library.all():
                for episode in show.episodes():
                    items.append(episode)

        logger.info(f"Scanning {len(items)} items...")

        missing_items = []

        for item in items:
            missing = self.needs_subtitles(item)
            if missing:
                item_name = item.title
                if isinstance(item, Episode):
                    item_name = f"{item.grandparentTitle} - S{item.seasonNumber:02d}E{item.index:02d} - {item.title}"

                plex_url = f"{self.plex_url}/web/index.html#!/server/{self.plex.machineIdentifier}/details?key=/library/metadata/{item.ratingKey}"

                missing_items.append({
                    'title': item_name,
                    'type': 'episode' if isinstance(item, Episode) else 'movie',
                    'missing_languages': list(missing),
                    'url': plex_url,
                    'item': item
                })

        return missing_items

    def print_missing_list(self, missing_items: list):
        """Print formatted list of missing items."""
        print("\n" + "=" * 80)
        print("ITEMS MISSING SUBTITLES")
        print("=" * 80)
        print(f"Total items missing subtitles: {len(missing_items)}")
        print("=" * 80)

        movies = [item for item in missing_items if item['type'] == 'movie']
        episodes = [item for item in missing_items if item['type'] == 'episode']

        if movies:
            print(f"\nMOVIES ({len(movies)} items)")
            print("-" * 80)
            for idx, item in enumerate(movies, 1):
                print(f"\n{idx}. {item['title']}")
                print(f"   Missing: {', '.join(item['missing_languages']).upper()}")
                print(f"   URL: {item['url']}")

        if episodes:
            print(f"\n\nTV EPISODES ({len(episodes)} items)")
            print("-" * 80)
            for idx, item in enumerate(episodes, 1):
                print(f"\n{idx}. {item['title']}")
                print(f"   Missing: {', '.join(item['missing_languages']).upper()}")
                print(f"   URL: {item['url']}")

        print("\n" + "=" * 80)
        if missing_items:
            print("\nTo download these subtitles, run:")
            print("  python selenium_downloader.py --library \"<name>\" --max-downloads <number>")
        print()


def main():
    parser = argparse.ArgumentParser(
        description='Download missing Plex subtitles using Selenium UI automation'
    )
    parser.add_argument(
        '--list-missing',
        action='store_true',
        help='List items missing subtitles without downloading'
    )
    parser.add_argument(
        '--plex-url',
        default=os.getenv('PLEX_URL', 'http://localhost:32400'),
        help='Plex server URL'
    )
    parser.add_argument(
        '--plex-token',
        default=os.getenv('PLEX_TOKEN'),
        help='Plex authentication token'
    )
    parser.add_argument(
        '--languages',
        nargs='+',
        default=os.getenv('SUBTITLE_LANGUAGES', 'en').split(','),
        help='Language codes to download'
    )
    parser.add_argument(
        '--library',
        required=True,
        help='Library name to process'
    )
    parser.add_argument(
        '--type',
        choices=['movie', 'episode'],
        help='Filter by media type'
    )
    parser.add_argument(
        '--max-downloads',
        type=int,
        help='Maximum number of subtitles to download'
    )
    parser.add_argument(
        '--headless',
        action='store_true',
        help='Run browser in headless mode (no GUI)'
    )
    parser.add_argument(
        '--report',
        default='selenium_download_report.txt',
        help='Output file for report'
    )

    args = parser.parse_args()

    # Validate
    if not args.plex_token:
        logger.error("PLEX_TOKEN is required")
        sys.exit(1)

    try:
        downloader = PlexSeleniumDownloader(
            plex_url=args.plex_url,
            plex_token=args.plex_token,
            languages=args.languages,
            headless=args.headless
        )

        # If --list-missing, just list and exit
        if args.list_missing:
            missing_items = downloader.list_missing_subtitles(
                library_name=args.library,
                media_type=args.type
            )
            downloader.print_missing_list(missing_items)

            # Save to file
            with open('missing_subtitles_list.txt', 'w', encoding='utf-8') as f:
                import io
                from contextlib import redirect_stdout

                output = io.StringIO()
                with redirect_stdout(output):
                    downloader.print_missing_list(missing_items)

                f.write(output.getvalue())

            logger.info("List saved to: missing_subtitles_list.txt")
            sys.exit(0)

        # Otherwise, download subtitles
        downloader.process_library(
            library_name=args.library,
            media_type=args.type,
            max_downloads=args.max_downloads
        )

        # Generate and save report
        print(downloader.generate_report())
        downloader.save_report(args.report)

    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
        if hasattr(downloader, 'driver') and downloader.driver:
            downloader.driver.quit()
        sys.exit(0)
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()