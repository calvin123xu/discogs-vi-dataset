"""The goal of this script is to allow the usage of the official Discogs-VI-YT splits when
you download the YouTube URLs yourself. Since the downloadable videos change with time and
location, downloading the videos yourself will create differences with the official splits.
As described in the ISMIR2024 paper, the official splits are compatible with the SHS100K-TEST 
and Da-TACOS benchmark sets. Therefore, we recommend using this script to make your *version* 
of the dataset compatible with the official splits. This script filters the 
Discogs-VI-YT-XXXYYZZ-light.json.train, Discogs-VI-YT-XXXYYZZ-light.json.val, and 
Discogs-VI-YT-XXXYYZZ-light.json.test splits by removing versions that do not have a downloaded 
Youtube video. It also removes cliques with less than two versions."""

import os
import json
import glob
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

if __name__ == "__main__":

    parser = ArgumentParser(
        description=__doc__, formatter_class=ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "input_dir", type=str, help="""Directory that contains 
        the Discogs-VI-YT-XXXYYZZ-light.json.train, 
        Discogs-VI-YT-XXXYYZZ-light.json.val, and 
        Discogs-VI-YT-XXXYYZZ-light.json.test files."""
    )
    parser.add_argument(
        "video_directory",
        type=str,
        help="""Directory with the downloaded Youtube videos. 
        You can provide multiple directories separated by commas, 
        e.g. '/path/to/dir1/,/path/to/dir2/./path/to/dir2/'.""",
    )
    args = parser.parse_args()

    # Get a list of directories where music is stored
    args.video_directory = args.video_directory.split(",")
    # Check if the directories exist
    for video_dir in args.video_directory:
        if not os.path.exists(video_dir):
            raise FileNotFoundError(f"{video_dir} does not exist.")

    # Find the files in the input_dir that ends with .train .val and .test
    train_path = glob.glob(os.path.join(args.input_dir, "**", "Discogs-VI-YT-*-light.json.train"), recursive=True)
    assert len(train_path) == 1, f"train split cannot be found. Expected 1 file, found {len(train_path)}."

    val_path = glob.glob(os.path.join(args.input_dir, "**", "Discogs-VI-YT-*-light.json.val"), recursive=True)
    assert len(val_path) == 1, f"val split cannot be found. Expected 1 file, found {len(val_path)}."

    test_path = glob.glob(os.path.join(args.input_dir, "**", "Discogs-VI-YT-*-light.json.test"), recursive=True)
    assert len(test_path) == 1, f"test split cannot be found. Expected 1 file, found {len(test_path)}."

    # Filter the cliques for each split and print statistics.
    for split, split_path in zip(["train", "val", "test"], [train_path, val_path, test_path]):
        print(f"Filtering the {split} split...")
        split_path = split_path[0]
        print(f"Loading {split_path}...")
        filtered_split_path = split_path + ".filtered"
        print(f"Saving the filtered split to {filtered_split_path}...")

        # Load the cliques of the split
        with open(split_path) as in_f:
            cliques = json.load(in_f)

        # Filter out versions without a youtube video, keep stats
        n_cliques_org, n_versions_org = 0, 0
        n_cliques_rem, n_versions_rem = 0, 0
        for clique_id in list(cliques.keys()):
            clique = cliques[clique_id]
            n_cliques_org += 1
            n_versions_org += len(clique)
            _versions = []
            for version in clique:
                yt_id = version["youtube_id"]
                # Check if the video is downloaded to any of the directories
                if any(
                    [
                        os.path.isfile(
                            os.path.join(video_dir, yt_id[:2], yt_id + ".mp4")
                        )
                        for video_dir in args.video_directory
                    ]
                ):
                    _versions.append(version)
            # Filter out cliques with less than two versions downloaded
            if len(_versions) < 2:
                del cliques[clique_id]
            else:
                cliques[clique_id] = _versions
                n_cliques_rem += 1
                n_versions_rem += len(cliques[clique_id])
        # Calculate percentage of remaining cliques and versions
        ratio_clique = 100*n_cliques_rem/n_cliques_org
        ratio_version = 100*n_versions_rem/n_versions_org
        print(f"{n_cliques_rem:>7,} cliques ({ratio_clique:.1f}%) and {n_versions_rem:>8,} versions ({ratio_version:.1f}) remain")

        # Save the filtered cliques
        with open(filtered_split_path, "w") as out_f:
            json.dump(cliques, out_f)

    print("Done!")
