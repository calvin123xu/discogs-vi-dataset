WRITTEN = "written-by"
FEAT = ["ft.", "feat.", "featuring"]

N_MAX_ARTISTS = 4  # Maximum number of artists per track

############ Excluded artsits ############
VARIOUS = "194"
UNKNOWN = "355"
NO_ARTIST = "118760"
ARTIST_WITHOUT_PAGE = "0"

EXCLUDE_ARTISTS = {
    VARIOUS,
    UNKNOWN,
    NO_ARTIST,
    ARTIST_WITHOUT_PAGE,
}

############ Excluded releases ############

EXCLUDE_TITLES = {"untitled", "intro", "outro"}
EXCLUDE_GENRES = {"Non-Music", "Stage & Screen"}

################# Paths #################

TAXONOMY_PATH = "../taxonomy/discogs_taxonomy.json"
