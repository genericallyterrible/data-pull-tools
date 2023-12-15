from __future__ import annotations

import logging
import multiprocessing as mp
from functools import partial
from typing import TYPE_CHECKING

import pandas as pd

from .cache_behavior import CacheBehavior, CacheBehaviorProtocol
from .cacher import DEFAULT_CACHER
from .excel_reader import CachedExcelReader

if TYPE_CHECKING:
    from pathlib import Path

    from pandas import DataFrame

    from .cacher import Cacher
    from .excel_reader import CacheLocation

module_logger = logging.getLogger(__name__)


class ExcelCollector:
    def __init__(
        self,
        input_dir: Path,
        output_file: Path | str,
        sheet_name: int | str | list[int] | list[str] | None = 0,
        glob_pattern: str = "*.xlsx",
        *,
        collection_cacher: Cacher = DEFAULT_CACHER,
        cache_dir: Path | str | None = None,
        cache_location: CacheLocation | None = None,
    ) -> None:
        if isinstance(output_file, str):
            output_file = input_dir / (
                output_file
                if output_file.endswith(".xlsx")
                else (output_file + ".xlsx")
            )

        self.input_dir = input_dir
        self.reader = CachedExcelReader(
            self.input_dir,
            cache_dir,
            cache_location=cache_location,
        )
        self.collection_cacher = collection_cacher
        self.output_file = output_file
        if self.output_file.exists():
            self.out_st_mtime = self.output_file.stat().st_mtime
        self.glob_pattern = glob_pattern
        self.sheet_name = sheet_name

    @property
    def _should_collect(self) -> bool:
        if not self.output_file.exists():
            return True

        for entry in self.input_dir.glob(self.glob_pattern):
            if (
                entry.is_file()
                and entry != self.output_file
                and entry.stat().st_mtime > self.out_st_mtime
            ):
                return True

        return False

    def _perform_collect(
        self,
        behavior: CacheBehaviorProtocol,
    ) -> None:
        module_logger.info("Reading input file(s)")
        with mp.Pool() as pool:
            reader = partial(
                self.reader.read_excel,
                sheet_name=self.sheet_name,
                cacher=self.collection_cacher,
                behavior=behavior,
            )
            entries = [
                entry
                for entry in self.input_dir.glob(self.glob_pattern)
                if entry.is_file() and entry != self.output_file
            ]
            raw_frames: list[DataFrame | dict[int | str, DataFrame]] = []
            raw_frames = pool.map(reader, entries)

        frames = []
        for frame in raw_frames:
            if isinstance(frame, dict):
                frames.extend(frame.values())
            else:
                frames.append(frame)

        module_logger.info("Saving result")

        collected = pd.concat(frames, ignore_index=True).convert_dtypes()
        collected.to_excel(self.output_file, index=False)
        self.out_st_mtime = self.output_file.stat().st_mtime

    def collect(
        self,
        behavior: CacheBehaviorProtocol = CacheBehavior.CHECK_CACHE,
    ) -> DataFrame:
        module_logger.info("Collecting Excel files.")
        if True or self._should_collect:
            self._perform_collect(behavior)
        return self.reader.read_excel(self.output_file, behavior=behavior)