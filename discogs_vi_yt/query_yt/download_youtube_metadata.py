"""This script takes a line delimited text file that contains the Youtube IDs to 
download their metadata. It will download the metadata for each Youtube ID and save
it in a JSONL file. The script will create a directory for each Youtube ID's metadata
file. The directory will be named after the first two characters of the Youtube ID.
The script will only download the metadata for the missing release videos. It script 
uses yt-dlp to download the metadata. The metadata is saved in a JSONL file after 
filtering some information."""

import os
import json
import time
import argparse

import yt_dlp

from utils_query import select_fields, get_youtube_url, seconds_to_dhms

YDL_OPTS = {
    "noplaylist": True,
    "source_address": "0.0.0.0",
    # Currently data servers are all blocked. ipv4 fixed it.
    # https://github.com/yt-dlp/yt-dlp/issues/7143
    "force_ipv4": True,
    # "verbose": True,
    # "proxy": "127.0.0.1:3128",
    # "client_certificate"
    # "http_headers": {
    #     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
    # },
    # source_address
    # sleep_interval_requests
    # sleep_interval
}


def download_metadata(yt_id, output_dir):
    """Download the metadata for a Youtube ID and save it in a JSONL file."""

    url = get_youtube_url(yt_id)
    # Download the metadata of the url
    with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
        # Download the metadata
        video_info = ydl.extract_info(url, download=False)
        video_info = ydl.sanitize_info(video_info)
        # Keep only the fields that we are interested
        video_info = select_fields(video_info)
        if len(video_info["id"]) != 11 or video_info["id"] == "M5t4UHllkUM":
            print(f"Invalid Youtube ID: {yt_id}")
        else:
            # Create the directory for the metadata
            metadata_dir = os.path.join(output_dir, yt_id[:2])
            os.makedirs(metadata_dir, exist_ok=True)
            # Write the metadata to the output file
            metadata_path = os.path.join(metadata_dir, f"{yt_id}.meta")
            with open(metadata_path, "w", encoding="utf-8") as out_f:
                out_f.write(json.dumps(video_info, ensure_ascii=False) + "\n")


def main(input_txt, output_dir):

    # Create an empty file for the logs
    output_log_path = f"{input_txt}.log"
    open(output_log_path, "w").close()

    # Read the youtube IDs from the input text file
    with open(input_txt, encoding="utf-8") as in_f:
        yt_ids = set([l for l in in_f.read().splitlines() if l != ""])
    print(f"{len(yt_ids):,} Youtube IDs read.")

    # Skip the downloaded metadata
    print("Checking for previously downloaded metadata...")
    downloaded_yt_ids = set()
    for yt_id in yt_ids:
        metadata_path = os.path.join(output_dir, yt_id[:2], f"{yt_id}.meta")
        if os.path.exists(metadata_path):
            downloaded_yt_ids.update({yt_id})
    if len(downloaded_yt_ids) > 0:
        print(f"{len(downloaded_yt_ids):,} metadata IDs were previously downloaded.")
        yt_ids = yt_ids.difference(downloaded_yt_ids)
    else:
        print("No previously downloaded metadata found.")
    print(f"{len(yt_ids):,} Youtube IDs will be downloaded.")

    # Download each yt url's metadata
    q_success, q_fail = 0, 0
    t0 = time.monotonic()
    print(f"Downloading the metadata for each missing Youtube ID...")
    for i, yt_id in enumerate(yt_ids):
        try:
            download_metadata(yt_id, output_dir)
            q_success += 1
        except Exception as e:
            print(f"Exception: {e} for Youtube ID: {yt_id}")
            q_fail += 1
            # Write the exception to the logs file
            with open(output_log_path, "a", encoding="utf-8") as logs_f:
                logs_f.write(f"Exception: {e} for Youtube ID: {yt_id}\n")
        if (i + 1) % 1000 == 0:
            print(f"{i+1:,}/{len(yt_id):,} Youtube URLs' metadata is processed.")
    print(f"{q_success:>8} Youtube URLs' metadata is successfully downloaded.")
    print(f"{q_fail:>8} Youtube URLs' metadata failed.")
    print(f"Total time: {seconds_to_dhms(time.monotonic() - t0)}")
    print("Done!")


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "input_txt", type=str, help="Path to the text file that contains Youtube URLS."
    )
    parser.add_argument(
        "output_dir", type=str, help="Directory to download the metadata files."
    )
    args = parser.parse_args()

    # Read the Youtube IDs from input_txt and download the metadata
    main(args.input_txt, args.output_dir)
