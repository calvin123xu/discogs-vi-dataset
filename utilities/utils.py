import re
import unicodedata
import unidecode

##################################### Artist Relations #####################################


def collect_all_related_artists(total_artist_ids, artist_id, artists_dict):
    """Collects all the artist ids related to a given artist id. It includes
    the artist's aliases, the aliases of the artist's members, and the aliases
    of the artist's members. It also includes the members of the artist and
    the aliases of each member."""

    # Include the artist ID
    total_artist_ids.update({artist_id})

    # Some artists are not in the artist dictionary so we can
    # not get more information about them
    if artist_id in artists_dict:
        # Get the artist's information
        artist = artists_dict[artist_id]

        # Include the artist's aliases
        artist_aliases = artist.get("aliases", [])
        total_artist_ids.update(artist_aliases)

        # More information about the artist's aliases
        for alias_id in artist_aliases:
            # If an alias is a group, include its members
            alias_members = artists_dict[alias_id].get("members", [])
            total_artist_ids.update(alias_members)
            # and the aliases of each member
            for member_id in alias_members:
                total_artist_ids.update(artists_dict[member_id].get("aliases", []))

        # If the artist is a group add its members
        members = artist.get("members", [])
        total_artist_ids.update(members)

        # and the aliases of each member
        for member_id in members:
            total_artist_ids.update(artists_dict[member_id].get("aliases", []))
            # we make sure that members can not have members

        # If the artist has name variations, include them
        if "namevariations_id" in artist:
            namevar_ids = set(artist["namevariations_id"])
            total_artist_ids.update(namevar_ids)
            for namevar_id in namevar_ids:
                total_artist_ids.update(artists_dict[namevar_id].get("aliases", []))


def collect_performance_artists(track, artists_dict):
    """Collects all the relevant artist ids for a track or a list of tracks.
    If for a given track, artist_ids are not available, it uses the release
    artist_ids instead. It also includes the track featured artists if available.
    Using this set of artist_ids, it collects the IDs for the artists and
    their aliases. If an artist is a group, it also includes each member and
    their aliases."""

    # If a single track is given get its artists
    if type(track) is dict:
        # Determine which ID to use
        if track["track_artist_ids"] != []:
            ids = set(track["track_artist_ids"])
        else:
            ids = set(track["release_artist_ids"])
        # Include the featured artists
        ids.update(set(track["track_feat_ids"]))

        # Collect the IDs for all artists, their aliases and group members
        artist_ids = set()
        for id in ids:
            # Get the related artist ids
            collect_all_related_artists(artist_ids, id, artists_dict)
        return artist_ids

    # If a list of tracks is given, collect the artists for each track
    elif type(track) is list:
        artist_ids = set()
        for t in track:
            artist_ids.update(collect_performance_artists(t, artists_dict))
        return artist_ids
    else:
        raise TypeError(
            f"track must be a dict or a list of dicts, \
                        not {type(track)}"
        )


def collect_writer_artists(track, artists_dict):
    """Collects all the relevant writer artist ids for a track or a list of tracks.
    Using this set of artist_ids, it collects the IDs for the artists and
    their aliases. If an artist is a group, it also includes each member and
    their aliases."""

    # If a single track is given get its artists
    if type(track) is dict:
        ids = set(track["track_writer_ids"])

        # Collect the IDs for all artists, their aliases and group members
        artist_ids = set()
        for id in ids:
            # Get the related artist ids
            collect_all_related_artists(artist_ids, id, artists_dict)
        return artist_ids

    # If a list of tracks is given, collect the artists for each track
    elif type(track) is list:
        artist_ids = set()
        for t in track:
            artist_ids.update(collect_writer_artists(t, artists_dict))
        return artist_ids
    else:
        raise TypeError(
            f"track must be a dict or a list of dicts, \
                        not {type(track)}"
        )


##################################### Text Cleaning Methods #####################################


def is_latin_character(char):
    # Unicode ranges for Basic Latin and Latin-1 Supplement, Latin Extended-A, and more.
    # This covers the basic alphabet and extended characters with diacritics.
    latin_ranges = [
        (0x0041, 0x005A),  # Basic Latin uppercase A-Z
        (0x0061, 0x007A),  # Basic Latin lowercase a-z
        (0x00C0, 0x00D6),  # Latin-1 Supplement uppercase A-O with diacritics
        (
            0x00D8,
            0x00F6,
        ),  # Latin-1 Supplement uppercase O with diacritics and lowercase o-y
        (0x00F8, 0x00FF),  # Latin-1 Supplement lowercase o-y with diacritics
        (0x0100, 0x017F),  # Latin Extended-A
        (0x0180, 0x024F),  # Latin Extended-B
        # Additional ranges can be added for Latin Extended Additional, etc.
    ]

    code_point = ord(char)  # Get the Unicode code point of the character

    # Check if the character falls within any of the Latin ranges
    for start, end in latin_ranges:
        if start <= code_point <= end:
            return True

    # If the character does not fall within any range, it's not considered Latin
    return False


def remove_latin_diacritics(text):
    """Removes diacritics from Latin characters but do not alter other characters.
    Returns the text without diacritics."""

    result = []
    for char in text:
        # If the character is a Latin letter with a diacritic, remove the diacritic
        if unicodedata.category(char).startswith("L") and is_latin_character(char):
            char = unidecode.unidecode(char)
        result.append(char)
    return "".join(result)


def clean_parentheses(text):

    # Remove all parentheses and their content
    text = re.sub(r"\s\(.*?\)\Z", "", text)

    return text


def hard_clean_text(text):
    """Cleans the text from unnecessary information. Returns the cleaned text."""

    # Lowercase the text
    text = text.lower()

    # Remove the leading "the", "A", and "an" from the text
    text = re.sub(r"\A(the|a|an)\s", "", text)

    # Replace & with and
    text = re.sub(r"\s&\s", " and ", text)

    # Remove all punctuation
    text = re.sub(r"[^\w\s]", "", text)

    # Multiple spaces
    text = re.sub(r"\s{2,}", " ", text)
    # Trailing spaces
    text = re.sub(r"\s\Z", "", text)
    # Leading spaces
    text = re.sub(r"\A\s", "", text)

    # Remove diacritics from Latin characters
    text = remove_latin_diacritics(text)

    return text


def soft_clean_text(text):
    """Cleans the text from unnecessary information. Returns the cleaned text."""

    # Lowercase the text
    text = text.lower()

    # Remove the leading "the", "A", and "an" from the text
    text = re.sub(r"\A(the|a|an)\s", "", text)

    # Replace & with and
    text = re.sub(r"\s&\s", " and ", text)

    result = []
    for char in text:
        category = unicodedata.category(char)
        if category.startswith("L"):  # Check if it's a letter
            if is_latin_character(char):
                decoded = unidecode.unidecode(char)
                result.append(decoded)
            else:
                # We do not process the non-latin characters
                result.append(char)
        elif category.startswith("P"):  # Punctuation
            # Simplify the punctuation
            # Replace all dashes with a single dash
            char = re.sub(r"[―－‐‑‒–—﹘﹘﹣⁃]", "-", char)
            # Replace all quotes with a single quote
            char = re.sub(r'["‘’“”‚„‛‟]', "'", char)
            result.append(char)
        else:
            result.append(char)
        # else: # Remove
        #     continue # TODO ??
    return "".join(result)
