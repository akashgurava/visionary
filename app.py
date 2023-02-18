import platform

import pandas as pd

import visionary
from visionary.visionary import mkv_to_mp4


if platform.system == "Windows":
    MEDIA_PATH = "E:\\Movies"
else:
    # MEDIA_PATH = "/Volumes/Etmnt/Movies"
    MEDIA_PATH = "/Users/akash/Downloads/Media"

files = visionary.get_media_files(MEDIA_PATH)
df = pd.DataFrame(
    files,
    columns=[
        "name",
        "ext",
        "size",
        "has_dv",
        "has_atmos",
        "has_subs",
    ],
)

cond = (df["ext"] == "mkv") & (df["has_atmos"])

print(df.loc[cond])
mkv_to_mp4(files[0])
