
import logging
from pathlib import Path
import sys
from typing import Any, Union

import ffmpeg

MEDIA_PATH = "E:\\Movies"
STATS_PATH = "visionary_stat.json"
LOGGER = logging.getLogger()
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(logging.StreamHandler(sys.stdout))


def get_media_files(path: Union[Path, str]):
    mp4_files = [path for path in Path(path).rglob("*.mp4")]
    mkv_files = [path for path in Path(path).rglob("*.mkv")]
    media_file_paths = set(mp4_files + mkv_files)

    media_files: dict[Path, Any] = {}
    for media_file_path in media_file_paths:
        try:
            media_files[media_file_path] = ffmpeg.probe(media_file_path)
        except ffmpeg.Error as exp:
            msg = f"Filename: {media_file_path.name}. Unable to parse."\
                f" Reason: {type(exp).__name__} - {exp}."
            LOGGER.error(msg)
    return media_files


def update_stats(stats: dict):
    pass


def process_file(path: Path, media_info: dict[str, Any]):
    video_stream = next(
        (stream for stream in media_info['streams']
        if stream['codec_type'] == 'video'),
        None
    )
    if video_stream is None:
        msg = f"Filename: {path}. No video stream found."
        LOGGER.error(msg)

    dv_data = video_stream.get("side_data_list")
    if dv_data is None:
        msg = f"Filename: {path}. No DV Data found."
        LOGGER.info(msg)
        return

    in_path = str(path.resolve())
    out_path = str(path.resolve().with_suffix(".hevc"))
    inp = ffmpeg.input(in_path)
    out = ffmpeg.output(inp, out_path, c="copy")
    ffmpeg.run(out)
    # else:
    #     print(dv_data)



def main():
    media_files = get_media_files(MEDIA_PATH)
    LOGGER.info(f"Number of files: {len(media_files)}.")
    if len(media_files) == 0:
        msg = "No files to process. Exiting."
        LOGGER.error(msg)
        return

    for path, media_info in media_files.items():
        if path.name.startswith("Everything"):
            process_file(path, media_info)


if __name__ == '__main__':
    main()
