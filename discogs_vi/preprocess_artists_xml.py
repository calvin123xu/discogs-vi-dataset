"""Loads a Discogs "artists" dump in XML format, pre-processes it and stores 
the output in a line-delimited JSON file where each line corresponds to a 
particular release."""

import os
import json
import time
import xmltodict
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

processed = 0

# All keys in the artist dictionary:
# ['realname', 'data_quality', 'aliases', 'urls', 'namevariations',
# 'groups', 'id', 'profile', 'name', 'images', 'members']


def get_artist(path, artist):
    """Removes unnecessary keys from the artist dictionary and writes it to
    the json file."""

    global processed

    # Remove unnecessary fields.
    remove_keys = [
        "images",
        "profile",
        "data_quality",
        "urls",
        "realname",
    ]
    for key in remove_keys:
        if key in artist:
            del artist[key]

    # Simplify some fields.
    for key in ["aliases", "groups"]:

        if key in artist:
            if artist[key] is None:
                del artist[key]
            else:
                artist[key] = (
                    artist[key]["name"]
                    if type(artist[key]["name"]) is list
                    else [artist[key]["name"]]
                )
                artist[key] = [
                    {"id": field["@id"], "name": field["#text"]}
                    for field in artist[key]
                ]

    if "namevariations" in artist:
        if artist["namevariations"] is None:
            del artist[key]
        else:
            artist["namevariations"] = (
                artist["namevariations"]["name"]
                if type(artist["namevariations"]["name"]) is list
                else [artist["namevariations"]["name"]]
            )

    if "members" in artist:
        if type(artist["members"]["id"]) is not list:
            artist["members"]["id"] = [artist["members"]["id"]]
        if type(artist["members"]["name"]) is not list:
            artist["members"]["name"] = [artist["members"]["name"]]
        # Simplify the members field while keeping the order
        names = []
        for id in artist["members"]["id"]:
            for name in artist["members"]["name"]:
                if id == name["@id"]:
                    names.append(name["#text"])
                    break
        if len(names) == len(artist["members"]["id"]):
            artist["members"]["name"] = names
        else:
            print("Error on", artist["id"])

    # Keep only the ids for these fields for fast lookup
    if "members" in artist:
        artist["members"] = artist["members"]["id"]
    for key in ["aliases", "groups"]:
        if key in artist:
            artist[key] = [group["id"] for group in artist[key]]

    # Write the json to a file
    json_f.write(json.dumps(artist, ensure_ascii=False) + "\n")

    processed += 1
    if not processed % 100000:
        print(f"Processed {processed:>10,} artists")

    return True


def main(xml_file, output_dir=None):

    assert os.path.splitext(xml_file)[1] == ".xml", "Input file must be an xml file"

    # Write next to the xml file if no output_dir is specified
    if output_dir is None:
        output_dir = os.path.dirname(os.path.normpath(xml_file))

    # The output file will have the same name as the xml file but with .json extension
    output_path = os.path.join(output_dir, f"{os.path.basename(xml_file)}.jsonl")

    # Ask the user whether to delete the existing file
    if os.path.isfile(output_path):
        if input(f"{output_path} exists. Remove?[Y/n] ") == "n":
            output_path = input(f"New .json path?\n")

    # Open the json files for writing
    global json_f
    json_f = open(output_path, "w", encoding="utf-8")

    # Parse and main the xml file
    start_time = time.monotonic()
    print(f"Loading {xml_file}")
    xmltodict.parse(open(xml_file, "rb"), item_depth=2, item_callback=get_artist)
    print(f"{processed:>10,} artists loaded")
    print(
        "Total processing time: "
        f"{time.strftime('%H:%M:%S', time.gmtime(time.monotonic()-start_time))}"
    )

    # Close the json file
    json_f.close()


if __name__ == "__main__":

    parser = ArgumentParser(
        description=__doc__, formatter_class=ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "xml_file", type=str, default=None, help='Input XML "releases" dump file.'
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

    main(args.xml_file, args.output_dir)

    #############
    print("Done!")
