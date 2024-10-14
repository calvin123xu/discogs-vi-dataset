"""Takes a line separated text file that contains queries and searches YouTube 
for each query. N=5 results per query is returned. The results are written to a 
json file and the query is mapped to the UUID in a separate json file. The 
directory is named with the first two characters of the UUID. This is done to 
avoid having too many files in a single directory."""

import os
import time
import json
import uuid
import argparse

from utils_query import select_fields, seconds_to_dhms

import yt_dlp

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


def main(input_txt, output_dir, N=5):

    # Read the queries from the input text file
    with open(input_txt, encoding="utf-8") as in_f:
        queries = in_f.read().splitlines()
    print(f"{len(queries):,} queries loaded.")

    # Set the mapping json path
    mapping_json = os.path.join(output_dir, "query_id-mapping.json")
    if os.path.exists(mapping_json):
        print("Skipping the queries that are already done...")
        completed_queries = set()
        with open(mapping_json, encoding="utf-8") as in_f:
            for jline in in_f:
                mapping = json.loads(jline)
                completed_queries.update({mapping["query"]})
        # Get the queries that are not done yet
        queries = [q for q in queries if q not in completed_queries]
        print(f"{len(queries):,} queries remaining.")

    # Search YouTube for each query
    print(f"Searching YouTube for {len(queries):,} queries...")
    t0 = time.monotonic()
    q_success, q_fail = 0, 0
    for i, query in enumerate(queries):
        try:
            # Make the YouTube query
            with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
                search_results = ydl.extract_info(
                    f"ytsearch{N}:{query}", download=False
                )  # Do not download the video
                search_results = ydl.sanitize_info(search_results)
        except Exception as e:
            print(f"Exception: {repr(e)} for query: {query}")
            q_fail += 1
            continue
        # Select the fields that we are interested in
        search_results["entries"] = [
            select_fields(entry) for entry in search_results["entries"]
        ]
        # Do not keep bad youtube_ids:
        search_results["entries"] = [
            entry
            for entry in search_results["entries"]
            if len(entry["id"]) == 11 and entry["id"] != "M5t4UHllkUM"
        ]
        # If there are no results for the query skip it
        if len(search_results["entries"]) == 0:
            print(f"No results for query: {query}")
            q_fail += 1
            continue
        # For each successful query assign a UUID
        query_id = str(uuid.uuid4())
        # Create a directory for the query convention is the first two characters of the UUID
        query_dir = os.path.join(output_dir, query_id[:2])
        os.makedirs(query_dir, exist_ok=True)
        # Write the results to a json file
        output_path = os.path.join(query_dir, query_id + ".json")
        with open(output_path, "w", encoding="utf-8") as out_f:
            json.dump(search_results, out_f, ensure_ascii=False)
        # Append the mapping to the json file
        mapping = {"uuid": query_id, "query": query}
        with open(mapping_json, "a", encoding="utf-8") as out_f:
            out_f.write(json.dumps(mapping, ensure_ascii=False) + "\n")
        print(
            f"{json.dumps(mapping, ensure_ascii=False, indent=4)} successfully written.\n"
        )
        q_success += 1
        if (i + 1) % 1000 == 0:
            print(f"{i+1:,}/{len(queries):,} queries completed.")
    print("=" * 60)
    print(
        f"Completed {len(queries):,} queries in: {seconds_to_dhms(time.monotonic() - t0)}."
    )
    print(f"Successfully completed: {q_success:,} queries.")
    print(f"Failed to complete: {q_fail:,} queries.")
    print("=" * 60)


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "input_txt",
        type=str,
        help="Path to the text file that contains the the line separated queries.",
    )
    parser.add_argument(
        "output_dir", type=str, help="Directory to download the metadata."
    )
    parser.add_argument(
        "--N", type=int, default=5, help="Number of search results to return per query."
    )
    args = parser.parse_args()

    main(args.input_txt, args.output_dir, N=args.N)

    #############
    print("Done!")
