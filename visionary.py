import logging
from pathlib import Path
import platform
import sys
from typing import Any, Union

import ffmpeg
from ffmpeg.nodes import FilterableStream

if platform.system == "Windows":
    MEDIA_PATH = "E:\\Movies"
else:
    MEDIA_PATH = "/Users/akash/Downloads/Media"
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
            msg = (
                f"Filename: {media_file_path.name}. Unable to parse."
                f" Reason: {type(exp).__name__} - {exp}."
            )
            LOGGER.error(msg)
    return media_files


def update_stats(stats: dict):
    pass


def get_best_vid_stream(path: Path, media_info: dict[str, Any]):
    video_streams = [
        stream for stream in media_info["streams"] if stream["codec_type"] == "video"
    ]
    if len(video_streams) == 0:
        msg = f"Filename: {path}. No video stream found."
        LOGGER.error(msg)
        return

    eng_vid_streams = list(
        filter(
            lambda x: x.get("tags", {}).get("language", "") == "eng",
            video_streams,
        )
    )
    if len(eng_vid_streams) == 0:
        msg = f"Filename: {path}. No english video stream found."
        LOGGER.error(msg)
        return

    eng_dv_vid_streams = []
    for eng_vid_stream in eng_vid_streams:
        dv_cfg = eng_vid_stream.get("side_data_list", [])
        for cfg in dv_cfg:
            if cfg.get("side_data_type", "") == "DOVI configuration record":
                eng_dv_vid_streams.append(eng_vid_stream)
                break
    if len(eng_dv_vid_streams) == 0:
        msg = f"Filename: {path}. No english DV video stream found."
        LOGGER.error(msg)
        return
    best_vid_stream = sorted(
        eng_dv_vid_streams, key=lambda x: int(x["tags"].get("NUMBER_OF_BYTES", 0))
    )
    return best_vid_stream[0]


def get_best_aud_stream(path: Path, media_info: dict[str, Any]):
    audio_streams = [
        stream for stream in media_info["streams"] if stream["codec_type"] == "audio"
    ]
    if len(audio_streams) == 0:
        msg = f"Filename: {path}. No audio stream found."
        LOGGER.error(msg)
        return

    eng_aud_streams = list(
        filter(
            lambda x: x.get("tags", {}).get("language", "") == "eng",
            audio_streams,
        )
    )
    if len(eng_aud_streams) == 0:
        msg = f"Filename: {path}. No english audio stream found."
        LOGGER.error(msg)
        return
    best_aud_stream = sorted(
        eng_aud_streams, key=lambda x: int(x["tags"].get("NUMBER_OF_BYTES", 0))
    )
    return best_aud_stream[0]


def get_best_sub_stream(path: Path, media_info: dict[str, Any]):
    sub_streams = [
        stream for stream in media_info["streams"] if stream["codec_type"] == "subtitle"
    ]
    if len(sub_streams) == 0:
        msg = f"Filename: {path}. No subtitle stream found."
        LOGGER.error(msg)
        return

    eng_sub_streams = list(
        filter(
            lambda x: x.get("tags", {}).get("language", "") == "eng",
            sub_streams,
        )
    )
    if len(eng_sub_streams) == 0:
        msg = f"Filename: {path}. No english subtitle stream found."
        LOGGER.error(msg)
        return
    best_sub_stream = sorted(
        eng_sub_streams, key=lambda x: int(x["tags"].get("NUMBER_OF_BYTES", 0))
    )
    return best_sub_stream[0]


def mkv_to_mp4(path: Path, media_info: dict[str, Any]):
    best_vid_stream = get_best_vid_stream(path, media_info)
    best_aud_stream = get_best_aud_stream(path, media_info)
    best_sub_stream = get_best_sub_stream(path, media_info)

    in_path = str(path.resolve())
    vid_out_path = str(path.resolve().with_suffix(".hevc"))
    vid_map = f"0:{best_vid_stream['index']}"
    aud_out_path = str(path.resolve().with_suffix(".eac3"))
    aud_map = f"0:{best_aud_stream['index']}"

    inp = ffmpeg.input(in_path)

    vid_out = ffmpeg.output(inp, vid_out_path, c="copy", map=vid_map)
    aud_out = ffmpeg.output(inp, aud_out_path, c="copy", map=aud_map)

    ffmpeg.run(vid_out, overwrite_output=True)
    ffmpeg.run(aud_out, overwrite_output=True)


def main():
    media_files = get_media_files(MEDIA_PATH)
    LOGGER.info(f"Number of files: {len(media_files)}.")
    if len(media_files) == 0:
        msg = "No files to process. Exiting."
        LOGGER.error(msg)
        return

    for path, media_info in media_files.items():
        mkv_to_mp4(path, media_info)


if __name__ == "__main__":
    main()
