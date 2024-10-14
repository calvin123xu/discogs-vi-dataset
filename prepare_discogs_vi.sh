#!/bin/bash

#########################################################################################

if [ $# == 0 ]; then
    echo "Description: This script prepares the Discogs-VI dataset from a monthly Discogs
    Dump.
            Example: resample.sh release_xml/ artist_xml/"
    echo "Usage: $0 param1 param2"
    echo "param1: release_xml path"
    echo "param2: artist_xml path"
    echo "param3: preprocess: 1 for preprocess xml files and 0 for not. If you previously 
        preprocessed the xml files, set this to 0."
    exit 0
fi

#########################################################################################

release_xml=$1
artist_xml=$2

release="$release_xml.jsonl"
artist="$artist_xml.jsonl"

clean_artist="$artist.clean"
clean_release="$release.clean"
tracks="$clean_release.tracks"

#########################################################################################

if [ $3 == 1 ]; then
    echo "Preprocessing xml files..."
    python discogs_vi/preprocess_artists_xml.py $artist_xml
    python discogs_vi/preprocess_releases_xml.py $release_xml
fi
echo

echo "Cleaning the artist metadata..."
python discogs_vi/clean_artists.py $artist
echo

echo "Cleaning the release metadata..."
python discogs_vi/clean_releases.py $release $clean_artist
echo

echo "Parsing releases to tracks..."
python discogs_vi/parse_releases_to_tracks.py $clean_release $clean_artist
echo

echo "Finding the cliques..."
python discogs_vi/clique_finder.py $tracks $clean_artist
echo

echo "Metadata preparation complete."