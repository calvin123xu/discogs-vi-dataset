"""Takes the tracks in tracks_json file and using the artist relations in the
artists_json finds cliques and versions. Saves the cliques in a jsonl file."""

import os
import sys
import json
import time
import argparse
from collections import defaultdict
from itertools import combinations

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from utilities.utils import (
    collect_writer_artists,
    collect_performance_artists,
    hard_clean_text,
)


class SetEncoder(json.JSONEncoder):
    """Convert sets to lists for json encoding"""

    def default(self, obj):
        if isinstance(obj, set):
            return list(obj)
        return json.JSONEncoder.default(self, obj)


def read_tracks(tracks_json, artists_dict):
    """Reads the tracks in the json file to a dict of lists with track titles as keys."""

    t0 = time.monotonic()

    n_tracks, tracks_dict = 0, defaultdict(lambda: defaultdict(list))
    print(f"Reading the tracks...")
    with open(tracks_json, encoding="utf-8") as in_f:
        for jsonline in in_f:
            track = json.loads(jsonline)
            n_tracks += 1
            track_artists = frozenset(collect_performance_artists(track, artists_dict))
            track_writers = frozenset(collect_writer_artists(track, artists_dict))
            found = False
            # Check if the track is already in the dictionary
            for i, (writers, _) in enumerate(
                tracks_dict[track["track_title_cleaned"]][track_artists]
            ):
                # If the writer_artists are the same, add the track to the list
                # we will merge later if there are intersecting writers
                # this is faster
                if writers == track_writers:
                    tracks_dict[track["track_title_cleaned"]][track_artists][i][
                        1
                    ].append(track)
                    found = True
                    break
            # Create a new entry if not found
            if not found:
                tracks_dict[track["track_title_cleaned"]][track_artists].append(
                    [track_writers, [track]]
                )
    print(f"There are {n_tracks:>10,} tracks.")
    print(f"There are {len(tracks_dict):>10,} unique track titles.")

    # Keep titles with more than one performer as only they can form cliques
    print("Removing the titles that appear only once...")
    tracks_dict = {k: v for k, v in tracks_dict.items() if len(v) > 1}
    print(
        f"There are {len(tracks_dict):>10,} unique titles with more than one performer."
    )

    # For each performance artist, merge tracks with intersecting writers (creates a version)
    print("Merging tracks with intersecting writers into versions...")
    for track_title, title_dict in tracks_dict.items():
        for writers_and_tracks in title_dict.values():
            merged = True
            while merged:
                merged = False
                for i, (writers, _) in enumerate(writers_and_tracks):
                    for j, (writers2, tracks2) in enumerate(
                        writers_and_tracks[i + 1 :]
                    ):
                        # If there are common writers, merge the tracks and writers
                        if writers & writers2:
                            # Update the writers
                            writers_and_tracks[i][0] = writers.union(writers2)
                            # Merge the tracks
                            writers_and_tracks[i][1].extend(tracks2)
                            # Delete the second writer
                            del writers_and_tracks[i + j + 1]
                            merged = True
                            break
                    if merged:
                        break

    # Test for intersection of writers
    for track_title, title_dict in tracks_dict.items():
        for writers_and_tracks in title_dict.values():
            for x1, x2 in combinations(writers_and_tracks, 2):
                assert x1[0] & x2[0] == frozenset(), track_title

    # Remove tracks with bad writer annotations
    # TODO: a smalle percetange of versions require union of artist sets to eliminate writer disagreements
    print("Removing versions with conflicting writer annotations...")
    writer_disagreements, writer_agreements, voted_agreements = 0, 0, 0
    for track_title in list(tracks_dict.keys()):
        for artists in list(tracks_dict[track_title].keys()):
            # Decide a writer for versions with conflicting writer annotations
            if len(tracks_dict[track_title][artists]) > 1:
                # Do a majority vote for the writer artists
                writer_votes = [
                    len(tracks) for _, tracks in tracks_dict[track_title][artists]
                ]
                # If there is a majority, remove the other writer artists
                if writer_votes.count(max(writer_votes)) == 1:
                    majority_index = writer_votes.index(max(writer_votes))
                    tracks_dict[track_title][artists] = tracks_dict[track_title][
                        artists
                    ][majority_index]
                    voted_agreements += 1
                else:
                    # Remove the version if there is no majority
                    del tracks_dict[track_title][artists]
                writer_disagreements += 1
            elif len(tracks_dict[track_title][artists]) == 1:
                # Remove the capsulating list
                tracks_dict[track_title][artists] = tracks_dict[track_title][artists][0]
                writer_agreements += 1
            else:
                raise ValueError
    print(f"Writer disagreements: {writer_disagreements:>9,} versions.")
    print(f" Voted disagreements: {voted_agreements:>9,} versions.")
    print(f"   Writer agreements: {writer_agreements:>9,} versions.")

    # Remove titles with no artists
    print("Removing titles with no performers left...")
    tracks_dict = {k: v for k, v in tracks_dict.items() if len(v) > 0}
    print(
        f"There are {len(tracks_dict):>10,} unique titles with more than one performer."
    )

    print(
        f"Processing time: {time.strftime('%H:%M:%S', time.gmtime(time.monotonic()-t0))}"
    )

    return tracks_dict


