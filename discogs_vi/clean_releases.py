"""Cleanup the line-delimited JSON file with Discogs 'releases' dump to keep only 
metadata relevant for building the DiscoTubeVersions dataset"""

import os.path
import json
import sys
import time
import argparse

from variables import (
    WRITTEN,
    FEAT,
    EXCLUDE_ARTISTS,
    EXCLUDE_GENRES,
    N_MAX_ARTISTS,
    TAXONOMY_PATH,
)

GENRE_TREE_ERRORS = 0


def extract_style(release, genre_tree):
    # Find parent genres for styles following Discogs genre tree.
    # TODO As an alternative to following the taxonomy, we could treat
    # genres and styles independently as tags.

    # Find a parent genre among genres for each style in styles.
    global GENRE_TREE_ERRORS
    genres_styles = []
    for s in release["styles"]:
        gs = [(g, s) for g in release["genres"] if s in genre_tree[g]]
        if gs == []:
            # print('ERROR: Cannot find parent genre for style', s, 'Genres:', ', '.join(genres))
            GENRE_TREE_ERRORS += 1
        genres_styles += gs
    release["styles"] = genres_styles


def extract_year(release):
    # Extract year from the "released" field string.
    if release["released"]:
        year = [d for d in release["released"].split("-") if len(d) == 4]
        if len(year) == 1:
            release["released"] = year[0]


def extract_videos(release):
    release["videos"] = [v["url"] for v in release["videos"]]


def extract_format(release):
    release["formats"] = [f["@name"] for f in release["formats"]]


def _get_unique_artists(obj, all_ids, unique_ids):
    """obj can be a release or track dict."""

    unique_artists = []
    # For each unique id we get a corresponding artist dictionary
    for artist_id in unique_ids:
        # Search for the corresponding artist dictionary
        # This will return the first instance of the artist's appearance
        artist_indx = all_ids.index(artist_id)
        unique_artists.append(obj["artists"][artist_indx])
    return unique_artists


def _get_writers_feats(obj):
    """obj can be a release or track dict."""

    writers, feats = [], []
    for ea in obj["extraartists"]:
        # Only include extraartists with roles
        if "role" in ea:
            role = ea["role"].lower()
            # Only include roles with WRITTEN or FEAT information
            if WRITTEN in role:
                writers.append(ea)
            else:
                # Check if the role contains FEAT information
                # This can be usefull for version identification later
                # but we do not use this information for clique or version
                for f in FEAT:
                    if f in role:
                        feats.append(ea)
                        break
    return writers, feats


def _clean_writers_feats(writers, feats, all_artist_ids):
    """Removes duplicate artists from the writers and feats lists."""

    def _get_uniques(obj, unique_ids):
        """obj can be a writer or feat dict."""

        uniques = []
        for _id in unique_ids:
            # Search for the corresponding dictionary
            for dct in obj:
                if dct["id"] == _id:
                    uniques.append(dct)
                    break
        return uniques

    # Clean the writers list from duplicates
    # Some tracks have the same artist listed multiple times for each role
    # i.e. 'Written-By' and "Written-By, Producer"
    # We keep only one instance of each artist
    writers_ids = [w["id"] for w in writers]
    unique_writers_ids = set(writers_ids)
    if len(writers_ids) != len(unique_writers_ids):
        # Replace the original writers with the cleaned one
        writers = _get_uniques(writers, unique_writers_ids)

    # Clean the feats list from duplicates
    # Some tracks have the same artist listed multiple times for each role
    # i.e. 'Featuring' and "Featuring, Vocals"
    # We keep only one instance of each artist
    feats_ids = [f["id"] for f in feats]
    unique_feats_ids = set(feats_ids)
    if len(feats_ids) != len(unique_feats_ids):
        # Replace the original feats with the cleaned one
        feats = _get_uniques(feats, unique_feats_ids)

    # TODO? Remove any writer that is also listed as a feat??

    # Remove featuring artists that are excluded
    feats = [f for f in feats if f["id"] not in EXCLUDE_ARTISTS]
    # Keep featuring artists are not in the artist list
    feats = [f for f in feats if f["id"] in all_artist_ids]

    return writers, feats


def clean_release_artists_duplicates(release):
    """Removes duplicate artists from the release."""

    # Each release has a list of artists
    ra_ids = [a["id"] for a in release["artists"]]

    # See if any artist IDs are duplicates
    unique_ra_ids = set(ra_ids)
    if len(ra_ids) != len(unique_ra_ids):
        # If there are duplicates, keep only one instance of each artist
        release["artists"] = _get_unique_artists(release, ra_ids, unique_ra_ids)


def clean_tracklist_artists_duplicates(release):
    """For each track in the tracklist, if artist information is
    provided, removes duplicate artists."""

    # Clean the artists from duplicates for each track in the tracklist
    for t in release["tracklist"]:
        # Some tracks don't have artists
        # we keep these tracks as they are
        if "artists" in t:
            ta_ids = [a["id"] for a in t["artists"]]
            # See if any artist IDs are duplicates
            unique_ta_ids = set(ta_ids)
            if len(ta_ids) != len(unique_ta_ids):
                # If there are duplicates, keep only one instance of each artist
                t["artists"] = _get_unique_artists(t, ta_ids, unique_ta_ids)


