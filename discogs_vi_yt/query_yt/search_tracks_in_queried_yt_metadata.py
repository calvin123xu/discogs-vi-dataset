"""Script to match the tracks in the versioned cliques to the downloaded Youtube metadata.
It reads versioned cliques and for the versions that are not matched to a Youtube URL,
tries to find it in downloaded metadata inside metadata_dir. The metadata should be 
downloaded with youtube_search_and_download_metadata.py"""

import os
import json
import time
import csv
import argparse

from utils_query import (
    get_youtube_url,
    count_version_video_matches,
    escape_ansi,
)
from lib import (
    prepare_track_for_matching,
    create_query_string,
    compare_video_metadata_with_track_metadata,
)


def main(input_json, metadata_dir, output_json=None, dont_count=False):
    """Read the versioned cliques and for the versions that were not matched to a
    Youtube URL in previous steps, try to find it in the downloaded metadata inside
    metadata_dir."""

    # Determine the output path
    if output_json is None:
        output_json = input_json + ".youtube_query_matched"
        print(f"Cliques will be saved to: {output_json}")
    # Check the output path for not over-writing
    if os.path.exists(output_json):
        if input(f"{output_json} exists. Remove?[Y/n] ") == "n":
            output_json = input(f"New .json path?\n")
        else:
            open(output_json, "w").close()
    # Create the parent directory if it does not exist
    output_dir = os.path.dirname(output_json)
    if output_dir != "":
        os.makedirs(output_dir, exist_ok=True)

    # Write the exceptions here
    log_path = output_json + ".log"
    print(f"Exceptions will be saved to: {log_path}")
    if os.path.exists(log_path):
        if input(f"{log_path} exists. Remove?[Y/n] ") == "n":
            log_path = input(f"New .log path?\n")
        else:
            open(log_path, "w").close()

    # Load all the queries and their mappings
    print("Loading the query mappings...")
    mapping_dict = {}
    mapping_path = os.path.join(metadata_dir, "query_id-mapping.json")
    with open(mapping_path, encoding="utf-8") as meta_file:
        for jline in meta_file:
            metadata = json.loads(jline)
            mapping_dict[metadata["query"]] = metadata["uuid"]

    print(
        "Searching for matches between versions and Youtube URLs using downloaded metadata."
    )
    print("=" * 75)
    t, t0, n_cliques = 0, time.monotonic(), 0
    with open(input_json, encoding="utf-8") as in_f:
        for jsonline in in_f:
            versioned_clique = json.loads(jsonline)

            # For each version in the clique, check if any track's youtube metadata was downloaded
            for version in versioned_clique["versions"]:
                # If the version has a Youtube URL skip it
                if "youtube_video" in version and version["youtube_video"] != []:
                    continue
                else:
                    version["youtube_video"] = []

                for track in version["tracks"]:
                    track["youtube_video"] = []
                    # If the query was made, load the metadata
                    query_string = create_query_string(track)
                    uuid = mapping_dict.get(query_string, "")
                    if not uuid:
                        print(f"Query not found: {query_string}")
                        continue
                    # Get the video metadata
                    search_results_path = os.path.join(
                        metadata_dir, uuid[:2], uuid + ".json"
                    )
                    with open(search_results_path, encoding="utf-8") as meta_file:
                        search_results = json.load(meta_file)
                    # Process the track metadata
                    t_title, t_artists, t_feat_artists = prepare_track_for_matching(
                        track
                    )
                    # Compare the metadata of each video with the track metadata
                    for video_metadata in search_results["entries"]:
                        try:
                            matched, match_type = (
                                compare_video_metadata_with_track_metadata(
                                    t_title,
                                    t_artists,
                                    t_feat_artists,
                                    video_metadata,
                                )
                            )
                            if matched:
                                url = get_youtube_url(video_metadata["id"])
                                # Add the URL to the track if it was found
                                track["youtube_video"].append(
                                    {
                                        "url": url,
                                        "source": "youtube_query",
                                        "match_type": match_type,
                                    }
                                )
                                # Since the results can contain more than one usefull video
                                # we will add all the matches to the track. Keep searching
                        except Exception as e:
                            e = escape_ansi(str(e))
                            with open(log_path, "a", encoding="utf-8") as logfile:
                                logger = csv.writer(logfile, delimiter="\t")
                                logger.writerow(
                                    (
                                        versioned_clique["clique_id"],
                                        version["version_id"],
                                        video_metadata["id"],
                                        e,
                                        track["release_title"],
                                    )
                                )
                    # Add all unique track videos to the version
                    for t_video in track["youtube_video"]:
                        if t_video["url"] not in [
                            v_video["url"] for v_video in version["youtube_video"]
                        ]:
                            # Each url is matched to a track in a certain way
                            # (e.g. title match, artist match, etc.)
                            version["youtube_video"].append(t_video)
                # Sort the videos by match quality
                version["youtube_video"].sort(key=lambda x: int(x["match_type"]))
            # Write the updated clique
            with open(output_json, "a", encoding="utf-8") as o_file:
                o_file.write(json.dumps(versioned_clique, ensure_ascii=False) + "\n")
            # Display progress
            n_cliques += 1
            if not n_cliques % 10000:
                delta_t = time.monotonic() - t0
                t += delta_t
                time_str = time.strftime("%H:%M:%S", time.gmtime(delta_t))
                print(
                    f"Searched {n_cliques:>7,} cliques in downloaded metadata. [{time_str}]"
                )
                t0 = time.monotonic()
    delta_t = time.monotonic() - t0
    t += delta_t
    time_str = time.strftime("%H:%M:%S", time.gmtime(delta_t))
    print(f"Searched {n_cliques:>7,} cliques in downloaded metadata. [{time_str}]")
    if not dont_count:
        count_version_video_matches(output_json)
    print(f"Total Processing time: {time.strftime('%H:%M:%S', time.gmtime(t))}")
    print("Finished the search.")
    print(f"Cliques are saved to: {output_json}")


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "input_json",
        type=str,
        help="Path to JSONL file that contains the cliques of the Discogs-VI dataset.",
    )
    parser.add_argument(
        "metadata_dir",
        type=str,
        help="Directory that contains the downloaded Youtube metadata.",
    )
    parser.add_argument(
        "--output-json",
        "-o",
        type=str,
        default=None,
        help="Path to JSONL file to write cliques with videos. "
        "Leave empty for auto.",
    )
    parser.add_argument(
        "--dont-count",
        action="store_true",
        help="If set, the script will not count the number of matches.",
    )
    args = parser.parse_args()

    # Read the input json, process and write to output_json
    main(args.input_json, args.metadata_dir, args.output_json, args.dont_count)

    #############
    print("Done!")
