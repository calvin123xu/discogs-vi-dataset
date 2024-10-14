import os
import sys
import re
from itertools import permutations

sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
)
from utilities.utils import soft_clean_text

EXCLUDE_TITLES = {"full album"}

############################## Regex Functions for Youtube Metadata ##############################


ARTIST_JOIN_SYMBOLS = [",", "-", "&", "and", " "]
FEAT_START_SYMBOLS = ["featuring", "feat", "feat.", "ft.", "with", " "]
TITLE_JOIN_SYMBOLS = ["-", ":", " "]

# Create regex for joining names. Will match any single symbol, with 0 or 1 space around it
ARTIST_JOIN_PATTERN = r"\s?" + rf"({'|'.join(ARTIST_JOIN_SYMBOLS)})" + r"\s?"
FEAT_START_PATTERN = r"\s?" + rf"({'|'.join(FEAT_START_SYMBOLS)})" + r"\s?"
TITLE_JOIN_PATTERN = r"\s?" + rf"[{''.join(TITLE_JOIN_SYMBOLS)}]" + r"\s?"


def wrap_in_brackets(s):
    return r"[\[\(]?" + s + r"[\]\)]?" + r"\s?"


##################################### Cleaning Methods #####################################


def clean_uploader_name(v_uploader):
    """Cleans the uploader name (channel) from unnecessary information. Returns the cleaned
    uploader name."""

    # Uploader is a single entity not concatenated artists or channels
    v_uploader = re.sub(r"\s?-?\s?topic\Z", "", v_uploader)  # TODO: is there .topic?
    v_uploader = re.sub(r"vevo\Z", "", v_uploader)
    # v_uploader = re.sub(r"[^u][^n]official\Z", "", v_uploader) # TODO: there are unofficial channels as well
    v_uploader = re.sub(
        r"\s?[\[\(\{]?\s?(official|hq)\s?[\]\)\}]?", "", v_uploader
    )  # TODO???
    return v_uploader


def clean_video_title(v_title):
    """Cleans the video title from unnecessary information. Returns the cleaned
    video title."""

    v_title = re.sub(
        r"\s?[\[\(\{]\s?official\s?(hd)?\s?(audio|video|music)?\s?[\]\)\}]", "", v_title
    )  # TODO: official video?
    v_title = re.sub(
        r"\s?[\[\(\{]\s?official\s?(music|lyrics?|youtube)\s?video\s?[\]\)\}]",
        "",
        v_title,
    )
    v_title = re.sub(
        r"\s?[\[\(\{]\s?(explicit|uncensored|extended|clean)\s?(version)?[\]\)\}]",
        "",
        v_title,
    )
    v_title = re.sub(r"\s?[\[\(\{]\s?(lyrics?|video|audio)\s?[\]\)\}]", "", v_title)
    v_title = re.sub(
        r"\s?[\[\(\{]\s?music\s?(video|audio|lyrics?)?\s?[\]\)\}]", "", v_title
    )
    v_title = re.sub(r"\s?[\[\(\{]\s?lyrics?\s?(video|audio)?\s?[\]\)\}]", "", v_title)
    v_title = re.sub(r"\s?[\[\(\{]\s?visualizer\s?[\]\)\}]", "", v_title)
    v_title = re.sub(r"\s?[\[\(\{]\s?pseudo\s?video\s?[\]\)\}]", "", v_title)
    v_title = re.sub(r"\s?-\s?original(\s?version)?", "", v_title)

    v_title = re.sub(
        r"\s?[\[\(\{]\s?\d{0,4}\s?-?\s?remaster(ed)(\s?version)?\s?[\]\)\}]",
        "",
        v_title,
    )
    v_title = re.sub(
        r"\s?[\[\(\{]\s?remaster(ed)?(\s?version)?\s?-?\s?\d{0,4}\s?[\]\)\}]",
        "",
        v_title,
    )
    v_title = re.sub(
        r"\s?[\[\(\{]\s?remaster(ed)?\s?-?\s?\d{0,4}\s?(\s?version)?[\]\)\}]",
        "",
        v_title,
    )
    v_title = re.sub(
        r"\s?[\[\(\{]\s?remaster(ed)?\s?(in)?\s?(4k|8k)?[\]\)\}]", "", v_title
    )

    v_title = re.sub(r"\s?[\[\(\{]\s?(hq|hd)\s?[\]\)\}]", "", v_title)
    v_title = re.sub(
        r"\s?[\[\(\{]\s?(stereo|mono|original)(\s?version)?\s?[\]\)\}]", "", v_title
    )

    # Multiple spaces
    v_title = re.sub(r"\s{2,}", " ", v_title)
    # Trailing spaces
    v_title = re.sub(r"\s\Z", "", v_title)
    # Leading spaces
    v_title = re.sub(r"\A\s", "", v_title)
    return v_title


##################################### Youtube Search Algorithm #####################################