def find_cliques(tracks_dict):

    t0 = time.monotonic()

    # Create cliques and versions
    cliques_dict = {}
    for track_title, title_dict in tracks_dict.items():
        cliques_dict[track_title] = []
        for version_writers, version_tracks in title_dict.values():

            # If the clique exists, add the version to it
            # A clique = [version_writers, versions=[[tracks=[...]], [tracks=[...]], ...]]
            found = False
            for i, (clique_writers, _) in enumerate(cliques_dict[track_title]):
                if clique_writers & version_writers:
                    # Merge the writers of the clique
                    cliques_dict[track_title][i][0] = clique_writers.union(
                        version_writers
                    )
                    # Add the version_tracks to the clique
                    cliques_dict[track_title][i][1].append(version_tracks)
                    found = True
                    break
            # Create a new clique with the version_writers and the version_tracks of tracks
            if not found:
                cliques_dict[track_title].append([version_writers, [version_tracks]])

    # Merge cliques with intersecting writers
    for track_title in cliques_dict.keys():
        merged = True
        while merged:
            merged = False
            for i, (writers, _) in enumerate(cliques_dict[track_title]):
                for j, (writers2, versions2) in enumerate(
                    cliques_dict[track_title][i + 1 :]
                ):
                    if writers & writers2:
                        # Merge the writers
                        cliques_dict[track_title][i][0] = writers.union(writers2)
                        # Put the versions together
                        cliques_dict[track_title][i][1].extend(versions2)
                        # Delete the second clique
                        del cliques_dict[track_title][i + j + 1]
                        merged = True
                        break
                if merged:
                    break

    # Remove cliques with only one version
    print("Removing cliques with only one version...")
    cliques_dict = {
        title: [clique for clique in cliques if len(clique[1]) > 1]
        for title, cliques in cliques_dict.items()
    }
    # Check for intersection of writers in cliques after the merge
    for clique_list in cliques_dict.values():
        for clique_a, clique_b in combinations(clique_list, 2):
            assert clique_a[0] & clique_b[0] == frozenset()

    # Remove the writer artists from the cliques_dict
    for cliques in cliques_dict.values():
        for i, (_, versions) in enumerate(cliques):
            cliques[i] = versions

    # Here disentangle versions based on their hard_cleaned title
    # cliques_dict[track_title] = [[version1_tracks], [version2_tracks], ...]
    # should become
    # cliques_dict[track_title] = [[version1A_tracks], [version1B_tracks], [version2_tracks], ...]
    for cliques_with_same_title in cliques_dict.values():
        for i, versions in enumerate(cliques_with_same_title):
            new_versions = []
            flag = False
            for version in versions:
                versions_dict = defaultdict(list)
                for track in version:
                    cleaned_title = hard_clean_text(track["track_title"])
                    versions_dict[cleaned_title].append(track)
                # If the version should be separated
                if len(versions_dict) > 1:
                    flag = True
                    for version_tracks in versions_dict.values():
                        new_versions.append(version_tracks)
                else:
                    new_versions.append(version)
            if flag:
                # Replace the old versions with the new ones
                cliques_with_same_title[i] = new_versions

    print(
        f"Processing time: {time.strftime('%H:%M:%S', time.gmtime(time.monotonic()-t0))}"
    )

    return cliques_dict


def main(input_json, artists_json, output_json=None):
    """Reads the tracks in the input_json, finds the unique track
    titles, and uses them and common writers to finds cliques."""

    # If no name is provided set it to Discogs-VI-YYYY_MM_DD.jsonl
    if output_json is None:
        _dir = os.path.dirname(input_json)
        dump_date = (
            input_json.split("_releases.xml")[0].split("/")[-1].split("discogs_")[-1]
        )
        output_json = os.path.join(_dir, f"Discogs-VI-{dump_date}.jsonl")
        print(f"Cliques will be saved to: {output_json}")

    # Check the output path for not over-writing
    if os.path.exists(output_json):
        if input(f"{output_json} exists. Remove?[Y/n] ") == "Y":
            open(output_json, "w").close()
        else:
            output_json = input(f"New .json path?\n")
    # Create the parent directory if it does not exist
    output_dir = os.path.dirname(output_json)
    if output_dir != "":
        os.makedirs(output_dir, exist_ok=True)

    # Load the artists dictionary
    print("Loading the artists dictionary...")
    artists_dict = {}
    with open(artists_json, encoding="utf-8") as infile:
        for jsonline in infile:
            artist = json.loads(jsonline)
            artists_dict[artist["id"]] = artist
            del artists_dict[artist["id"]]["id"]

    # Read track information and apply preprocessing
    tracks_dict = read_tracks(input_json, artists_dict)

    # Clique and Version detection algorithm
    n_cliques, n_versions, n_tracks = 0, 0, 0
    print("Searching for cliques and versions...")
    cliques_dict = find_cliques(tracks_dict)
    # Get the different cliques that share the same title
    for cliques in cliques_dict.values():
        # For each clique create a dictionary
        for clique in cliques:
            clique_dict = {
                "clique_id": f"C-{str(n_cliques).zfill(7)}",
                "versions": [],
            }
            n_cliques += 1
            for version in clique:
                clique_dict["versions"].append(
                    {
                        "version_id": f"V-{str(n_versions).zfill(7)}",
                        "tracks": version,
                    }
                )
                n_versions += 1
                n_tracks += len(version)
            with open(output_json, "a", encoding="utf-8") as outfile:
                outfile.write(
                    json.dumps(clique_dict, cls=SetEncoder, ensure_ascii=False) + "\n"
                )
    print(
        f"{n_cliques:>9,} cliques are versioned into {n_versions:>9,} versions with {n_tracks:>10,} tracks."
    )
    print("Finished the search.")


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "input_json", type=str, help="Path to json file that contains parsed tracks."
    )
    parser.add_argument(
        "artists_json", type=str, help="Parsed artists.json.clean file."
    )
    parser.add_argument(
        "--output-json",
        "-o",
        type=str,
        default=None,
        help="Path to json file to write cliques. Leave empty for auto.",
    )
    args = parser.parse_args()

    # Read the input json, artists json and process them.
    # Write the outputs to output_json
    main(args.input_json, args.artists_json, args.output_json)

    ##############
    print("Done!")
