import logging
import json
from pathlib import Path
import platform
import sys
from typing import Any, Union

import ffmpeg

from utils import file_size


if platform.system == "Windows":
    MEDIA_PATH = "E:\\Movies"
else:
    # MEDIA_PATH = "/Volumes/Etmnt/Movies"
    MEDIA_PATH = "/Users/akash/Downloads/Media"

STATS_PATH = "visionary_stat.json"
LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
LOGGER.addHandler(logging.StreamHandler(sys.stdout))

FILE_EXT = [
    # "mp4",
    "mkv",
]


def get_media_files(path: Union[Path, str]):
    media_file_paths = [
        fpath for ext in FILE_EXT for fpath in Path(path).rglob(f"*.{ext}")
    ]

    media_files: dict[Path, Any] = {}
    for media_file_path in media_file_paths:
        try:
            media_files[media_file_path] = ffmpeg.probe(media_file_path)
            json.dump(media_files[media_file_path], open(STATS_PATH, "w"), indent=2)
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
        msg = f"Filename: {path.name}. No video stream found."
        LOGGER.error(msg)
        return

    dv_streams = []
    for dv_stream in video_streams:
        dv_cfg = dv_stream.get("side_data_list", [])
        for cfg in dv_cfg:
            if cfg.get("side_data_type", "") == "DOVI configuration record":
                dv_streams.append(dv_stream)
                break
    if len(dv_streams) == 0:
        msg = f"Filename: {path.name}. No DV video stream found."
        LOGGER.debug(msg)
        return

    eng_dv_streams = []
    for dv_stream in dv_streams:
        lang = dv_stream.get("tags", {}).get("language", "")
        if lang == "eng":
            eng_dv_streams.append(dv_stream)
    if len(eng_dv_streams) == 0:
        msg = f"Filename: {path.name}. No english video stream found. Using all DV Streams."
        LOGGER.debug(msg)
        eng_dv_streams = dv_streams

    best_vid_stream = sorted(
        dv_streams, key=lambda x: int(x["tags"].get("NUMBER_OF_BYTES", 0))
    )
    return best_vid_stream[-1]


def get_best_aud_stream(path: Path, media_info: dict[str, Any]):
    audio_streams = [
        stream for stream in media_info["streams"] if stream["codec_type"] == "audio"
    ]
    if len(audio_streams) == 0:
        msg = f"Filename: {path.name}. No audio stream found."
        LOGGER.error(msg)
        return
    eng_aud_streams = list(
        filter(
            lambda x: x.get("tags", {}).get("language", "") == "eng",
            audio_streams,
        )
    )
    if len(eng_aud_streams) == 0:
        msg = f"Filename: {path.name}. No english audio stream found."
        LOGGER.debug(msg)
        return
    best_aud_stream = sorted(
        eng_aud_streams, key=lambda x: int(x["tags"].get("NUMBER_OF_BYTES", 0))
    )
    return best_aud_stream[-1]


def get_best_sub_stream(path: Path, media_info: dict[str, Any]):
    sub_streams = [
        stream for stream in media_info["streams"] if stream["codec_type"] == "subtitle"
    ]
    if len(sub_streams) == 0:
        msg = f"Filename: {path.name}. No subtitle stream found."
        LOGGER.debug(msg)
        return

    eng_sub_streams = list(
        filter(
            lambda x: x.get("tags", {}).get("language", "") == "eng",
            sub_streams,
        )
    )
    if len(eng_sub_streams) == 0:
        msg = f"Filename: {path.name}. No english subtitle stream found."
        LOGGER.debug(msg)
        return
    best_sub_stream = sorted(
        eng_sub_streams, key=lambda x: int(x["tags"].get("NUMBER_OF_BYTES", 0))
    )
    return best_sub_stream[-1]


def get_dv_profile(stream: dict):
    dv_cfg = stream.get("side_data_list", [])
    for cfg in dv_cfg:
        if "dv_profile" in cfg:
            return cfg["dv_profile"]


def mkv_to_mp4(path: Path, media_info: dict[str, Any]):
    best_vid_stream = get_best_vid_stream(path, media_info)
    best_aud_stream = get_best_aud_stream(path, media_info)
    best_sub_stream = get_best_sub_stream(path, media_info)

    if best_vid_stream is None:
        return
    else:
        msg = (
            f"Filename: {path.name}.Size: {file_size(path)}."
            " Processing DV stream in MKV container."
        )
        LOGGER.info(msg)

    in_path = str(path.resolve())
    inp = ffmpeg.input(in_path)
    inp_vid = inp[str(best_vid_stream["index"])]
    inp_aud = inp[str(best_aud_stream["index"])]
    inp_sub = inp[str(best_sub_stream["index"])]

    vid_out_path = str(Path(path.parent, f"{path.stem}_REQ{path.suffix}"))
    vid_out = ffmpeg.output(
        inp_vid,
        inp_aud,
        inp_sub,
        vid_out_path,
        c="copy",
        **{"metadata:s:v:0": "language=eng"},
    )
    vid_out.run(quiet=True, overwrite_output=True)

    # if best_vid_stream is not None:
    #     if get_dv_profile(best_vid_stream) in ["5", "8"]:
    #         vid_out_path = str(path.resolve().with_name("BL_RPU").with_suffix(".hevc"))
    #         kwargs = {"vbsf": "hevc_mp4toannexb", "f": "hevc"}
    #     # else:
    #     #     vid_out_path = str(path.resolve().with_suffix(".hevc"))
    #     #     kwargs = {"vbsf": "hevc_mp4toannexb", "f": "hevc"}
    #     vid_map = f"0:{best_vid_stream['index']}"
    #     vid_out = ffmpeg.output(inp, vid_out_path, c="copy", map=vid_map, **kwargs)
    #     ffmpeg.run(vid_out, quiet=True, overwrite_output=True)

    # if best_aud_stream is not None:
    #     aud_out_path = str(path.resolve().with_suffix(".eac3"))
    #     aud_map = f"0:{best_aud_stream['index']}"
    #     aud_out = ffmpeg.output(inp, aud_out_path, c="copy", map=aud_map)
    #     ffmpeg.run(aud_out, quiet=True, overwrite_output=True)

    # if best_sub_stream is not None:
    #     sub_out_path = str(path.resolve().with_suffix(".srt"))
    #     sub_map = f"0:{best_sub_stream['index']}"
    #     sub_out = ffmpeg.output(inp, sub_out_path, c="copy", map=sub_map)
    #     ffmpeg.run(sub_out, quiet=True, overwrite_output=True)


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
