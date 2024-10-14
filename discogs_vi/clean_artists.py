"""Loads a Discogs "artists" dump in XML format, pre-processes it and stores 
the output in a line-delimited JSON file where each line corresponds to a 
particular release."""

import os
import json
import time
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

from variables import NO_ARTIST


def clean_artist(artist, diff):
    """Removes artists with bad quality annotations and fixes the keys."""

    # Make sure that an artist does not appear in its own members list
    members = artist.get("members", [])
    if artist["id"] in members:
        # Delete the artist from the list of members
        artist["members"] = [member for member in members if member != artist["id"]]
        # If the artist has no members left, delete the key
        if not artist["members"]:
            del artist["members"]
    # Make sure that an artist does not appear in its own groups list
    groups = artist.get("groups", [])
    if artist["id"] in groups:
        # Delete the artist from the list of members
        artist["groups"] = [group for group in groups if group != artist["id"]]
        # If the artist has no groups lfet, delete the key
        if not artist["groups"]:
            del artist["groups"]

    # 4240 artists have both members and groups
    if "members" in artist and "groups" in artist:
        del artist["members"]

    # If any of the fields contains an artist and the artist has no releases,
    # remove that artist
    for key in ["aliases", "members", "groups"]:
        if key in artist:
            artist[key] = [id for id in artist[key] if id not in diff]
            # If the artist has no members left, delete the key
            if not artist[key]:
                del artist[key]

    # If any of the fields contains the NO_ARTIST, remove that artist
    for key in ["aliases", "members", "groups"]:
        if key in artist:
            artist[key] = [id for id in artist[key] if id != NO_ARTIST]
            # If the artist has no members left, delete the key
            if not artist[key]:
                del artist[key]

    return artist


def get_all_name_variations(artist_id, artists_dict, name_to_id):
    """Returns a set of all the name variations of the artist."""

    if "namevariations" not in artists_dict[artist_id]:
        return []

    namevar_ids = set()
    for namevar in artists_dict[artist_id]["namevariations"]:
        # Use the reverse lookup dictionary
        if namevar in name_to_id:
            namevar_ids.add(name_to_id[namevar])

    # namevar_ids.add(artist_id) # TODO: Is this necessary?

    # Collect the variations of the variations
    namevar_var_ids = set()
    for _id in namevar_ids:
        if "namevariations" in artists_dict[_id]:
            for namevar in artists_dict[_id]["namevariations"]:
                # Use the reverse lookup dictionary
                if namevar in name_to_id:
                    namevar_var_ids.add(name_to_id[namevar])

    return list(namevar_ids.union(namevar_var_ids))


def main(json_file, output_dir=None):

    # Write next to the json file if no output_dir is specified
    if output_dir is None:
        output_dir = os.path.dirname(os.path.normpath(json_file))

    # The output file will have the same name as the xml file but with .json extension
    clean_json_file = f"{json_file}.clean"
    # Ask the user whether to delete the existing file
    if os.path.isfile(clean_json_file):
        if input(f"{clean_json_file} exists. Remove?[Y/n] ") == "n":
            clean_json_file = input(f"New .json path?\n")

    start_time = time.monotonic()

    # Load all the artists from the json file
    print("Loading the artists...")
    artist_ids_with_releases, all_artist_ids = set(), set()
    with open(json_file, encoding="utf-8") as infile:
        for jsonline in infile:
            # Load the artist information
            artist_dict = json.loads(jsonline)

            # Add the artist's ID to the set of artists with releases
            artist_ids_with_releases.update({artist_dict["id"]})

            # Add the artist and all its aliases, members and groups
            # to the set of all artists
            all_artist_ids.update({artist_dict["id"]})
            all_artist_ids.update(artist_dict.get("aliases", {}))
            all_artist_ids.update(artist_dict.get("members", {}))
            all_artist_ids.update(artist_dict.get("groups", {}))
    diff = all_artist_ids - artist_ids_with_releases
    print(f"Found {len(all_artist_ids):>9,} artists in total")
    print(f"Found {len(artist_ids_with_releases):>9,} artists with releases")
    print(f"Found {len(diff):>9,} artists without releases")

    # Load all the artists from the json file and clean them
    print("Cleaning the artists...")
    processed = 0
    artists_dict = {}
    with open(json_file, encoding="utf-8") as infile:
        for jsonline in infile:
            # Load the artist information
            artist_dict = json.loads(jsonline)

            # Clean the artist
            artist = clean_artist(artist_dict, diff)

            # Add the cleaned artist to the dictionary
            artists_dict[artist["id"]] = artist

            processed += 1
            if not processed % 100000:
                print(f"Processed {processed:>10,} artists")
    print(f"Processed {processed:>10,} artists")

    print('Adding "namevariations_id" to the artists...')
    start_time = time.monotonic()
    # Create a reverse lookup dictionary
    name_to_id = {v["name"]: k for k, v in artists_dict.items()}

    with open(clean_json_file, "w", encoding="utf-8") as json_f_clean:
        for artist_id in artists_dict:
            # Add the name variations to the dictionary
            name_variations = get_all_name_variations(
                artist_id, artists_dict, name_to_id
            )
            if name_variations:
                artists_dict[artist_id]["namevariations_id"] = name_variations
            # Write the cleaned and modified artist to the output file
            json_f_clean.write(
                json.dumps(artists_dict[artist_id], ensure_ascii=False) + "\n"
            )
    print(
        "Processing time: "
        f"{time.strftime('%H:%M:%S', time.gmtime(time.monotonic()-start_time))}"
    )


if __name__ == "__main__":

    parser = ArgumentParser(
        description=__doc__, formatter_class=ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "json_file", type=str, default=None, help="Path to the json file."
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=str,
        default=None,
        help="Output directory."
        "If not specified, the output file will be stored"
        "next to the input file.",
    )
    args = parser.parse_args()

    # Read the input xml, process and write to json_file
    main(args.json_file, args.output_dir)

    #############
    print("Done!")
