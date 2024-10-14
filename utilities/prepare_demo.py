"""This script prepares the demo.json file for the demo.py script."""

import os
import json
import argparse

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("videos_json", type=str, help="Path to videos.json")
    parser.add_argument(
        "--output_json", type=str, default=None, help="Path to output json"
    )
    args = parser.parse_args()

    # Determine the output path if not provided
    if not args.output_json:
        args.output_json = args.videos_json + ".demo"
        print(f"The demo file will be saved to: {args.output_json}")

    # Ask the user whether to delete the existing file
    if os.path.isfile(args.output_json):
        if input(f"{args.output_json} exists. Remove?[Y/n] ") == "n":
            args.output_json = input(f"New .json path?\n")

    # Load the videos.json, filter information and write the demo.json
    n_versions = []
    with open(args.videos_json, encoding="utf-8") as in_f, open(
        args.output_json, "w", encoding="utf-8"
    ) as out_f:
        for jsonline in in_f:
            # Load the clique
            clique = json.loads(jsonline)
            # Remove versions without a youtube video
            _versions = []
            for version in clique["versions"]:
                if len(version["youtube_video"]) >= 1:
                    # Keep only the first track, ın most of the cases ıt ıs the same
                    version["tracks"] = [version["tracks"][0]]
                    _versions.append(version)
            clique["versions"] = _versions
            # Keep only cliques with more than one version remaining
            if len(clique["versions"]) > 1:
                # Keep only the first track, ın most of the cases ıt ıs the same
                for version in clique["versions"]:
                    track = version["tracks"][0]
                    version["tracks"] = [track]
                out_f.write(json.dumps(clique) + "\n")
                n_versions.append(len(clique["versions"]))
    print(f"Found {len(n_versions):,} cliques with {sum(n_versions):,} versions.")
    print(f"Average clique size: {sum(n_versions)/len(n_versions):.1f}")
    print(f"Max clique size: {max(n_versions)}")
    print(f"Min clique size: {min(n_versions)}")
    print(f"Median clique size: {sorted(n_versions)[len(n_versions)//2]}")
    print(f"Mode of the clique sizes: {max(set(n_versions), key=n_versions.count)}")
    print("DOne!")