# TODO: Use feat_artist_names as normal artists too
def create_title_artist_combinations_regex(
    title: str, artist_names: list, feat_artist_names: list = []
):
    """Creates all permutations of the artist_names, joins them with the artist_join_symbols
    and joins each artist pattern with the title using the title_artist_join_symbols.
    Returns a list of compiled regexps. If feat artist names are provided, it will create
    all permutations of the feat artist names and join them with the feat_join_symbols.
    This method is designed specifically for the Youtube metadata video title and artist
    combination."""

    # Escape the special characters in the names
    title = re.escape(title)
    artist_names = [re.escape(a) for a in artist_names]
    feat_artist_names = [re.escape(a) for a in feat_artist_names]

    # Consider all permutations of the artists
    artist_perms = list(permutations(artist_names))
    artist_patterns = [ARTIST_JOIN_PATTERN.join(a) for a in artist_perms]

    # Put the feat artist names in the format
    if len(feat_artist_names) == 0:
        feat_artist_patterns = []
    elif len(feat_artist_names) == 1:
        # Create "(feat. Artist)", "[ft. Artist]", "(featuring Artist)"... patterns
        feat_artist_patterns = [
            wrap_in_brackets(FEAT_START_PATTERN + feat_artist_names[0])
        ]
    else:
        # Create all permutations of the feat artist names
        feat_artist_perms = list(permutations(feat_artist_names))
        # Create "(feat. Artist0, Artist1)", "[ft. Artist1 - Artist0]",
        #  "(featuring Artist2, Artist0 - Artist1)"...
        feat_artist_patterns = [
            wrap_in_brackets(FEAT_START_PATTERN + ARTIST_JOIN_PATTERN.join(a))
            for a in feat_artist_perms
        ]

    # Combine all information
    total_pattern = []
    if len(feat_artist_patterns) == 0:  # No featuring artist information
        # Combine each artist permutation with the title
        for artist_pattern in artist_patterns:
            p1 = re.compile(artist_pattern + TITLE_JOIN_PATTERN + title)  # X - Title
            p2 = re.compile(
                title + TITLE_JOIN_PATTERN + artist_pattern
            )  # Title - X feat Y
            total_pattern.extend([p1, p2])
    else:
        # Combine each artist permutation with the title and the feat artist permutations
        for feat_artist_pattern in feat_artist_patterns:
            p0 = re.compile(title + feat_artist_pattern)  # Title feat Y
            total_pattern.append(p0)
            for artist_pattern in artist_patterns:
                p1 = re.compile(
                    artist_pattern + feat_artist_pattern + TITLE_JOIN_PATTERN + title
                )  # X feat Y - Title
                p2 = re.compile(
                    title + TITLE_JOIN_PATTERN + artist_pattern + feat_artist_pattern
                )  # Title - X feat Y
                p3 = re.compile(
                    artist_pattern + TITLE_JOIN_PATTERN + title + feat_artist_pattern
                )  # X - Title feat Y
                total_pattern.extend([p1, p2, p3])

    return total_pattern


def prepare_track_for_query(track):
    """Prepares the track information for querying the YouTube API. Returns lowercased
    track title, track artists and featuring artists."""

    # Determine the key to use for the artist names
    if track["track_artist_names"] != []:
        key = "track_artist_names"
    else:
        key = "release_artist_names"

    # Make each artist name lowercase
    t_artists = [a.lower() for a in track[key]]
    t_feat_artists = [a.lower() for a in track["track_feat_names"]]

    # Make the track title lowercase
    t_title = track["track_title"].lower()

    return t_title, t_artists, t_feat_artists


def create_query_string(track):
    """Creates a query string from the track information. Returns the query string."""

    t_title, t_artists, t_feat_artists = prepare_track_for_query(track)

    if t_feat_artists != []:
        return f"{', '.join(t_artists)} - {t_title} (featuring {', '.join(t_feat_artists)})"
    else:
        return f"{', '.join(t_artists)} - {t_title}"


def prepare_track_for_matching(track):

    t_title, t_artists, t_feat_artists = prepare_track_for_query(track)

    t_title = soft_clean_text(t_title)
    t_artists = [soft_clean_text(artist) for artist in t_artists]
    t_feat_artists = [soft_clean_text(artist) for artist in t_feat_artists]

    return t_title, t_artists, t_feat_artists


def check_officiality(uploader, description, track_artist=None):
    """Checks if the video is official by using its metadata. Can use track
    artist information if provided. You should prepare the track metadata with
    prepare_track_for_query() before using this function.
    The function uses the following rules to determine if a video is official:
        1. If the uploader is a topic channel
        2. If the uploader is a VEVO channel
        3. If the description contains "provided to youtube by
        4. If the uploader is the same as the track artist
    NOTE: We do not use video artist because it can be unofficially uploaded.
    """

    # Topic channels are official
    if re.search(r"\s?-?\s?topic\Z", uploader):
        return True
    # VEVO channels are official
    elif re.search(r"vevo\Z", uploader):
        return True
    # Official uploads have this in the description
    elif re.search("provided to youtube by", description):
        return True
    # Uploader is the same name as the track_artist
    # NOTE: We could process the track_artist e.g. remove the space in between
    elif (track_artist is not None) and track_artist == uploader:
        return True
    # If all tests fail, it's not official
    return False
