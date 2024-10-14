"""Takes release data in JSON format, parses the tracks inside each release,
and excludes certain tracks that are not usefull for cliques. The release file
shoul be cleaned with clean_releases_for_versioning.py before using this script."""

import os
import re
import sys
import json
import time
import argparse

from variables import (
    WRITTEN,
    FEAT,
    EXCLUDE_ARTISTS,
    EXCLUDE_TITLES,
    N_MAX_ARTISTS,
)

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from utilities.utils import hard_clean_text, clean_parentheses


def remove_disogs_pattern(artist):
    """Removes the Discogs pattern from the artist name. 'Oguz (3)' type of Discogs convention"""
    return re.sub(r"\s\(\d+?\)", "", artist)


def fix_artists(t_artists, t_feat_artists):
    """Fixes the artists and feat artists lists by removing intersections and making
    them disjoint."""

    # Find the intersection between the track artists and the feat artists
    t_artists_set = set(t_artists)
    t_feat_artists_set = set(t_feat_artists)
    intersection = t_artists_set.intersection(t_feat_artists_set)

    # Remove feat artists from the track artists
    if intersection != set():
        if t_artists_set.issubset(t_feat_artists_set):
            t_feat_artists = [a for a in t_feat_artists if a not in intersection]
        else:
            t_artists = [a for a in t_artists if a not in intersection]
    return t_artists, t_feat_artists


# TODO: what if release artist is EXCLUDE_ARTIST?
def format_tracks(release, all_artist_ids):
    """Takes a release and parses its tracks. The metadata is put in a format
    for finding clique and version relationships."""

    # Collect release artist ids and names
    r_artist_ids, r_artist_names = [], []
    for ra in release["artists"]:
        r_artist_ids.append(ra["id"])
        r_artist_names.append(ra["name"])

    # Collect release writer ids and names
    # clean_releases_for_versioning.py already cleaned up the roles
    r_writer_ids, r_writer_names = [], []
    r_feat_ids, r_feat_names = [], []
    for rea in release["extraartists"]:
        role = rea["role"].lower()
        if WRITTEN in role:
            r_writer_ids.append(rea["id"])
            r_writer_names.append(remove_disogs_pattern(rea["name"]))
        else:
            for f in FEAT:
                if f in role:
                    r_feat_ids.append(rea["id"])
                    r_feat_names.append(rea["name"])
                    break

    # Clean up the artists and feat artists, remove intersections
    r_artist_ids, r_feat_ids = fix_artists(r_artist_ids, r_feat_ids)
    r_artist_names, r_feat_names = fix_artists(r_artist_names, r_feat_names)

    # Remove the Discogs pattern from the artist names
    r_artist_names = [remove_disogs_pattern(a) for a in r_artist_names]
    r_feat_names = [remove_disogs_pattern(a) for a in r_feat_names]

    # For each track, collect information
    tracks = []
    for t in release["tracklist"]:
        assert len(t["extraartists"]) > 0, "No extraartists left in track."

        # Skip tracks with no title
        if t["title"] == "":
            continue

        # Exclude tracks with certain titles
        if t["title"].lower() in EXCLUDE_TITLES:
            continue

        # Clean the title for comparison
        clean_title = clean_parentheses(t["title"])
        clean_title = hard_clean_text(clean_title)

        # Collect track artist ids and names, if provided
        t_artist_ids, t_artist_names = [], []
        if "artists" in t:
            for ta in t["artists"]:
                t_artist_ids.append(ta["id"])
                t_artist_names.append(ta["name"])
        # Skip tracks with generic artists
        if len(set(t_artist_ids).intersection(EXCLUDE_ARTISTS)) > 0:
            continue
        # Skip tracks with artists that are not in the artist file
        if len(set(t_artist_ids).difference(all_artist_ids)) > 0:
            continue

        # Classify track extraartists as writers or features
        # clean_releases.py already cleaned up the roles
        t_writer_ids, t_writer_names = [], []
        t_feat_ids, t_feat_names = [], []
        for tea in t["extraartists"]:
            role = tea["role"].lower()
            if WRITTEN in role:
                t_writer_ids.append(tea["id"])
                t_writer_names.append(remove_disogs_pattern(tea["name"]))
            else:
                for f in FEAT:
                    if f in role:
                        t_feat_ids.append(tea["id"])
                        t_feat_names.append(tea["name"])
                        break
        # Skip tracks with generic artists
        if len(EXCLUDE_ARTISTS.intersection(set(t_writer_ids))) > 0:
            continue
        if len(EXCLUDE_ARTISTS.intersection(set(t_feat_ids))) > 0:
            continue
        # Skip tracks with artists that are not in the artist file
        if len(set(t_feat_ids).difference(all_artist_ids)) > 0:
            continue

        # Clean up the artists and feat artists, remove intersections
        t_artist_ids, t_feat_ids = fix_artists(t_artist_ids, t_feat_ids)
        t_artist_names, t_feat_names = fix_artists(t_artist_names, t_feat_names)

        # Keep only tracks with up to N_MAX_ARTISTS artists for Youtube search
        if len(t_artist_ids) > N_MAX_ARTISTS or len(t_feat_ids) > N_MAX_ARTISTS:
            continue

        # Remove the Discogs pattern from the track artist names
        t_artist_names = [remove_disogs_pattern(a) for a in t_artist_names]
        t_feat_names = [remove_disogs_pattern(a) for a in t_feat_names]

        # Put the track in the required format and append to tracks
        tracks.append(
            {
                "track_title": t["title"],
                "release_title": release["title"],
                "track_writer_ids": t_writer_ids,
                "track_writer_names": t_writer_names,
                "track_artist_ids": t_artist_ids,
                "track_artist_names": t_artist_names,
                "track_feat_ids": t_feat_ids,
                "track_feat_names": t_feat_names,
                "release_id": release["id"],
                "release_artist_ids": r_artist_ids,
                "release_artist_names": r_artist_names,
                "release_writer_ids": r_writer_ids,
                "release_writer_names": r_writer_names,
                "release_feat_ids": r_feat_ids,
                "release_feat_names": r_feat_names,
                "release_genres": release["genres"],
                "release_styles": release["styles"],
                "country": release["country"],
                "labels": release["labels"],
                "formats": release["formats"],
                "master_id": release["master_id"],
                "main_release": release["main_release"],
                "release_videos": release["videos"],
                "released": release["released"],
                "track_title_cleaned": clean_title,
            }
        )

    return tracks


