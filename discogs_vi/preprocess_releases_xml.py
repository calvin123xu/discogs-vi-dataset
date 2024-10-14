"""Loads a Discogs "releases" dump in XML format, pre-processes it and stores 
the output in a line-delimited JSON file where each line corresponds to a 
particular release."""

import os
import json
import time
import xmltodict
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

processed = 0
errors = 0


def get_release(path, release):
    global errors
    global processed

    # Path: releases (root) -> release (id) -> ...
    release["id"] = path[1][1]["id"]

    # Remove unnecessary fields.
    if "images" in release:
        del release["images"]
    if "notes" in release:
        del release["notes"]
    if "companies" in release:
        del release["companies"]
    if "identifiers" in release:
        del release["identifiers"]
    if "data_quality" in release:
        del release["data_quality"]

    # Simplify some fields.
    try:
        release["genres"] = release["genres"]["genre"]
        release["styles"] = release["styles"]["style"] if "styles" in release else []
        release["artists"] = release["artists"]["artist"]
        release["tracklist"] = release["tracklist"]["track"]
        release["formats"] = release["formats"]["format"]
        release["labels"] = release["labels"]["label"]
        release["videos"] = release["videos"]["video"] if "videos" in release else []
        release["extraartists"] = (
            [] if release["extraartists"] is None else release["extraartists"]["artist"]
        )
        release["country"] = release["country"] if "country" in release else ""
        release["released"] = release["released"] if "released" in release else ""
        release["master_id"] = release["master_id"] if "master_id" in release else {}
    except:
        print("Error reading", json.dumps(release, indent=4))
        errors += 1
        return True

    # Make each field a list
    if type(release["genres"]) is str:
        release["genres"] = [release["genres"]]
    if type(release["styles"]) is str:
        release["styles"] = [release["styles"]]
    if type(release["artists"]) is not list:
        release["artists"] = [release["artists"]]
    if type(release["tracklist"]) is not list:
        release["tracklist"] = [release["tracklist"]]
    if type(release["formats"]) is not list:
        release["formats"] = [release["formats"]]
    if type(release["labels"]) is not list:
        release["labels"] = [release["labels"]]
    if type(release["videos"]) is not list:
        release["videos"] = [release["videos"]]
    if type(release["extraartists"]) is not list:
        release["extraartists"] = [release["extraartists"]]

    release["labels"] = list(set([l["@name"] for l in release["labels"]]))

    # Clean extraartists field
    for a in release["extraartists"]:
        if a["role"] is None:
            a["role"] = ""
        del a["anv"]
        del a["join"]
        del a["tracks"]

    # Clean artists field
    for a in release["artists"]:
        del a["anv"]
        del a["join"]
        del a["role"]  # They all are None
        del a["tracks"]

    # Clean tracklist fields
    for t in release["tracklist"]:
        del t["position"]
        del t["duration"]
        if t["title"] is None:
            t["title"] = ""
        if "extraartists" in t:
            t["extraartists"] = t["extraartists"]["artist"]  # Simplify
            if type(t["extraartists"]) is not list:  # Make list
                t["extraartists"] = [t["extraartists"]]
            for ta in t["extraartists"]:
                del ta["tracks"]
                del ta["anv"]
                del ta["join"]
        if "artists" in t:
            t["artists"] = t["artists"]["artist"]  # Simplify
            if type(t["artists"]) is not list:  # Make list
                t["artists"] = [t["artists"]]
            for ta in t["artists"]:  # Clean
                del ta["role"]  # They are all None
                del ta["anv"]
                del ta["join"]
                del ta["tracks"]

    # Clean format
    for f in release["formats"]:
        if "@text" in f:
            del f["@text"]

    # Clean videos
    release["videos"] = [
        {"url": v["@src"], "duration": int(v["@duration"]), "title": v["title"]}
        for v in release["videos"]
    ]

    ##############
    # Cleanup done

    # Write to file as a line-delimited json
    json_f.write(json.dumps(release, ensure_ascii=False) + "\n")

    processed += 1
    if not processed % 50000:
        print(f"Processed {processed:>10,} releases")
    return True


def main(xml_file, output_dir=None):

    assert os.path.splitext(xml_file)[1] == ".xml", "Input file must be an xml file"

    # Write next to the xml file if no output_dir is specified
    if output_dir is None:
        output_dir = os.path.dirname(os.path.normpath(xml_file))

    # The output file will have the same name as the xml file but with .jsonl extension
    output_path = os.path.join(output_dir, f"{os.path.basename(xml_file)}.jsonl")

    # Ask the user whether to delete the existing file
    if os.path.isfile(output_path):
        if input(f"{output_path} exists. Remove?[Y/n] ") == "n":
            output_path = input(f"New path?\n")

    # Open the output file
    global json_f
    json_f = open(output_path, "w", encoding="utf-8")

    # Parse and main the xml file
    start_time = time.monotonic()
    print(f"Loading {xml_file}")
    xmltodict.parse(open(xml_file, "rb"), item_depth=2, item_callback=get_release)
    print(f"Processed {processed:>10,} releases")
    print(f"{errors:>20,} releases skipped due to errors")
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

    # Read the input xml, process and write to output_path
    main(args.xml_file, args.output_dir)

    #############
    print("Done!")
