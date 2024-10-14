"""This script contains the search algorithm used to find the official youtube ID
of a track using Discogs metadata.

The algorithm is based on the following assumptions:
"""  # TODO: update

import os
import sys

from .search_utilities import (
    EXCLUDE_TITLES,
    create_title_artist_combinations_regex,
    clean_uploader_name,
    clean_video_title,
    check_officiality,
)

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
from utilities.utils import soft_clean_text


def compare_video_metadata_with_track_metadata(
    t_title: str,
    t_artists: list,
    t_feat_artists: list,
    v_metadata: dict,
    max_minute: float = 20,
):
    """Compares the metadata of a video with the metadata of a track to determine
    if the video is the official version of the track. Returns True if it is,
    False otherwise. prepare_track_for_matching() should be used to prepare the track
    metadata for this function with the track metadata."""

    """ 1 - Filter out certain videos"""

    ################## Video Category ##################

    # Skip non-music videos
    try:
        if "Music" not in v_metadata["categories"]:
            return (False, None)
    except:
        raise Exception(f"No category information.")

    ################## Video Duration ##################

    # Skip videos longer than T minutes
    if v_metadata["duration"] > max_minute * 60:
        return (False, None)

    ################## Officiality Check ##################

    # Format some fields
    # TODO: some videos do not have uploader information
    try:
        v_uploader = soft_clean_text(v_metadata["uploader"])
    except:
        raise Exception(f"No uploader information.")

    # We do not clean the description because we use only a little part of it
    description = v_metadata["description"].lower()

    # Create a set of all the artists
    all_t_artists = set(t_artists + t_feat_artists)

    # Check if the video is official for any of the artists
    # NOTE: We only accept official videos. This will reject many videos but we
    #      can be sure that the video is official.
    any_official = any(
        [
            check_officiality(v_uploader, description, t_artist)
            for t_artist in all_t_artists
        ]
    )
    if not any_official:
        return (False, None)

    ################## Remove certain videos ##################

    # Format the video title
    v_title = soft_clean_text(v_metadata["title"])

    # Exclude videos with certain titles
    for e_title in EXCLUDE_TITLES:
        if e_title in v_title:
            return (False, None)

    """ 2 - Compare Title and Artist information"""

    # Clean the artist information if available
    v_artist = v_metadata.get("artist", None)
    if v_artist is not None:
        # Even if there are multiple artists, they are joined with a comma in a string in YT
        # TODO: some artist names include ',' which cause problems, e.g. "Grover Washington, Jr."
        v_artist = {soft_clean_text(artist) for artist in set(v_artist.split(", "))}

    # Clean the uploader name (channel)
    v_uploader = clean_uploader_name(v_uploader)

    # First check for a strict title match
    if t_title == v_title:

        # If artist information is available, use it
        if v_artist is not None:
            # If the video artists and the track artists coincide, accept it as a artist match
            # NOTE: this can be a relaxed condition, it is not a strict match may lead to losing
            # feat. versions etc. but due to how Youtube data is structured, it is the best we can
            if v_artist == all_t_artists:
                return (True, 0)
            elif v_artist.intersection(all_t_artists):
                return (True, 1)
        else:
            # If the uploader is the artist accept it as an artist match
            if {v_uploader} == all_t_artists:
                return (True, 2)
            elif v_uploader in all_t_artists:
                return (True, 3)

    elif t_title in v_title:

        # Clean the video title
        v_title = clean_video_title(v_title)

        # Check again
        if t_title == v_title:

            # Same as above
            if v_artist is not None:
                if v_artist == all_t_artists:
                    return (True, 4)
                elif v_artist.intersection(all_t_artists):
                    return (True, 5)
            else:
                if {v_uploader} == all_t_artists:
                    return (True, 6)
                elif v_uploader in all_t_artists:
                    return (True, 7)

        else:
            # TODO: due to wrong feat artist annotations and differences between YT and Discogs
            #       maybe we should look for other artists in the description
            # TODO: how to also use the aliases?
            patterns = create_title_artist_combinations_regex(
                t_title, t_artists, t_feat_artists
            )
            for pattern in patterns:
                # Compare each title-artist combination with the video title
                # NOTE: here we apply full match to reduce noise
                if pattern.fullmatch(v_title):
                    return (True, 8)  # Return the url if both match

    return (False, None)
