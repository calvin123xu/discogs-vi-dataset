import re
import json
from collections import Counter

######################################### Path Functions #########################################


def get_youtube_id(url):
    return url.split("/watch?v=")[1]


def get_youtube_url(yt_id):
    return f"https://www.youtube.com/watch?v={yt_id}"


####################################### Metadata Cleaning #######################################

# These are the youtube metadata keys that we are interested in
KEYS = [
    "id",
    "title",
    "description",
    "uploader",
    "channel",
    "uploader_id",
    "channel_id",
    "duration",
    "categories",
    "tags",
    "creator",
    "alt_title",
    "track",
    "artist",
    "album",
    "release_date",
    "release_year",
    "view_count",
]


def select_fields(metadata: dict):
    return {k: metadata[k] for k in KEYS if k in metadata and metadata[k] != None}


########################################## Misc #########################################


def escape_ansi(line):
    ansi_escape = re.compile(r"(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]")
    return ansi_escape.sub("", line)


def seconds_to_dhms(seconds):
    # Calculate days, hours, minutes, and seconds
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    # Format into a string
    formatted_time = (
        f"{days} days, {hours} hours, {minutes} minutes, {seconds:.1f} seconds"
    )

    return formatted_time


########################################## Statistics ##########################################


def count_version_video_matches(videos_json):
    """Creates statistics."""

    print("Counting version video matches...")
    all_urls, release_matched, query_matched = set(), set(), set()
    total_v_matches, total_c_matches = 0, 0
    c2_matches, c3_matches, c4_matches, c5_matches = 0, 0, 0, 0
    match_type_counter = Counter()
    with open(videos_json, "r", encoding="utf-8") as in_f:
        for jsonline in in_f:
            clique = json.loads(jsonline)
            clique_yt_ids = set()  # Collect unique YT ids for this clique
            clique_v_counter = 0  # Version counter for this clique
            for version in clique["versions"]:
                # Version has been matched to at least one url
                if len(version["youtube_video"]) > 0:
                    clique_v_counter += (
                        1  # Version has been matched to at least one url
                    )
                _best_match = 100000
                for video in version["youtube_video"]:
                    clique_yt_ids.update({video["url"]})
                    # Record the source of the match
                    if video["source"] == "youtube_query":
                        query_matched.update({video["url"]})
                    elif video["source"] == "release_video":
                        release_matched.update({video["url"]})
                    if int(video["match_type"]) < _best_match:
                        _best_match = int(video["match_type"])
                match_type_counter[_best_match] += 1
            # Cliques with at least 2 or 3 versions matched to at least one url
            if clique_v_counter >= 2:
                c2_matches += 1
            if clique_v_counter >= 3:
                c3_matches += 1
            if clique_v_counter >= 4:
                c4_matches += 1
            if clique_v_counter >= 5:
                c5_matches += 1
            # All versions of this clique have a match
            if len(clique["versions"]) == clique_v_counter:
                total_c_matches += 1
            # Collect all unique urls
            all_urls.update(clique_yt_ids)
            # Total number of versions matched to a url
            total_v_matches += clique_v_counter
    unique_t_matches = len(all_urls)
    match_type_counter = sorted(match_type_counter.items(), key=lambda item: item[0])

    print("=" * 75)
    print(
        f"{total_v_matches:>7,} versions have at least one track matched to a Youtube URL"
    )
    print(f"{unique_t_matches:>7,} URLs are unique")
    print(f"{len(query_matched):>7,} URLs are found using the Youtube API")
    print(
        f"{len(release_matched):>7,} URLs are found using the release videos metadata"
    )
    print(
        f"{len(query_matched.intersection(release_matched)):>7,} URLs are found using both methods"
    )
    print(
        f"{c2_matches:>7,} cliques have minimum 2 versions matched to at least one Youtube URL"
    )
    print(
        f"{c3_matches:>7,} cliques have minimum 3 versions matched to at least one Youtube URL"
    )
    print(
        f"{c4_matches:>7,} cliques have minimum 4 versions matched to at least one Youtube URL"
    )
    print(
        f"{c5_matches:>7,} cliques have minimum 5 versions matched to at least one Youtube URL"
    )
    print(
        f"{total_c_matches:>7,} cliques have all versions matched to at least one Youtube URL"
    )
    print("=" * 75)
    print("Match type distribution (Counts the best match only)")
    for k, v in match_type_counter:
        print(f"{k:>2}: {v:>7,}")
    print("=" * 75)
