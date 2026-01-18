#!/usr/bin/env python3
"""
Plex Tools - Library Analysis Utilities

Provides tools for analyzing your Plex library including:
- Listing items missing subtitles
- Library statistics
"""

import os
import sys
import argparse
import logging
from typing import List, Set
from dotenv import load_dotenv

from plexapi.server import PlexServer
from plexapi.video import Movie, Episode

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PlexTools:
    """Tools for analyzing Plex libraries."""

    def __init__(self, plex_url: str, plex_token: str):
        """
        Initialize Plex Tools.

        Args:
            plex_url: Plex server URL
            plex_token: Plex authentication token
        """
        self.plex = PlexServer(plex_url, plex_token)

        logger.info(f"Connected to Plex server: {self.plex.friendlyName}")

    def get_system_info(self):
        """Get comprehensive system information about the Plex server."""
        import platform
        import psutil
        from datetime import datetime

        system_info = {}

        # Basic system info
        system_info['hostname'] = platform.node()
        system_info['os'] = platform.system()
        system_info['os_version'] = platform.release()
        system_info['architecture'] = platform.machine()
        system_info['python_version'] = platform.python_version()

        # CPU Information
        system_info['cpu_physical_cores'] = psutil.cpu_count(logical=False)
        system_info['cpu_logical_cores'] = psutil.cpu_count(logical=True)
        system_info['cpu_usage_percent'] = psutil.cpu_percent(interval=1, percpu=False)
        system_info['cpu_usage_per_core'] = psutil.cpu_percent(interval=1, percpu=True)

        try:
            cpu_freq = psutil.cpu_freq()
            if cpu_freq:
                system_info['cpu_freq_current'] = cpu_freq.current
                system_info['cpu_freq_min'] = cpu_freq.min
                system_info['cpu_freq_max'] = cpu_freq.max
        except:
            pass

        # Memory Information
        memory = psutil.virtual_memory()
        system_info['memory_total'] = memory.total
        system_info['memory_available'] = memory.available
        system_info['memory_used'] = memory.used
        system_info['memory_percent'] = memory.percent

        # Swap Information
        swap = psutil.swap_memory()
        system_info['swap_total'] = swap.total
        system_info['swap_used'] = swap.used
        system_info['swap_percent'] = swap.percent

        # Disk Information
        system_info['disks'] = []
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                system_info['disks'].append({
                    'device': partition.device,
                    'mountpoint': partition.mountpoint,
                    'fstype': partition.fstype,
                    'total': usage.total,
                    'used': usage.used,
                    'free': usage.free,
                    'percent': usage.percent
                })
            except PermissionError:
                continue

        # Network Information
        system_info['network_interfaces'] = {}
        net_if_addrs = psutil.net_if_addrs()
        for interface_name, interface_addresses in net_if_addrs.items():
            addrs = []
            for address in interface_addresses:
                if str(address.family) == 'AddressFamily.AF_INET':
                    addrs.append({
                        'type': 'IPv4',
                        'address': address.address,
                        'netmask': address.netmask
                    })
            if addrs:
                system_info['network_interfaces'][interface_name] = addrs

        # GPU Information (if available)
        system_info['gpu_info'] = []
        try:
            import GPUtil
            gpus = GPUtil.getGPUs()
            for gpu in gpus:
                system_info['gpu_info'].append({
                    'name': gpu.name,
                    'load': gpu.load * 100,
                    'memory_total': gpu.memoryTotal,
                    'memory_used': gpu.memoryUsed,
                    'memory_free': gpu.memoryFree,
                    'temperature': gpu.temperature
                })
        except ImportError:
            system_info['gpu_info'] = None
        except Exception as e:
            logger.debug(f"Could not get GPU info: {e}")
            system_info['gpu_info'] = None

        # System uptime
        try:
            boot_time = psutil.boot_time()
            system_info['boot_time'] = datetime.fromtimestamp(boot_time).strftime("%Y-%m-%d %H:%M:%S")
            system_info['uptime_seconds'] = datetime.now().timestamp() - boot_time
        except:
            pass

        # Plex Server Info
        try:
            system_info['plex_version'] = self.plex.version
            system_info['plex_platform'] = self.plex.platform
            system_info['plex_platform_version'] = self.plex.platformVersion
            system_info['plex_friendly_name'] = self.plex.friendlyName
            system_info['plex_machine_identifier'] = self.plex.machineIdentifier
        except Exception as e:
            logger.debug(f"Could not get Plex server info: {e}")

        # Library Statistics
        system_info['libraries'] = []
        try:
            for section in self.plex.library.sections():
                lib_info = {
                    'name': section.title,
                    'type': section.type,
                }

                # Calculate total library size and item count
                total_size = 0
                items_count = 0

                if section.type == 'movie':
                    items = section.all()
                    items_count = len(items)
                    for item in items:
                        try:
                            if item.media and len(item.media) > 0:
                                if item.media[0].parts and len(item.media[0].parts) > 0:
                                    size_bytes = item.media[0].parts[0].size
                                    if size_bytes:
                                        total_size += size_bytes
                        except:
                            continue

                elif section.type == 'show':
                    # For TV shows, count episodes not shows
                    shows = section.all()
                    for show in shows:
                        try:
                            episodes = show.episodes()
                            items_count += len(episodes)
                            for episode in episodes:
                                try:
                                    if episode.media and len(episode.media) > 0:
                                        if episode.media[0].parts and len(episode.media[0].parts) > 0:
                                            size_bytes = episode.media[0].parts[0].size
                                            if size_bytes:
                                                total_size += size_bytes
                                except:
                                    continue
                        except:
                            continue

                elif section.type == 'artist':
                    # For music, count tracks not artists
                    artists = section.all()
                    for artist in artists:
                        try:
                            albums = artist.albums()
                            for album in albums:
                                try:
                                    tracks = album.tracks()
                                    items_count += len(tracks)
                                    for track in tracks:
                                        try:
                                            if track.media and len(track.media) > 0:
                                                if track.media[0].parts and len(track.media[0].parts) > 0:
                                                    size_bytes = track.media[0].parts[0].size
                                                    if size_bytes:
                                                        total_size += size_bytes
                                        except:
                                            continue
                                except:
                                    continue
                        except:
                            continue
                else:
                    # For other types, just count items
                    items = section.all()
                    items_count = len(items)
                    for item in items:
                        try:
                            if item.media and len(item.media) > 0:
                                if item.media[0].parts and len(item.media[0].parts) > 0:
                                    size_bytes = item.media[0].parts[0].size
                                    if size_bytes:
                                        total_size += size_bytes
                        except:
                            continue

                lib_info['items_count'] = items_count
                lib_info['total_size'] = total_size
                system_info['libraries'].append(lib_info)
        except Exception as e:
            logger.debug(f"Could not get library info: {e}")

        return system_info

    def print_system_info(self, system_info: dict):
        """Print formatted system information."""

        def format_bytes(bytes_value):
            """Convert bytes to human readable format."""
            for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
                if bytes_value < 1024.0:
                    return f"{bytes_value:.2f} {unit}"
                bytes_value /= 1024.0
            return f"{bytes_value:.2f} PB"

        def format_seconds(seconds):
            """Convert seconds to human readable format."""
            days = int(seconds // 86400)
            hours = int((seconds % 86400) // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{days}d {hours}h {minutes}m"

        print("\n" + "=" * 80)
        print("PLEX SERVER INFORMATION")
        print("=" * 80)

        # Plex Server Info (REMOTE)
        print("\n" + "-" * 80)
        print("REMOTE PLEX SERVER")
        print("-" * 80)
        if 'plex_friendly_name' in system_info:
            print(f"Server Name: {system_info['plex_friendly_name']}")
            print(f"Version: {system_info.get('plex_version', 'N/A')}")
            print(f"Platform: {system_info.get('plex_platform', 'N/A')} {system_info.get('plex_platform_version', '')}")
            print(f"Machine ID: {system_info.get('plex_machine_identifier', 'N/A')}")

        # Libraries (REMOTE - from Plex)
        if system_info.get('libraries'):
            print("\n" + "-" * 80)
            print("PLEX LIBRARIES (on remote server)")
            print("-" * 80)
            total_items = 0
            total_size = 0

            for lib in system_info['libraries']:
                item_type = "items"
                if lib['type'] == 'movie':
                    item_type = "movies"
                elif lib['type'] == 'show':
                    item_type = "episodes"
                elif lib['type'] == 'artist':
                    item_type = "tracks"

                print(f"\n{lib['name']} ({lib['type']})")
                print(f"  {item_type.capitalize()}: {lib['items_count']:,}")
                print(f"  Total Size: {format_bytes(lib['total_size'])}")
                total_items += lib['items_count']
                total_size += lib['total_size']

            print(f"\nTotal across all libraries:")
            print(f"  Items: {total_items:,}")
            print(f"  Size: {format_bytes(total_size)}")

        # Local system info
        print("\n" + "-" * 80)
        print("LOCAL CLIENT MACHINE (where this script is running)")
        print("-" * 80)
        print(f"Hostname: {system_info.get('hostname', 'N/A')}")
        print(f"OS: {system_info.get('os', 'N/A')} {system_info.get('os_version', '')}")
        print(f"Architecture: {system_info.get('architecture', 'N/A')}")

        print("\n" + "=" * 80)
        print("NOTE: System stats (CPU, RAM, Disk) shown above are for the LOCAL")
        print("machine running this script, NOT the remote Plex server.")
        print("Plex API does not expose remote server hardware information.")
        print("=" * 80)
        print()

    def get_media_quality(self, item) -> dict:
        """Get video quality and codec information."""
        quality_info = {
            'resolution': 'Unknown',
            'video_codec': 'Unknown',
            'audio_codec': 'Unknown',
            'width': 0,
            'height': 0
        }

        try:
            if item.media and len(item.media) > 0:
                media = item.media[0]

                # Get resolution
                if media.videoResolution:
                    quality_info['resolution'] = media.videoResolution
                elif media.width and media.height:
                    quality_info['width'] = media.width
                    quality_info['height'] = media.height
                    # Determine resolution category
                    if media.height >= 2160:
                        quality_info['resolution'] = '4K'
                    elif media.height >= 1080:
                        quality_info['resolution'] = '1080p'
                    elif media.height >= 720:
                        quality_info['resolution'] = '720p'
                    else:
                        quality_info['resolution'] = 'SD'

                # Get video codec
                if media.videoCodec:
                    quality_info['video_codec'] = media.videoCodec.upper()

                # Get audio codec
                if media.audioCodec:
                    quality_info['audio_codec'] = media.audioCodec.upper()
        except Exception as e:
            logger.debug(f"Could not get media quality: {e}")

        return quality_info

    def get_watch_info(self, item) -> dict:
        """Get watch statistics for an item."""
        watch_info = {
            'watched': False,
            'view_count': 0,
            'last_viewed_at': None
        }

        try:
            watch_info['watched'] = item.isWatched if hasattr(item, 'isWatched') else False
            watch_info['view_count'] = item.viewCount if hasattr(item, 'viewCount') else 0

            if hasattr(item, 'lastViewedAt') and item.lastViewedAt:
                watch_info['last_viewed_at'] = item.lastViewedAt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            logger.debug(f"Could not get watch info: {e}")

        return watch_info

    def analyze_library_quality(self, library_name: str) -> dict:
        """Analyze video quality and codec distribution in a library."""
        try:
            library = self.plex.library.section(library_name)
        except Exception as e:
            logger.error(f"Could not find library '{library_name}': {e}")
            return {}

        stats = {
            'resolutions': {},
            'video_codecs': {},
            'audio_codecs': {},
            'total_items': 0
        }

        # Get items
        items = []
        if library.type == 'movie':
            items = library.all()
        elif library.type == 'show':
            for show in library.all():
                items.extend(show.episodes())

        logger.info(f"Analyzing {len(items)} items for quality metrics...")

        for item in items:
            stats['total_items'] += 1
            quality = self.get_media_quality(item)

            # Count resolutions
            res = quality['resolution']
            stats['resolutions'][res] = stats['resolutions'].get(res, 0) + 1

            # Count video codecs
            vcodec = quality['video_codec']
            stats['video_codecs'][vcodec] = stats['video_codecs'].get(vcodec, 0) + 1

            # Count audio codecs
            acodec = quality['audio_codec']
            stats['audio_codecs'][acodec] = stats['audio_codecs'].get(acodec, 0) + 1

        return stats

    def analyze_library_stats(self, library_name: str) -> dict:
        """Get general statistics for a library."""
        try:
            library = self.plex.library.section(library_name)
        except Exception as e:
            logger.error(f"Could not find library '{library_name}': {e}")
            return {}

        stats = {
            'total_items': 0,
            'total_size': 0,
            'watched_count': 0,
            'unwatched_count': 0,
            'total_duration': 0,
            'by_year': {},
            'by_genre': {},
            'by_rating': {},
        }

        # Get items
        items = []
        if library.type == 'movie':
            items = library.all()
        elif library.type == 'show':
            for show in library.all():
                items.extend(show.episodes())

        logger.info(f"Analyzing {len(items)} items for statistics...")

        for item in items:
            stats['total_items'] += 1

            # Size
            filesize_bytes = 0
            try:
                if item.media and len(item.media) > 0:
                    if item.media[0].parts and len(item.media[0].parts) > 0:
                        filesize_bytes = item.media[0].parts[0].size or 0
                        stats['total_size'] += filesize_bytes
            except:
                pass

            # Watch status
            watch_info = self.get_watch_info(item)
            if watch_info['watched']:
                stats['watched_count'] += 1
            else:
                stats['unwatched_count'] += 1

            # Duration
            try:
                if hasattr(item, 'duration') and item.duration:
                    stats['total_duration'] += item.duration
            except:
                pass

            # Year (for movies and shows)
            try:
                if hasattr(item, 'year') and item.year:
                    year = str(item.year)
                    stats['by_year'][year] = stats['by_year'].get(year, 0) + 1
                elif hasattr(item, 'originallyAvailableAt') and item.originallyAvailableAt:
                    year = str(item.originallyAvailableAt.year)
                    stats['by_year'][year] = stats['by_year'].get(year, 0) + 1
            except:
                pass

            # Genres
            try:
                if hasattr(item, 'genres'):
                    for genre in item.genres:
                        genre_name = genre.tag
                        stats['by_genre'][genre_name] = stats['by_genre'].get(genre_name, 0) + 1
            except:
                pass

            # Content rating
            try:
                if hasattr(item, 'contentRating') and item.contentRating:
                    rating = item.contentRating
                    stats['by_rating'][rating] = stats['by_rating'].get(rating, 0) + 1
            except:
                pass

        return stats

    def check_library_health(self, library_name: str) -> dict:
        """Check library health and identify potential issues."""
        try:
            library = self.plex.library.section(library_name)
        except Exception as e:
            logger.error(f"Could not find library '{library_name}': {e}")
            return {}

        health = {
            'total_items': 0,
            'missing_metadata': [],
            'low_quality': [],
            'no_subtitles': [],
            'very_large_files': [],
            'never_watched': [],
        }

        # Get items
        items = []
        if library.type == 'movie':
            items = library.all()
        elif library.type == 'show':
            for show in library.all():
                items.extend(show.episodes())

        logger.info(f"Checking health for {len(items)} items...")

        for item in items:
            health['total_items'] += 1

            item_name = item.title
            if isinstance(item, Episode):
                item_name = f"{item.grandparentTitle} - S{item.seasonNumber:02d}E{item.index:02d} - {item.title}"

            # Check for missing metadata
            try:
                if not item.summary or len(item.summary.strip()) < 10:
                    health['missing_metadata'].append({
                        'title': item_name,
                        'issue': 'No summary',
                        'rating_key': item.ratingKey
                    })
                elif not hasattr(item, 'year') or not item.year:
                    health['missing_metadata'].append({
                        'title': item_name,
                        'issue': 'No year',
                        'rating_key': item.ratingKey
                    })
            except:
                pass

            # Check for low quality (SD only)
            quality = self.get_media_quality(item)
            if quality['resolution'] == 'SD':
                health['low_quality'].append({
                    'title': item_name,
                    'resolution': quality['resolution'],
                    'rating_key': item.ratingKey
                })

            # Check for missing subtitles
            subtitle_info = self.get_subtitle_info(item)
            if not subtitle_info['has_subtitles']:
                health['no_subtitles'].append({
                    'title': item_name,
                    'rating_key': item.ratingKey
                })

            # Check for very large files (>50GB)
            filesize_bytes = 0
            try:
                if item.media and len(item.media) > 0:
                    if item.media[0].parts and len(item.media[0].parts) > 0:
                        filesize_bytes = item.media[0].parts[0].size or 0
                        if filesize_bytes > 50 * 1024 * 1024 * 1024:  # 50GB
                            health['very_large_files'].append({
                                'title': item_name,
                                'size': filesize_bytes,
                                'rating_key': item.ratingKey
                            })
            except:
                pass

            # Check for never watched items
            watch_info = self.get_watch_info(item)
            if watch_info['view_count'] == 0:
                health['never_watched'].append({
                    'title': item_name,
                    'rating_key': item.ratingKey
                })

        return health

    def get_filepath(self, item) -> str:
        """Get the file path for an item."""
        try:
            if item.media and len(item.media) > 0:
                if item.media[0].parts and len(item.media[0].parts) > 0:
                    filepath = item.media[0].parts[0].file
                    if filepath:
                        return filepath
        except Exception as e:
            logger.debug(f"Could not get filepath: {e}")
        return "Unknown"

    def get_filepath(self, item) -> str:
        """Get the file path for an item."""
        try:
            if item.media and len(item.media) > 0:
                if item.media[0].parts and len(item.media[0].parts) > 0:
                    filepath = item.media[0].parts[0].file
                    if filepath:
                        return filepath
        except Exception as e:
            logger.debug(f"Could not get filepath: {e}")
        return "Unknown"

    def get_filesize(self, item) -> str:
        """Get human-readable file size for an item."""
        try:
            # Get the first media part (usually there's only one)
            if item.media and len(item.media) > 0:
                if item.media[0].parts and len(item.media[0].parts) > 0:
                    size_bytes = item.media[0].parts[0].size
                    if size_bytes:
                        # Convert to human readable
                        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                            if size_bytes < 1024.0:
                                return f"{size_bytes:.2f} {unit}"
                            size_bytes /= 1024.0
        except Exception as e:
            logger.debug(f"Could not get filesize: {e}")
        return "Unknown"

    def get_subtitle_info(self, item) -> dict:
        """Get detailed subtitle information for an item."""
        subtitle_info = {
            'has_subtitles': False,
            'languages': [],
            'count': 0,
            'streams': []
        }

        for stream in item.subtitleStreams():
            subtitle_info['has_subtitles'] = True
            subtitle_info['count'] += 1

            # Get language info
            lang_code = stream.languageCode if stream.languageCode else 'unknown'
            lang_name = stream.language if stream.language else 'Unknown'

            # Normalize language code
            if lang_code and len(lang_code) == 3:
                conversions = {'eng': 'en', 'spa': 'es', 'fra': 'fr', 'deu': 'de', 'ita': 'it', 'por': 'pt'}
                lang_code = conversions.get(lang_code.lower(), lang_code[:2])
            elif lang_code:
                lang_code = lang_code.lower()

            if lang_code not in subtitle_info['languages']:
                subtitle_info['languages'].append(lang_code)

            subtitle_info['streams'].append({
                'language': lang_name,
                'language_code': lang_code,
                'title': stream.title if hasattr(stream, 'title') and stream.title else None,
                'format': stream.codec if hasattr(stream, 'codec') else stream.format if hasattr(stream,
                                                                                                 'format') else 'srt',
                'forced': stream.forced if hasattr(stream, 'forced') else False,
                'external': getattr(stream, 'external', False)
            })

        return subtitle_info

    def list_library(self, library_name: str, media_type: str = None):
        """
        List all items in library with subtitle details.

        Args:
            library_name: Library name to scan
            media_type: Filter by 'movie' or 'episode'

        Returns:
            List of items with subtitle info
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

        library_items = []

        for item in items:
            subtitle_info = self.get_subtitle_info(item)
            filepath = self.get_filepath(item)
            filesize = self.get_filesize(item)
            quality_info = self.get_media_quality(item)
            watch_info = self.get_watch_info(item)

            item_name = item.title
            if isinstance(item, Episode):
                item_name = f"{item.grandparentTitle} - S{item.seasonNumber:02d}E{item.index:02d} - {item.title}"

            plex_url = f"{self.plex._baseurl}/web/index.html#!/server/{self.plex.machineIdentifier}/details?key=/library/metadata/{item.ratingKey}"

            library_items.append({
                'title': item_name,
                'type': 'episode' if isinstance(item, Episode) else 'movie',
                'url': plex_url,
                'rating_key': item.ratingKey,
                'filepath': filepath,
                'filesize': filesize,
                'resolution': quality_info['resolution'],
                'video_codec': quality_info['video_codec'],
                'audio_codec': quality_info['audio_codec'],
                'watched': watch_info['watched'],
                'view_count': watch_info['view_count'],
                'last_viewed': watch_info['last_viewed_at'],
                'has_subtitles': subtitle_info['has_subtitles'],
                'languages': subtitle_info['languages'],
                'subtitle_streams': subtitle_info['streams']
            })

        return library_items

    def print_library_list(self, library_items: list):
        """Print formatted list of library items with subtitle details."""
        print("\n" + "=" * 80)
        print("LIBRARY ITEMS WITH SUBTITLE DETAILS")
        print("=" * 80)
        print(f"Total items: {len(library_items)}")

        # Count items with/without subtitles
        with_subs = len([item for item in library_items if item['has_subtitles']])
        without_subs = len(library_items) - with_subs

        print(f"Items with subtitles: {with_subs}")
        print(f"Items without subtitles: {without_subs}")
        print("=" * 80)

        movies = [item for item in library_items if item['type'] == 'movie']
        episodes = [item for item in library_items if item['type'] == 'episode']

        if movies:
            print(f"\nMOVIES ({len(movies)} items)")
            print("-" * 80)
            for idx, item in enumerate(movies, 1):
                print(f"\n{idx}. {item['title']}")
                print(f"   Rating Key: {item['rating_key']}")
                print(f"   File Path: {item['filepath']}")
                print(f"   URL: {item['url']}")
                print(f"   File Size: {item['filesize']}")
                print(f"   Quality: {item['resolution']} | Video: {item['video_codec']} | Audio: {item['audio_codec']}")
                print(f"   Watched: {'✓ Yes' if item['watched'] else '✗ No'} (Views: {item['view_count']})")
                if item['last_viewed']:
                    print(f"   Last Viewed: {item['last_viewed']}")

                if item['has_subtitles']:
                    print(f"   Subtitles: YES")
                    print(
                        f"   Languages: {', '.join(set(item['languages'])).upper() if item['languages'] else 'Unknown'}")
                    print(f"   Streams:")
                    for stream in item['subtitle_streams']:
                        forced = " [FORCED]" if stream['forced'] else ""
                        title = f" - {stream['title']}" if stream['title'] else ""
                        external = " [EXTERNAL]" if stream['external'] else " [EMBEDDED]"
                        print(
                            f"     • {stream['language']} ({stream['language_code'].upper()}) - {stream['format']}{title}{forced}{external}")
                else:
                    print(f"   Subtitles: NO")

        if episodes:
            print(f"\n\nTV EPISODES ({len(episodes)} items)")
            print("-" * 80)

            # Group by show
            shows = {}
            for ep in episodes:
                show_name = ep['title'].split(' - ')[0]
                if show_name not in shows:
                    shows[show_name] = []
                shows[show_name].append(ep)

            for show_name, eps in sorted(shows.items()):
                print(f"\n{show_name} ({len(eps)} episodes)")
                for ep in sorted(eps, key=lambda x: x['title']):
                    print(f"\n  {ep['title']}")
                    print(f"    Rating Key: {ep['rating_key']}")
                    print(f"    File Path: {ep['filepath']}")
                    print(f"    URL: {ep['url']}")
                    print(f"    File Size: {ep['filesize']}")
                    print(f"    Quality: {ep['resolution']} | Video: {ep['video_codec']} | Audio: {ep['audio_codec']}")
                    print(f"    Watched: {'✓ Yes' if ep['watched'] else '✗ No'} (Views: {ep['view_count']})")

                    if ep['has_subtitles']:
                        print(f"    Subtitles: YES")
                        print(
                            f"    Languages: {', '.join(set(ep['languages'])).upper() if ep['languages'] else 'Unknown'}")
                        print(f"    Streams:")
                        for stream in ep['subtitle_streams']:
                            forced = " [FORCED]" if stream['forced'] else ""
                            title = f" - {stream['title']}" if stream['title'] else ""
                            external = " [EXTERNAL]" if stream['external'] else " [EMBEDDED]"
                            print(
                                f"      • {stream['language']} ({stream['language_code'].upper()}) - {stream['format']}{title}{forced}{external}")
                    else:
                        print(f"    Subtitles: NO")

        print("\n" + "=" * 80)
        print()

    def save_library_report(self, library_items: list, output_file: str = "library_subtitles.txt"):
        """Save the library report to a file."""
        import io
        from contextlib import redirect_stdout

        # Capture print output
        f = io.StringIO()
        with redirect_stdout(f):
            self.print_library_list(library_items)

        report = f.getvalue()

        with open(output_file, 'w', encoding='utf-8') as file:
            file.write(report)

        logger.info(f"Report saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description='Plex Info - Comprehensive Plex library analysis tool',
        epilog='''
Examples:
  # List all available libraries
  python plex_info.py

  # List all movies with details
  python plex_info.py --library "Movies"

  # Find items missing subtitles
  python plex_info.py --library "Movies" --list-missing

  # Analyze quality distribution
  python plex_info.py --library "Movies" --quality

  # Get library statistics
  python plex_info.py --library "Movies" --stats

  # Check library health
  python plex_info.py --library "Movies" --health

  # View system information
  python plex_info.py --system

For more information, see the README.md file.
        ''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--list-missing',
        action='store_true',
        help='Show only items missing subtitles'
    )
    parser.add_argument(
        '--system',
        action='store_true',
        help='Display detailed system information about the Plex server'
    )
    parser.add_argument(
        '--quality',
        action='store_true',
        help='Analyze video quality and codec distribution in the library'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show general statistics for the library (watch counts, genres, years, etc.)'
    )
    parser.add_argument(
        '--health',
        action='store_true',
        help='Check library health and identify potential issues'
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
        '--library',
        help='Library name to analyze (e.g., "Movies", "TV Shows"). If not specified, lists all libraries.'
    )
    parser.add_argument(
        '--type',
        choices=['movie', 'episode'],
        help='Filter by media type'
    )
    parser.add_argument(
        '--output',
        default='library_subtitles.txt',
        help='Output file for report (default: library_subtitles.txt)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate
    if not args.plex_token:
        logger.error("PLEX_TOKEN is required. Set it in .env or pass --plex-token")
        sys.exit(1)

    try:
        tools = PlexTools(
            plex_url=args.plex_url,
            plex_token=args.plex_token
        )

        # If --system flag, show system info and exit
        if args.system:
            logger.info("Gathering system information...")
            system_info = tools.get_system_info()
            tools.print_system_info(system_info)
            return

        # If --quality flag, analyze quality distribution
        if args.quality:
            if not args.library:
                logger.error("--library is required for --quality analysis")
                sys.exit(1)

            logger.info(f"Analyzing quality distribution for library: {args.library}")
            quality_stats = tools.analyze_library_quality(args.library)

            print("\n" + "=" * 80)
            print(f"VIDEO QUALITY ANALYSIS - {args.library}")
            print("=" * 80)

            print(f"\nTotal Items: {quality_stats['total_items']:,}")

            print("\n" + "-" * 80)
            print("RESOLUTION DISTRIBUTION")
            print("-" * 80)
            for res, count in sorted(quality_stats['resolutions'].items(), key=lambda x: x[1], reverse=True):
                percentage = (count / quality_stats['total_items'] * 100) if quality_stats['total_items'] > 0 else 0
                print(f"{res:15s}: {count:5,} ({percentage:5.1f}%)")

            print("\n" + "-" * 80)
            print("VIDEO CODEC DISTRIBUTION")
            print("-" * 80)
            for codec, count in sorted(quality_stats['video_codecs'].items(), key=lambda x: x[1], reverse=True):
                percentage = (count / quality_stats['total_items'] * 100) if quality_stats['total_items'] > 0 else 0
                print(f"{codec:15s}: {count:5,} ({percentage:5.1f}%)")

            print("\n" + "-" * 80)
            print("AUDIO CODEC DISTRIBUTION")
            print("-" * 80)
            for codec, count in sorted(quality_stats['audio_codecs'].items(), key=lambda x: x[1], reverse=True):
                percentage = (count / quality_stats['total_items'] * 100) if quality_stats['total_items'] > 0 else 0
                print(f"{codec:15s}: {count:5,} ({percentage:5.1f}%)")

            print("\n" + "=" * 80)
            print()
            return

        # If --stats flag, show general statistics
        if args.stats:
            if not args.library:
                logger.error("--library is required for --stats analysis")
                sys.exit(1)

            logger.info(f"Gathering statistics for library: {args.library}")
            stats = tools.analyze_library_stats(args.library)

            def format_bytes(bytes_value):
                for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                    if bytes_value < 1024.0:
                        return f"{bytes_value:.2f} {unit}"
                    bytes_value /= 1024.0
                return f"{bytes_value:.2f} TB"

            def format_duration(ms):
                seconds = ms / 1000
                hours = int(seconds // 3600)
                minutes = int((seconds % 3600) // 60)
                return f"{hours}h {minutes}m"

            print("\n" + "=" * 80)
            print(f"LIBRARY STATISTICS - {args.library}")
            print("=" * 80)

            print(f"\nTotal Items: {stats['total_items']:,}")
            print(f"Total Size: {format_bytes(stats['total_size'])}")
            if stats['total_duration'] > 0:
                print(f"Total Runtime: {format_duration(stats['total_duration'])}")

            print(
                f"\nWatched: {stats['watched_count']:,} ({(stats['watched_count'] / stats['total_items'] * 100 if stats['total_items'] > 0 else 0):.1f}%)")
            print(
                f"Unwatched: {stats['unwatched_count']:,} ({(stats['unwatched_count'] / stats['total_items'] * 100 if stats['total_items'] > 0 else 0):.1f}%)")

            if stats['by_year']:
                print("\n" + "-" * 80)
                print("BY YEAR (Top 10)")
                print("-" * 80)
                for year, count in sorted(stats['by_year'].items(), key=lambda x: x[1], reverse=True)[:10]:
                    print(f"{year}: {count:,}")

            if stats['by_genre']:
                print("\n" + "-" * 80)
                print("BY GENRE (Top 10)")
                print("-" * 80)
                for genre, count in sorted(stats['by_genre'].items(), key=lambda x: x[1], reverse=True)[:10]:
                    print(f"{genre:25s}: {count:,}")

            if stats['by_rating']:
                print("\n" + "-" * 80)
                print("BY CONTENT RATING")
                print("-" * 80)
                for rating, count in sorted(stats['by_rating'].items(), key=lambda x: x[1], reverse=True):
                    print(f"{rating:15s}: {count:,}")

            print("\n" + "=" * 80)
            print()
            return

        # If --health flag, check library health
        if args.health:
            if not args.library:
                logger.error("--library is required for --health check")
                sys.exit(1)

            logger.info(f"Checking health for library: {args.library}")
            health = tools.check_library_health(args.library)

            def format_bytes(bytes_value):
                for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                    if bytes_value < 1024.0:
                        return f"{bytes_value:.2f} {unit}"
                    bytes_value /= 1024.0
                return f"{bytes_value:.2f} TB"

            print("\n" + "=" * 80)
            print(f"LIBRARY HEALTH CHECK - {args.library}")
            print("=" * 80)

            print(f"\nTotal Items Scanned: {health['total_items']:,}")

            print("\n" + "-" * 80)
            print(f"MISSING METADATA: {len(health['missing_metadata'])} items")
            print("-" * 80)
            if health['missing_metadata']:
                for idx, item in enumerate(health['missing_metadata'][:10], 1):
                    print(f"{idx}. {item['title']} - Issue: {item['issue']}")
                if len(health['missing_metadata']) > 10:
                    print(f"... and {len(health['missing_metadata']) - 10} more")
            else:
                print("✓ No issues found")

            print("\n" + "-" * 80)
            print(f"LOW QUALITY (SD): {len(health['low_quality'])} items")
            print("-" * 80)
            if health['low_quality']:
                for idx, item in enumerate(health['low_quality'][:10], 1):
                    print(f"{idx}. {item['title']} - {item['resolution']}")
                if len(health['low_quality']) > 10:
                    print(f"... and {len(health['low_quality']) - 10} more")
            else:
                print("✓ No SD content found")

            print("\n" + "-" * 80)
            print(f"MISSING SUBTITLES: {len(health['no_subtitles'])} items")
            print("-" * 80)
            if health['no_subtitles']:
                for idx, item in enumerate(health['no_subtitles'][:10], 1):
                    print(f"{idx}. {item['title']}")
                if len(health['no_subtitles']) > 10:
                    print(f"... and {len(health['no_subtitles']) - 10} more")
            else:
                print("✓ All items have subtitles")

            print("\n" + "-" * 80)
            print(f"VERY LARGE FILES (>50GB): {len(health['very_large_files'])} items")
            print("-" * 80)
            if health['very_large_files']:
                for idx, item in enumerate(health['very_large_files'][:10], 1):
                    print(f"{idx}. {item['title']} - {format_bytes(item['size'])}")
                if len(health['very_large_files']) > 10:
                    print(f"... and {len(health['very_large_files']) - 10} more")
            else:
                print("✓ No files larger than 50GB")

            print("\n" + "-" * 80)
            print(f"NEVER WATCHED: {len(health['never_watched'])} items")
            print("-" * 80)
            if health['never_watched']:
                for idx, item in enumerate(health['never_watched'][:10], 1):
                    print(f"{idx}. {item['title']}")
                if len(health['never_watched']) > 10:
                    print(f"... and {len(health['never_watched']) - 10} more")
            else:
                print("✓ All items have been watched at least once")

            print("\n" + "=" * 80)
            print()
            return

        # If no library specified, list all libraries
        if not args.library:
            print("\n" + "=" * 80)
            print("AVAILABLE PLEX LIBRARIES")
            print("=" * 80)

            sections = tools.plex.library.sections()
            for section in sections:
                print(f"\n{section.title}")
                print(f"  Type: {section.type}")
                print(f"  Items: {len(section.all())}")

            print("\n" + "=" * 80)
            print("\nTo analyze a library, run:")
            print('  python plex_info.py --library "Library Name"')
            print("\nExamples:")
            print('  python plex_info.py --library "Movies"')
            print('  python plex_info.py --library "TV Shows" --list-missing')
            print('  python plex_info.py --system')
            print()
            return

        # Get library items with subtitle details
        library_items = tools.list_library(
            library_name=args.library,
            media_type=args.type
        )

        # Filter for missing only if requested
        if args.list_missing:
            library_items = [item for item in library_items if not item['has_subtitles']]
            if not library_items:
                print("\n✓ All items in the library have subtitles!\n")
                return

        # Print to console
        tools.print_library_list(library_items)

        # Save to file
        tools.save_library_report(library_items, args.output)

    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()