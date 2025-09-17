"""Takes a line separated Youtube IDs in a text file and attempts to download
each video as an audio file. The output is a tab separated file with the
following columns: Youtube ID, status, output_mp4, output_meta."""

import os
import sys
import json
import time
import csv
import random
import argparse

import yt_dlp as youtube_dl

from fake_useragent import UserAgent  # pip install fake-useragent

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from query_yt.utils_query import get_youtube_url, escape_ansi, seconds_to_dhms

YDL_OPTS = {
    # 140: m4a, audio only, tiny 134k, m4a_dash container, mp4a.40.2@128k (44100Hz)
    "format": "140",
    # Download single video instead of a playlist if in doubt.
    "noplaylist": True,
    #'download_archive': True,
    # Too frequent queries to YouTube can lead to HTTP Error 429: Too Many Requests.
    # You can reduce load by enabling caching and adding a sleep interval.
    #'sleep-interval': 3,
    "source_address": "0.0.0.0",
    # Currently data servers are all blocked. ipv4 fixed it.
    # https://github.com/yt-dlp/yt-dlp/issues/7143
    "force_ipv4": True,
    # 'headers': {
    #     'User-Agent': 'Your User Agent String',
    #     'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    #     'Accept-Language': 'en-US,en;q=0.5',
    #     'Accept-Encoding': 'gzip, deflate',
    #     'Connection': 'keep-alive',
    # }
}

"""
def download_audio_and_metadata(yt_id, root_dir, force_failed=False):
    # See youtube_dl options here:
    # https://github.com/ytdl-org/youtube-dl/blob/master/README.md#embedding-youtube-dl

    url = get_youtube_url(yt_id)

    log_dir = os.path.join(root_dir, "logs")
    audio_dir = os.path.join(root_dir, "audio")

    prefix = yt_id[:2]
    output_mp4 = os.path.join(audio_dir, prefix, f"{yt_id}.mp4")
    output_meta = os.path.join(audio_dir, prefix, f"{yt_id}.meta")
    output_log = os.path.join(log_dir, prefix, f"{yt_id}.log")

    if os.path.exists(output_mp4) and os.path.exists(output_meta):
        status = "file exists"
    elif os.path.exists(output_log) and not force_failed:
        status = "download previously failed"
    else:
        # Output filename.
        YDL_OPTS["outtmpl"] = output_mp4
        with youtube_dl.YoutubeDL(YDL_OPTS) as ydl:
            try:
                ydl.download([url])
                meta = ydl.extract_info(url, download=False)
                meta = ydl.sanitize_info(meta)
                with open(output_meta, "w", encoding="utf-8") as out_f:
                    out_f.write(json.dumps(meta, ensure_ascii=False) + "\n")
                status = "downloaded"

            # TODO TypeError exception should not happen, this is an upstream bug in youtube-dl.
            except (youtube_dl.utils.DownloadError, TypeError) as e:
                status = escape_ansi(str(e))
                if "HTTP Error 429: Too Many Requests" not in status:
                    os.makedirs(os.path.dirname(output_log), exist_ok=True)
                    with open(output_log, "w") as f:
                        f.write(
                            "\t".join((yt_id, output_mp4, output_meta, status)) + "\n"
                        )
                status = "check log"
        del YDL_OPTS["outtmpl"]
    return (yt_id, output_mp4, output_meta, output_log, status)
"""


def download_audio_and_metadata(yt_id, root_dir, force_failed=False):
    url = get_youtube_url(yt_id)
    output_mp4 = os.path.join(root_dir, f"{yt_id}.m4a")
    output_meta = os.path.join(root_dir, f"{yt_id}.json")
    output_log = os.path.join(root_dir, f"{yt_id}.log")

    if os.path.exists(output_mp4) and os.path.exists(output_meta) and not force_failed:
        return (yt_id, output_mp4, output_meta, output_log, "already_downloaded")

    # 生成随机 User-Agent
    ua = UserAgent()
    random_agent = ua.random

    YDL_OPTS = {
        "format": "140",
        "noplaylist": True,
        "force_ipv4": True,
        "quiet": True,
        "outtmpl": output_mp4,
        "ratelimit": 500_000,
        "headers": {"User-Agent": random_agent},  # 设置随机 User-Agent
    }

    max_retries = 1
    status = "failed"

    for attempt in range(1, max_retries + 1):
        try:
            with youtube_dl.YoutubeDL(YDL_OPTS) as ydl:
                ydl.download([url])
                meta = ydl.extract_info(url, download=False)

            with open(output_meta, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)

            status = "downloaded"
            break

        except youtube_dl.utils.DownloadError as e:
            err_msg = str(e)
            if "HTTP Error 429" in err_msg or "HTTP Error 403" in err_msg:
                wait_time = 0
                if max_retries > 1:
                    wait_time = 30 + random.randint(0, 30)
                time.sleep(wait_time)
                continue
            else:
                print(f"[{yt_id}] Fatal error: {err_msg}")
                status = "check log"
                break

        except Exception as e:
            print(f"[{yt_id}] Unexpected error: {e}")
            status = "check log"
            break

    if status != "downloaded":
        with open(output_log, "w", encoding="utf-8") as f:
            f.write(status)

    return (yt_id, output_mp4, output_meta, output_log, status)





def main(input_ids, root_dir, force_failed=False):
    counter = 0
    t0 = time.monotonic()
    with open(input_ids + ".log", "w") as logfile:
        logger = csv.writer(logfile, delimiter="\t")
        for yt_id in open(input_ids, "r"):
            yt_id = yt_id.strip("\n")
            logger.writerow(
                download_audio_and_metadata(yt_id, root_dir, force_failed=force_failed)
            )
              # pause for random time 
            pause = random.uniform(5,10)
            time.sleep(pause)
            counter += 1
            print("=" * 15 + f"Processed {counter:,} ids" + "=" * 15)
    print(f"Total time: {seconds_to_dhms(time.monotonic() - t0)}")


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "input_ids", type=str, help="Youtube IDs file (one ID per line)."
    )
    parser.add_argument(
        "root_dir", type=str, help="Root directory for logs and audio files."
    )
    parser.add_argument(
        "--force-failed",
        "-f",
        action="store_true",
        help="Force download of failed IDs.",
    )
    args = parser.parse_args()

    main(args.input_ids, args.root_dir, force_failed=args.force_failed)
