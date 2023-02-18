from __future__ import annotations
import json
import os

import sys
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Union
from typing_extensions import Self

import ffmpeg

from visionary.utils import get_file_size


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
        fpath for ext in FILE_EXT for fpath in Path(path).rglob(f"*{os.extsep}{ext}")
    ]

    media_files = []
    for media_file_path in media_file_paths:
        try:
            media_file = MediaFile(media_file_path, ffmpeg.probe(media_file_path))
            media_files.append(media_file)
        except ffmpeg.Error as exp:
            msg = (
                f"Filename: {media_file_path.name}. Unable to parse."
                f" Reason: {type(exp).__name__} - {exp}."
            )
            LOGGER.error(msg)
    return media_files


@dataclass
class Stream:
    alias = {}

    index: int
    stream_size: int

    codec_name: str
    codec_long_name: str
    codec_type: str
    codec_tag_string: str
    codec_tag: str

    language: Optional[str]

    def __init__(
        self,
        index: int,
        codec_name: str,
        codec_long_name: str,
        codec_type: str,
        codec_tag_string: str,
        codec_tag: str,
        language: str | None = None,
        **kwargs,
    ) -> None:
        self.index = index
        self.stream_size = int(kwargs.get("tags", {}).get("NUMBER_OF_BYTES", 0))

        self.codec_name = codec_name
        self.codec_long_name = codec_long_name
        self.codec_type = codec_type
        self.codec_tag_string = codec_tag_string
        self.codec_tag = codec_tag
        self.language = language

    @classmethod
    def from_json(cls, **kwargs) -> Self:
        kwarg_dict = kwargs.copy()
        for field, alias in cls.alias.items():
            if field not in kwargs:
                if alias in kwargs:
                    kwarg_dict[field] = kwargs[alias]
                else:
                    kwarg_dict[field] = None
        return cls(**kwarg_dict)