def main(input_json, artists_json, output_json=None):
    """Use the clean json file containing releases. Parses the tracks inside
    the releases and excludes certain tracks that are not usefull for cliques."""

    # Determine the output path if not provided
    if not output_json:
        output_json = input_json + ".tracks"
        print(f"Tracks will be saved to: {output_json}")
    # Create the parent directory if it does not exist
    output_dir = os.path.dirname(output_json)
    if output_dir != "":
        os.makedirs(output_dir, exist_ok=True)

    # Ask the user whether to delete the existing file
    if os.path.isfile(output_json):
        if input(f"{output_json} exists. Remove?[Y/n] ") == "n":
            output_json = input(f"New .json path?\n")

    # Load all the artist ids from the json file
    print("Loading all artist ids...")
    all_artist_ids = set()
    with open(artists_json, encoding="utf-8") as infile:
        for jsonline in infile:
            # Load the artist information
            artist_dict = json.loads(jsonline)
            # Add the artist's ID to the set of artists with releases
            all_artist_ids.update({artist_dict["id"]})

    # Search each track inside each release for certain information
    print("Parsing releases to tracks and filtering tracks with certain metadata...")
    t0 = time.monotonic()
    r_total, r_success, t_total = 0, 0, 0
    with open(input_json, encoding="utf-8") as in_f, open(
        output_json, "w", encoding="utf-8"
    ) as out_f:
        for jsonline in in_f:
            # Load the release
            release = json.loads(jsonline)
            # Put the tracks in the required format
            tracks = format_tracks(release, all_artist_ids)
            # If there are tracks, write them to the output file as json lines
            if len(tracks) > 0:
                t_total += len(tracks)
                r_success += 1
                # Write each track to a separate json line
                for track in tracks:
                    out_f.write(json.dumps(track, ensure_ascii=False) + "\n")
            r_total += 1
            if not r_total % 500000:
                print(f"Parsed {r_total:>9,} releases.")
    print(f"Parsed {r_total:>9,} releases to {t_total:>9,} tracks.")
    print(
        f"Processing time: {time.strftime('%M:%S', time.gmtime(time.monotonic()-t0))}"
    )


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "input_json",
        type=str,
        help="Input line-delimited JSON file with clean metadata.",
    )
    parser.add_argument(
        "artists_json", type=str, help="Parsed artists.json.clean file."
    )
    parser.add_argument(
        "--output-json",
        "-o",
        type=str,
        default=None,
        help="Output line-delimited JSON file with writer information."
        " Leave empty for automatically determining the path.",
    )
    args = parser.parse_args()

    # Read the input json, process and write to output_json
    main(args.input_json, args.artists_json, args.output_json)

    #############
    print("Done!")
