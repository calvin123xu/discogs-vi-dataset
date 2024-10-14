# Re-create Discogs-VI and Discogs-VI-YT

Here we explain in detail how to re-create the Discogs-VI and Discogs-VI-YT datasets using a monthly Discogs dump.

* [Download the latest Discogs dump](#download-the-latest-discogs-dump)
* [Re-create Discogs-VI](#re-create-discogs-vi)
* [Re-create Discogs-VI-YT](#re-create-discogs-vi-yt)
* [Prepare the streamlit demo](#prepare-the-streamlit-demo)
* [Split to Train, Validation, and Test Partitions](#split-to-train-validation-and-test-partitions)

## Download the latest Discogs dump

Download the latest [Discogs release dump](https://data.discogs.com). The Discogs database is growing and we can expect to build an even larger dataset using more recent dumps.

```bash
# create a folder for the metadata
mkdir -p data/discogs_metadata/
cd data/discogs_metadata/

wget https://discogs-data-dumps.s3-us-west-2.amazonaws.com/data/2024/discogs_20240701_releases.xml.gz
wget https://discogs-data-dumps.s3-us-west-2.amazonaws.com/data/2024/discogs_20240701_artists.xml.gz

# Unzip the files
gunzip discogs_20240701_releases.xml.gz
gunzip discogs_20240701_artists.xml.gz
```

## Re-create Discogs-VI

If you are interested, each step of creating Discogs-VI from the downloaded dumps are described in the remainder of this section. Instead, you can use `prepare_discogs_vi.sh` and the whole process will be automated.

```bash
./prepare_discogs_vi.sh data/discogs_metadata/discogs_20240701_releases.xml data/discogs_metadata/discogs_20240701_artists.xml 1
```

### Preprocess the dump files

Parse the XML files, pre-process, and convert to JSON. You can run these two scripts in parallel, i.e. they do not depend on each other and `discogs_20240701_releases.xml` takes a long time to process. The prepocessing will prepare and unify the fields and remove metadata that are irrelevant to the task.

```bash
$ python discogs_vi/preprocess_releases_xml.py discogs_20240701_releases.xml
> Processed 17,402,065 releases
>                    3 releases skipped due to errors
> Total processing time: 03:16:55
> Done!

$ python discogs_vi/preprocess_artists_xml.py discogs_20240701_artists.xml
>  9,187,518 artists loaded
> Total processing time: 00:06:10
```

### Clean the artist metadata

There are problems related to artist IDs and relationships. In order to deal with them we clean the artists file.

```bash
python discogs_vi/clean_artists.py discogs_20240701_artists.xml.json
```

### Clean the release metadata

Clean the release metadata by:

* Deleting the tracks without extraartist information,
* Keeping extra artist information only related to the writers and featuring,
* Deleting release and track artist, extraartist duplicates,
* Filter out tracks with more than 4 artists or featuring artists. (This is done to simplify the Youtube search.)
* Checking [genre-style annotation consistency](#genre-style-matching-errors),
* Formatting the metadata,

After cleaning the metadata of a release, if no track is left with the necessary information, we discard the release.

We also remove tracks with

* "various" or "unkown" artists,
* "untitled", "intro", "outro" titles,
* "Non-Music", "Stage & Screen" genres.

```bash
$ python discogs_vi/clean_releases.py discogs_20240701_releases.xml.json
> 17,402,065 releases are processed in total.
>  2,484,508 releases remain after cleaning.
> 14,407,815 tracks remain after cleaning.
>    174,958 genre-style matching errors found.
> Total processing time: 00:12:59
Done!
```

### Genre-style matching errors

Genre-styles matching errors occur when a style does not correspond to any genre associated with the same release according to the genre taxonomy. These errors aren't very common in the database and they appear to happen due to historical changes in the Discogs taxonomy. We discard such genre-style annotations.

### Parse the releases to tracks

In order to put the tracks in clique relationships we need to parse the releases to tracks. Each track will be a dictionary with the following fields:

```json
{
    "track_title": ...,
    "release_title": ...,
    "track_writer_ids": ...,
    "track_writer_names": ...,
    "track_artist_ids": ...,
    "track_artist_names": ...,
    "track_feat_ids": ...,
    "track_feat_names": ...,
    "release_id": ...,
    "release_artist_ids": ...,
    "release_artist_names": ...,
    "release_writer_ids": ...,
    "release_writer_names": ...,
    "release_feat_ids": ...,
    "release_feat_names": ...,
    "genres": ...,
    "styles": ...,
    "country": ...,
    "labels": ...,
    "formats": ...,
    "master_id": ...,
    "main_release": ...,
    "release_videos": ...,
    "released": ...,
}
```

```bash
$ python discogs_vi/parse_releases_to_tracks.py discogs_20240701_releases.xml.json.clean
> Parsed 2,484,508 releases to 14,389,443 tracks.
> Processing time: 13:40
> Done!
```

### Put tracks into cliques

A clique is a collection of music performances that are realizations of the same composition. Using writer information we put the parsed tracks into clique relationships where each clique has a unique UUID. Currently 2 tracks can be in a clique relationship only if they have exactly the same title. The unique elements of a clique are called versions. Since the Discogs dump contains different releases of the same track, we group the tracks that are exactly the same into versions.

A clique will be of the form,

```json
{
    "clique_id": uuid,
    "versions": [
        {"version_id": version_id,
         "tracks": [track0, track1, ...]},
        {}, ...
    ]
}
```

where the tracks have the form as in the previous section. An example clique is provided in `examples/example_clique.json`

```bash
python discogs_vi/clique_finder.py discogs_20240701_releases.xml.json.clean.tracks
>   348,796 cliques are versioned into 1,911,611 versions with  8,038,309 tracks.
> Finished the search.
> Done!
```

You have created the Discogs-VI dataset and you are ready to match the versions to YouTube URLs. By default the file will be named `Discogs-VI-20240701.jsonl`

## Re-create Discogs-VI-YT

In this part our goal is to match the versions in `Discogs-VI-20240701.jsonl` to youtube IDs. We do this in 2 main steps and then post-process it.

**NOTE**: We download the audio files as mono, with 44,100 Hz sampling rate in AAC format. This took 1.8 TB of disk space. In many Version Identification systems, the audio is downsampled to 16,000 or 22,050 Hz. While training Discogs-VINet, we downsampled these files to 16,000 Hz on-the-fly.

### Search versions in Youtube

In this step we search for each version in Youtube by creating queries and storing them. Use the following command to create query strings for the unmatched versions.

```bash
python discogs_vi_yt/query_yt/prepare_query_string.py Discogs-VI-20240701.jsonl
```

Once you have the query strings ready, make a youtube query for each string and store top 5 results' metadata. You can parallelize this step. There are **many** queries to make and time is of the essence, therefore we split the queries into multiple parts and make the queries for each part in parallel. We used 16 processes but this many processes may get you banned from Youtube.

```bash
utilities/shuffle_and_split.sh Discogs-VI-20240701.jsonl.queries 16
```

Then for each part of the split you should use the below command in a separate terminal session (e.g. with TMUX).

```bash
python discogs_vi_yt/query_yt/query_and_download_yt_metadata.py Discogs-VI-20240701.jsonl.queries.split.00 <metadata_dir>
```

Once all the metadata is downloaded, now we can search for the versions inside this metadata collection.

```bash
python discogs_vi_yt/query_yt/search_tracks_in_queried_yt_metadata.py Discogs-VI-20240701.jsonl <metadata_dir>
```

### Download the matched version audio

After the matching you need to download the matched audio.

```bash
python discogs_vi_yt/audio_download_yt/download_missing_version_youtube_urls.py Discogs-VI-20240701.jsonl.youtube_query_matched music_dir/
```

### Post-process the dataset

In this step we check if each video is downloaded and remove the versions without a downloaded video. Then, betweeen the different versions of a same clique that are matched to the same Youtube URL are removed also. Finally, any clique with less than two versions are deleted.

```bash
python discogs_vi_yt/post_processing.py Discogs-VI-20240701.jsonl.youtube_query_matched music_dir/
```

This will create `Discogs-VI-YT-20240701.jsonl` and `Discogs-VI-YT-20240701-light.json`.

Since the Discogs-VI-YT has a large size and occupies a lot of memory, we create `Discogs-VI-YT-20240701-light.json` that only contains:

* Clique ID
* Version ID
* All Youtube URLs for each version.

`Discogs-VI-YT-20240701-light.json` is a JSON file with the default encoding.

Congratulations, you are almost done!

**NOTE**: You will have less versions in the dataset than the downloaded music because of the post processing. You can move these extra files to a directory above with: `notebooks/file.ipynb`

## Prepare the streamlit demo

Once you have the dataset, you can use the streamlit demo to visualize the cliques. But first we have to do preprocesesing by removing some redundant information to reduce the memory load.

```bash
python utils/prepare_demo.py Discogs-VI-YT-20240701.jsonl
```

## Create Train, Validation, and Test Splits

We first find the intersections of our dataset and other datasets' test sets and then partition our data acordingly.

### Intersections With Da-TACOS and SHS100K

Since Da-TACOS Train set is not public we do not work with it. We only find the intersections between Da-TACOS Benchmark set and Discogs-VI-YT. For SHS100K we used the metadata in <https://github.com/NovaFrost/SHS100K2>. We find out which cliques in Da-TACOS benchmark and SHS100K-Test sets are contained in Discogs-VI-YT by using a jupyter notebook `discogs_vi_yt/partition/datacos_shs100k.ipynb`. This will create a line separated text file of the clique IDs called `data/Discogs-VI-20240701-DaTACOS_benchmark-SHS100K2_TEST-lost_cliques.txt`

We use Discogs-VI first instead of Discogs-VI-YT since it contains more cliques.

We use the following jupyter notebook `discogs_vi_yt/partition/datacos_shs100k.ipynb` for this step.

Let $S =$ ( Discogs-VI $\cap$ Da-TACOS benchmark ) $\cup$ ( Discogs-VI $\cap$ SHS100K-Test )

Remember that Discogs-VI-YT $\subset$ Discogs-VI $\implies$ $S \subset $ Discogs-VI-YT. For simplicity we use $S' = S \cup$ Discogs-VI-YT. That is, we will put all the cliques in $S'$ to our test partition.

### Split to Train, Validation, and Test Partitions

For this step we use a jupyter notebook `discogs_vi_yt/partition/create_splits.ipynb`. Follow the instructions there.

1. We use the clique IDs (`data/Discogs-VI-20240701-DaTACOS_benchmark-SHS100K2_TEST-lost_cliques.txt`) obtained in [step](#intersections-with-da-tacos-and-shs100k) and put the corresponding cliques into Discogs-VI-YT-Light-Test first.
1. Then we sample additional cliques into Discogs-VI-YT-Light-Test set.
1. Then we sample cliques for the Discogs-VI-YT-Light-Val set.
1. The remaining cliques are for the Discogs-VI-YT-Light-Train set.

You are done!
