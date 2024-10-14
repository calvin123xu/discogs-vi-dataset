"""This script reads a jsonl file containing the cliques and creates a .txt file with 
unique youtube queries (for the format of the query string see create_query_string()) 
for all the tracks."""

import os
import json
import argparse

from lib import create_query_string


def main(input_json, output_txt=None):

    # Determine the output path
    if output_txt is None:
        output_txt = input_json + ".queries"
        print(f"The output will be written to: {output_txt}")
    if os.path.exists(output_txt):
        if input(f"{output_txt} exists. Remove?[Y/n] ") == "n":
            output_txt = input(f"New .txt path?\n")
        else:
            open(output_txt, "w").close()
    # Create the parent directory if it does not exist
    output_dir = os.path.dirname(output_txt)
    if output_dir != "":
        os.makedirs(output_dir, exist_ok=True)

    # Load the data
    total_queries = 0
    with open(input_json, encoding="utf-8") as in_f, open(
        output_txt, "w", encoding="utf-8"
    ) as out_f:
        for jline in in_f:
            versioned_clique = json.loads(jline)
            for version in versioned_clique["versions"]:
                queries = set()
                # If the version is not matched to a youtube video before
                # Find the unique queries for all the tracks
                if "youtube_video" not in version or version["youtube_video"] == []:
                    for track in version["tracks"]:
                        queries.update({create_query_string(track)})
                total_queries += len(queries)
                # Write them to the output file
                for query_string in queries:
                    out_f.write(query_string + "\n")
    print(f"Total unique queries: {total_queries:,}")


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "input_json",
        type=str,
        help="Path to the input jsonl file. It should contain versioned cliques.",
    )
    parser.add_argument(
        "--output-txt",
        "-o",
        type=str,
        default=None,
        help="Path to the output txt file. Leave empty for auto.",
    )
    args = parser.parse_args()

    main(args.input_json, args.output_txt)

    print("Done!")