@dataclass
class VidStream(Stream):

    alias = {
        "aspect_ratio": "display_aspect_ratio",
    }

    aspect_ratio: str
    is_dv: bool

    def __init__(
        self,
        index: int,
        codec_name: str,
        codec_long_name: str,
        codec_type: str,
        codec_tag_string: str,
        codec_tag: str,
        aspect_ratio: str,
        language: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(
            index,
            codec_name,
            codec_long_name,
            codec_type,
            codec_tag_string,
            codec_tag,
            language,
        )

        self.aspect_ratio = aspect_ratio
        self.is_dv = False

        dv_cfg = kwargs.get("side_data_list", [])
        for cfg in dv_cfg:
            if cfg.get("side_data_type", "") == "DOVI configuration record":
                self.is_dv = True
                break


@dataclass
class AudStream(Stream):

    sample_rate: str
    is_atmos: bool

    def __init__(
        self,
        index: int,
        codec_name: str,
        codec_long_name: str,
        codec_type: str,
        codec_tag_string: str,
        codec_tag: str,
        sample_rate: str,
        language: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(
            index,
            codec_name,
            codec_long_name,
            codec_type,
            codec_tag_string,
            codec_tag,
            language,
        )

        self.sample_rate = sample_rate
        self.is_atmos = codec_name.lower() in ["eac3"]


@dataclass
class SubStream(Stream):
    def __init__(
        self,
        index: int,
        codec_name: str,
        codec_long_name: str,
        codec_type: str,
        codec_tag_string: str,
        codec_tag: str,
        language: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(
            index,
            codec_name,
            codec_long_name,
            codec_type,
            codec_tag_string,
            codec_tag,
            language,
        )


@dataclass
class MediaFile:

    path: Path
    name: str
    ext: str
    size: str
    stream_count: int

    videos: list[VidStream]
    dv_videos: list[VidStream]
    best_vid: VidStream
    has_video: bool
    has_dv: bool

    audios: list[AudStream]
    atmos: list[AudStream]
    best_aud: AudStream
    has_audio: bool
    has_atmos: bool

    subs: list[SubStream]
    has_subs: bool

    def __init__(self, path: Path, media_info: dict[str, Any]) -> None:
        self.path = path
        split = path.name.split(os.extsep)
        self.name, self.ext = "".join(split[:-1]), split[-1]
        self.size = get_file_size(path)

        self.videos = self._get_video_streams(media_info)
        self.dv_videos = [vid for vid in self.videos if vid.is_dv]
        self.best_vid = self._get_best_vid_stream(self.dv_videos or self.videos)
        self.has_video = len(self.videos) > 0
        self.has_dv = len(self.dv_videos) > 0

        self.audios = self._get_audio_streams(media_info)
        self.atmos = [aud for aud in self.audios if aud.is_atmos]
        self.best_aud = self._get_best_aud_stream(self.atmos or self.audios)
        self.has_audio = len(self.audios) > 0
        self.has_atmos = len(self.atmos) > 0

        self.subs = self._get_sub_streams(media_info)
        self.has_subs = len(self.subs) > 0

        self.stream_count = len(self.videos)

    @staticmethod
    def _get_video_streams(info: dict[str, Any]) -> list[VidStream]:
        return [
            VidStream.from_json(**stream)
            for stream in info["streams"]
            if stream["codec_type"] == "video"
        ]

    @staticmethod
    def _get_best_vid_stream(vid_streams: list[VidStream]) -> VidStream:
        eng_dv_streams = []
        for dv_stream in vid_streams:
            if dv_stream.language == "eng":
                eng_dv_streams.append(dv_stream)
        if len(eng_dv_streams) == 0:
            eng_dv_streams = vid_streams

        best_vid_stream = sorted(eng_dv_streams, key=lambda x: x.stream_size)
        return best_vid_stream[-1]

    @staticmethod
    def _get_audio_streams(info: dict[str, Any]):
        return [
            AudStream.from_json(**stream)
            for stream in info["streams"]
            if stream["codec_type"] == "audio"
        ]

    @staticmethod
    def _get_best_aud_stream(aud_streams: list[AudStream]) -> AudStream:
        eng_aud_streams = []
        for aud_stream in aud_streams:
            if aud_stream.language == "eng":
                eng_aud_streams.append(aud_stream)
        if len(eng_aud_streams) == 0:
            eng_aud_streams = aud_streams

        best_aud_stream = sorted(eng_aud_streams, key=lambda x: x.stream_size)
        return best_aud_stream[-1]

    @staticmethod
    def _get_sub_streams(info: dict[str, Any]):
        return [
            SubStream.from_json(**stream)
            for stream in info["streams"]
            if stream["codec_type"] == "subtitle"
        ]


# def get_best_aud_stream(path: Path, media_info: dict[str, Any]):
#     audio_streams = [
#         stream for stream in media_info["streams"] if stream["codec_type"] == "audio"
#     ]
#     if len(audio_streams) == 0:
#         msg = f"Filename: {path.name}. No audio stream found."
#         LOGGER.error(msg)
#         return
#     eng_aud_streams = list(
#         filter(
#             lambda x: x.get("tags", {}).get("language", "") == "eng",
#             audio_streams,
#         )
#     )
#     if len(eng_aud_streams) == 0:
#         msg = f"Filename: {path.name}. No english audio stream found."
#         LOGGER.debug(msg)
#         return
#     best_aud_stream = sorted(
#         eng_aud_streams, key=lambda x: int(x["tags"].get("NUMBER_OF_BYTES", 0))
#     )
#     return best_aud_stream[-1]


# def get_best_sub_stream(path: Path, media_info: dict[str, Any]):
#     sub_streams = [
#         stream for stream in media_info["streams"] if stream["codec_type"] == "subtitle"
#     ]
#     if len(sub_streams) == 0:
#         msg = f"Filename: {path.name}. No subtitle stream found."
#         LOGGER.debug(msg)
#         return

#     eng_sub_streams = list(
#         filter(
#             lambda x: x.get("tags", {}).get("language", "") == "eng",
#             sub_streams,
#         )
#     )
#     if len(eng_sub_streams) == 0:
#         msg = f"Filename: {path.name}. No english subtitle stream found."
#         LOGGER.debug(msg)
#         return
#     best_sub_stream = sorted(
#         eng_sub_streams, key=lambda x: int(x["tags"].get("NUMBER_OF_BYTES", 0))
#     )
#     return best_sub_stream[-1]


# def get_dv_profile(stream: dict):
#     dv_cfg = stream.get("side_data_list", [])
#     for cfg in dv_cfg:
#         if "dv_profile" in cfg:
#             return cfg["dv_profile"]


def mkv_to_mp4(media_file: MediaFile):
    path = media_file.path
    in_path = str(path.resolve())
    inp = ffmpeg.input(in_path)
    inp_vid = inp[str(media_file.best_vid.index)]
    inp_aud = inp[str(media_file.best_aud.index)]
    # inp_sub = inp[str(best_sub_stream["index"])]

    # vid_out_path = str(Path(path.parent, f"{path.stem}_REQ{path.suffix}"))
    # vid_out = ffmpeg.output(
    #     inp_vid,
    #     inp_aud,
    #     vid_out_path,
    #     c="copy",
    #     **{"metadata:s:v:0": "language=eng", "metadata:s:a:0": "language=eng"},
    # )
    # # print(vid_out.compile())
    # vid_out.run(quiet=True, overwrite_output=True)

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

    if media_file.best_aud is not None:
        aud_out_path = str(media_file.path.resolve().with_suffix(".eac3"))
        aud_map = f"0:{media_file.best_aud.index}"
        aud_out = ffmpeg.output(inp, aud_out_path, c="copy", map=aud_map)
        ffmpeg.run(aud_out, quiet=True, overwrite_output=True)

    # if best_sub_stream is not None:
    #     sub_out_path = str(path.resolve().with_suffix(".srt"))
    #     sub_map = f"0:{best_sub_stream['index']}"
    #     sub_out = ffmpeg.output(inp, sub_out_path, c="copy", map=sub_map)
    #     ffmpeg.run(sub_out, quiet=True, overwrite_output=True)


# def main():
#     media_files = get_media_files(MEDIA_PATH)
#     LOGGER.info(f"Number of files: {len(media_files)}.")
#     if len(media_files) == 0:
#         msg = "No files to process. Exiting."
#         LOGGER.error(msg)
#         return

#     for path, media_info in media_files.items():
#         mkv_to_mp4(path, media_info)


# if __name__ == "__main__":
#     main()
