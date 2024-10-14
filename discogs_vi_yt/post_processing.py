"""This script filters out the versions that do not have a downloaded Youtube 
video from the versions.json file to finalize the Discogs-VI-YT dataset. It also 
filters out the cliques that have only one version left. Also it keeps only one 
version per youtube_id. The output is written to a new .json file."""

import os
import json
from collections import defaultdict, Counter
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

from query_yt.utils_query import get_youtube_id, count_version_video_matches

if __name__ == "__main__":

    parser = ArgumentParser(
        description=__doc__, formatter_class=ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "input_json", type=str, help="Path to query matched cliques.json file."
    )
    parser.add_argument(
        "video_directory",
        type=str,
        help="Directory with the downloaded Youtube videos."
        "You can provide multiple directories separated by commas.",
    )
    parser.add_argument(
        "--output-json",
        "-o",
        type=str,
        default=None,
        help="Output json file. Leave empty for auto.",
    )
    args = parser.parse_args()

    # Determine the output path
    if args.output_json is None:  # if empty string
        _dir = os.path.dirname(args.input_json)
        _base = os.path.basename(args.input_json).split(".")[0]
        date = _base.split("-")[-1]
        args.output_json = os.path.join(_dir, f"Discogs-VI-YT-{date}.jsonl")
        print(f"The output will be written to: {args.output_json}")
    discogs_vi_yt_light_path = args.output_json.replace(".jsonl", "-light.json")
    print(f"The light dataset will be written to: {discogs_vi_yt_light_path}")
    # Ask the user whether to delete
    if os.path.exists(args.output_json):
        if input(f"{args.output_json} exists. Remove?[Y/n] ") == "n":
            args.output_json = input(f"New .json path?\n")
    if os.path.exists(discogs_vi_yt_light_path):
        if input(f"{discogs_vi_yt_light_path} exists. Remove?[Y/n] ") == "n":
            discogs_vi_yt_light_path = input(f"New .json path?\n")
    # Create the parent directory if it does not exist
    output_dir = os.path.dirname(args.output_json)
    if output_dir != "":
        os.makedirs(output_dir, exist_ok=True)

    # Split the video directories
    args.video_directory = args.video_directory.split(",")
    # Check if the directories exist
    for video_dir in args.video_directory:
        if not os.path.exists(video_dir):
            raise FileNotFoundError(f"{video_dir} does not exist.")

    # For each version, delete the videos that were not downloaded
    n_cliques, n_versions = 0, 0
    with open(args.input_json, encoding="utf-8") as in_f, open(
        args.output_json, "w", encoding="utf-8"
    ) as out_f:
        for jsonline in in_f:
            clique = json.loads(jsonline)

            for version in clique["versions"]:
                _videos = []
                for video in version["youtube_video"]:
                    yt_id = get_youtube_id(video["url"])
                    # Check if the video is downloaded to any of the directories
                    if any(
                        [
                            os.path.isfile(
                                os.path.join(video_dir, yt_id[:2], yt_id + ".mp4")
                            )
                            for video_dir in args.video_directory
                        ]
                    ):
                        _videos.append(video)
                version["youtube_video"] = _videos
            # Filter out versions without a youtube video
            clique["versions"] = [
                version
                for version in clique["versions"]
                if version["youtube_video"] != []
            ]
            # Filter out cliques with less than two versions
            if len(clique["versions"]) < 2:
                continue

            # Check which versions are matched to the same video
            video_version_mappings = defaultdict(list)
            for i, version in enumerate(clique["versions"]):
                # Use only the best match NOTE: could be improved
                video_version_mappings[version["youtube_video"][0]["url"]].append(i)
            # Keep one version per video
            _versions = []
            for version_indices in video_version_mappings.values():
                _versions.append(clique["versions"][version_indices[0]])
            clique["versions"] = _versions
            # Filter out cliques with less than two versions
            if len(clique["versions"]) < 2:
                continue

            # Write the clique to the output file
            out_f.write(json.dumps(clique, ensure_ascii=False) + "\n")
            n_cliques += 1
            n_versions += len(clique["versions"])

    print(f"{n_cliques:>7,} cliques versioned into {n_versions:>8,} versions.")
    # Print some statistics
    count_version_video_matches(args.output_json)

    # Here we will keep only the first video that was downloaded for each version and reduce the amount of metadata
    print("Creating the light dataset...")
    dataset = dict()
    with open(args.output_json, encoding="utf-8") as in_f:
        for jline in in_f:
            clique = json.loads(jline)
            dataset[clique["clique_id"]] = []
            for version in clique["versions"]:
                # Find which video was downloaded
                relevant_yt_id = ""
                for video in version["youtube_video"]:
                    yt_id = get_youtube_id(video["url"])
                    # Check if the video is downloaded to any of the directories
                    if any(
                        [
                            os.path.isfile(
                                os.path.join(video_dir, yt_id[:2], yt_id + ".mp4")
                            )
                            for video_dir in args.video_directory
                        ]
                    ):
                        relevant_yt_id = yt_id
                        break
                assert (
                    relevant_yt_id != ""
                ), f"No video found for {version['version_id']}"
                version_reduced = {
                    "version_id": version["version_id"],
                    "track_title": version["tracks"][0][
                        "track_title"
                    ],  # use the first track
                    # '' # TODO: track artists and release artists?
                    "youtube_id": relevant_yt_id,
                }
                dataset[clique["clique_id"]].append(version_reduced)

    # Count the number of versions per clique
    n_total_cliques = len(dataset)
    print(f"Number of total cliques: {n_total_cliques}")
    n_versions_per_clique = Counter([len(clique) for clique in dataset.values()])
    n_total_versions = sum([len(clique) for clique in dataset.values()])
    print(f"Number of total versions: {n_total_versions}")

    # We write the light dataset as a JSON file with the default encoding
    with open(discogs_vi_yt_light_path, "w") as out_f:
        json.dump(dataset, out_f)

    print("Done!")