def clean_release_extraartists(release, all_artist_ids):
    """On the release level, removes any extraartist role that does not
    contain 'Written-By' or 'Featuring' information. Then, removes
    duplicate artists from the remaining roles."""

    # get WRITTEN and FEAT information
    writers, feats = _get_writers_feats(release)

    # Clean the writers and feats from duplicates
    writers, feats = _clean_writers_feats(writers, feats, all_artist_ids)

    # Replace the original extraartists with the cleaned one
    release["extraartists"] = writers + feats


def clean_tracklist_extraartists(release, all_artist_ids):
    """Keeps only tracks with extraartist information. For those tracks,
    removes any extraartist role that does not contain 'Written-By' or
    'Featuring' information. If no writer information is provided for a
    track, it is deleted. Then, it removes duplicate artists from the
    remaining roles.
    """

    _tracklist = []
    for t in release["tracklist"]:
        # Add only the tracks with extraartists
        if "extraartists" not in t:
            continue

        # get WRITTEN and FEAT information
        writers, feats = _get_writers_feats(t)
        # If no writers were found, do not include the track
        if writers == []:
            continue

        # Clean the writers and feats from duplicates
        writers, feats = _clean_writers_feats(writers, feats, all_artist_ids)
        # Replace the original extraartists with the cleaned one
        t["extraartists"] = writers + feats

        # Add the track to the cleaned tracklist
        _tracklist.append(t)
    # Replace the original tracklist with the cleaned one
    release["tracklist"] = _tracklist


def clean_master_id(release):
    if "@is_main_release" in release["master_id"]:
        release["main_release"] = release["master_id"]["@is_main_release"]
        release["master_id"] = release["master_id"]["#text"]
    else:
        release["main_release"] = ""
        release["master_id"] = ""


def main(input_json, artists_json, output_json=None):
    """Clean each release and export the cleaned version"""

    # Determine the output path if not provided
    if output_json is None:
        output_json = input_json + ".clean"
        print(f"Releases will be saved to: {output_json}")
    # Create the parent directory if it does not exist
    output_dir = os.path.dirname(output_json)
    if output_dir != "":
        os.makedirs(output_dir, exist_ok=True)

    # Ask the user whether to delete the existing file
    if os.path.isfile(output_json):
        if input(f"{output_json} exists. Remove?[Y/n] ") == "n":
            output_json = input(f"New .json path?\n")

    # Discogs genre tree.
    genre_tree_json = json.load(open(os.path.join(sys.path[0], TAXONOMY_PATH)))
    genre_tree = {}
    for genre in genre_tree_json:
        genre_tree[genre["name"]] = genre["styles"]
    # Decode javascript unicode strings.
    # Converting to json and back appears to be the easiest way to do that.
    genre_tree = json.loads(json.dumps(genre_tree))

    # Load all the artist ids from the json file
    all_artist_ids = set()
    with open(artists_json, encoding="utf-8") as infile:
        for jsonline in infile:
            # Load the artist information
            artist_dict = json.loads(jsonline)
            # Add the artist's ID to the set of artists with releases
            all_artist_ids.update({artist_dict["id"]})

    # Clean the releases
    start_time = time.monotonic()
    print("Cleaning the releases...")
    with open(input_json, encoding="utf-8") as in_f, open(
        output_json, "w", encoding="utf-8"
    ) as out_f:
        r_total, r_success, t_total = 0, 0, 0
        for jsonline in in_f:
            # Load the release
            release = json.loads(jsonline)

            # Print progress
            r_total += 1
            if not r_total % 500000:
                print(f"Processed {r_total:>10,} releases")

            # Skip releases with generic artists
            r_artists = set([a["id"] for a in release["artists"]])
            if len(r_artists.intersection(EXCLUDE_ARTISTS)) > 0:
                continue
            # Skip releases with artists not in the artist list
            # This is a discogs bug
            if len(r_artists.intersection(all_artist_ids)) != len(r_artists):
                continue
            # Exclude releases with certain genres
            if len(set(release["genres"]).intersection(EXCLUDE_GENRES)) > 0:
                continue

            # Clean the release in an efficient way
            clean_tracklist_extraartists(release, all_artist_ids)
            if len(release["tracklist"]) == 0:
                continue
            clean_release_artists_duplicates(release)
            if len(release["artists"]) > N_MAX_ARTISTS:
                continue
            clean_tracklist_artists_duplicates(release)
            if len(release["tracklist"]) == 0:
                continue
            clean_release_extraartists(release, all_artist_ids)

            # Extract the relevant metadata
            extract_year(release)
            extract_style(release, genre_tree)
            extract_videos(release)
            extract_format(release)
            clean_master_id(release)

            # Write the cleaned release
            out_f.write(json.dumps(release, ensure_ascii=False) + "\n")
            r_success += 1
            t_total += len(release["tracklist"])
    print(f"{r_total:>10,} releases are processed in total.")
    print(f"{r_success:>10,} releases remain after cleaning.")
    print(f"{t_total:>10,} tracks remain after cleaning.")
    print(f"{GENRE_TREE_ERRORS:>10,} genre-style matching errors found.")
    print(
        "Total processing time: "
        f"{time.strftime('%H:%M:%S', time.gmtime(time.monotonic()-start_time))}"
    )


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("input_json", type=str, help="Input line-delimited JSON file.")
    parser.add_argument(
        "artists_json", type=str, help="Parsed artists.json.clean file."
    )
    parser.add_argument(
        "--output-json",
        "-o",
        type=str,
        default=None,
        help="Output line-delimited JSON file with clean metadata."
        " Leave empty for auto.",
    )
    args = parser.parse_args()

    # Read the input json, process and write to output_json
    main(args.input_json, args.artists_json, args.output_json)

    #############
    print("Done!")
