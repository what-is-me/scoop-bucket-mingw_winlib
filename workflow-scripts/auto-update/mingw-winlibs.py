from collections import defaultdict
import logging
from pathlib import Path
import time
from typing import Tuple
import requests
import json
import re


class WinLibVersion:
    def __get_version_tuple(self, version_str: str) -> Tuple[int]:
        return tuple(map(int, version_str.split(".")))

    def __tuple_to_version(self, version_tuple: Tuple[int]) -> str:
        return ".".join(map(str, version_tuple))

    def __init__(
        self,
        gcc_version: str = "0.0.0",
        threading_model: str = "",
        llvm_version: str = "0.0.0",
        mingw_version: str = "0.0.0",
        runtime_library: str = "",
        release_num: str = "0",
    ) -> None:
        self.gcc_version = self.__get_version_tuple(gcc_version)
        self.threading_model = threading_model.lower()
        self.llvm_version = self.__get_version_tuple(llvm_version)
        self.mingw_version = self.__get_version_tuple(mingw_version)
        self.runtime_library = runtime_library.lower()
        self.release_num = int(release_num)

    def get_gcc_version(self) -> str:
        return self.__tuple_to_version(self.gcc_version)

    def get_llvm_version(self) -> str:
        return self.__tuple_to_version(self.llvm_version)

    def get_mingw_version(self) -> str:
        return self.__tuple_to_version(self.mingw_version)

    def __repr__(self) -> str:
        return f"GCC{self.get_gcc_version()}_LLVM{self.get_llvm_version()}_MINGW{self.get_mingw_version()}_{self.threading_model}_{self.runtime_library}_r{self.release_num}"

    def get_comparable_version_tuple(self) -> Tuple:
        return self.gcc_version, self.llvm_version, self.mingw_version, self.release_num

    def get_tag(self) -> str:
        return f"{self.threading_model}_{self.runtime_library}"

    def get_version(self, with_llvm: bool) -> str:
        if with_llvm:
            return f"GCC{self.get_gcc_version()}_LLVM{self.get_llvm_version()}_MINGW{self.get_mingw_version()}_r{self.release_num}"
        else:
            return f"GCC{self.get_gcc_version()}_MINGW{self.get_mingw_version()}_r{self.release_num}"

    def get_url(self, arch_64: bool = True, with_llvm: bool = True) -> str:
        tag_name = f"{self.get_gcc_version()}{self.threading_model}-{self.get_llvm_version()}-{self.get_mingw_version()}-{self.runtime_library}-r{self.release_num}"
        zip_name = f"winlibs-{'x86_64'if arch_64 else'i686'}-{self.threading_model}-{'seh'if arch_64 else'dwarf'}-gcc-{self.get_gcc_version()}{f'-llvm-{self.get_llvm_version()}'if with_llvm else ''}-mingw-w64{self.runtime_library}-{self.get_mingw_version()}-r{self.release_num}.7z"
        return f"https://github.com/brechtsanders/winlibs_mingw/releases/download/{tag_name}/{zip_name}"

    def get_hash(self, arch_64: bool = True, with_llvm: bool = True) -> str:
        sha = requests.get(self.get_url(arch_64, with_llvm) + ".sha256").text.split(
            " "
        )[0]
        time.sleep(1)
        if len(sha) < 10:
            raise Exception(f"get {self.get_url(arch_64, with_llvm)}.sha256 fail")
        return sha

    def gen_scoop_json(self, with_llvm: bool = True):
        return {
            "version": self.get_version(with_llvm),
            "description": "GNU Compiler Collection (WinLibs build)",
            "homepage": "https://winlibs.com",
            "license": "GPL-3.0-or-later,ZPL-2.1,BSD-2-Clause,...",
            "architecture": {
                "64bit": {
                    "url": self.get_url(True, with_llvm),
                    "hash": self.get_hash(True, with_llvm),
                    "extract_dir": "mingw64",
                },
                "32bit": {
                    "url": self.get_url(False, with_llvm),
                    "hash": self.get_hash(False, with_llvm),
                    "extract_dir": "mingw32",
                },
            },
            "post_install": 'Copy-Item "$dir\\bin\\mingw32-make.exe" "$dir\\bin\\make.exe"',
            "env_add_path": "bin",
            "checkver": {
                "regex": f"(?<gcc>[\\d.]+){self.threading_model}-(?<llvm>[\\d.]+)-(?<mingw>[\\d.]+)-{self.runtime_library}-r(?<release>\\d+)",
                "replace": (
                    "GCC${gcc}_LLVM${llvm}_MINGW${mingw}_r${release}"
                    if with_llvm
                    else "GCC${gcc}_MINGW${mingw}_r${release}"
                ),
            },
            "autoupdate": {
                "architecture": {
                    "64bit": {
                        "url": f"https://github.com/brechtsanders/winlibs_mingw/releases/download/$matchGcc{self.threading_model}-$matchLlvm-$matchMingw-{self.runtime_library}-r$matchRelease/winlibs-x86_64-{self.threading_model}-seh-gcc-$matchGcc{'-llvm-$matchLlvm'if with_llvm else ''}-mingw-w64{self.runtime_library}-$matchMingw-r$matchRelease.7z"
                    },
                    "32bit": {
                        "url": f"https://github.com/brechtsanders/winlibs_mingw/releases/download/$matchGcc{self.threading_model}-$matchLlvm-$matchMingw-{self.runtime_library}-r$matchRelease/winlibs-i686-{self.threading_model}-dwarf-gcc-$matchGcc{'-llvm-$matchLlvm'if with_llvm else ''}-mingw-w64{self.runtime_library}-$matchMingw-r$matchRelease.7z"
                    },
                },
                "hash": {"url": "$url.sha256"},
            },
        }


def get_version(name: str, **kargvs) -> WinLibVersion | None:
    if (
        len(
            version_from_name := re.findall(
                r"GCC (\d+\.\d+\.\d+) \(([A-Z]+) threads\) \+ LLVM (\d+\.\d+\.\d+) \+ MinGW-w64 (\d+\.\d+\.\d+) ([A-Z]+) \(release (\d+)\)",
                name,
            )
        )
        == 1
    ):
        return WinLibVersion(*version_from_name[0])
    return None


def main():
    tag_list = requests.get(
        "https://api.github.com/repos/brechtsanders/winlibs_mingw/releases"
    ).json()
    latest_versions = defaultdict(WinLibVersion)
    for tag_src in tag_list:
        try:
            version = get_version(**tag_src)
            if version is None:
                continue
            tag = version.get_tag()
            if (
                version.get_comparable_version_tuple()
                > latest_versions[tag].get_comparable_version_tuple()
            ):
                latest_versions[tag] = version
        except Exception as e:
            logging.error(e)
    Path("bucket").mkdir(exist_ok=True)
    for tag_name_short, version in latest_versions.items():
        for with_llvm in [True, False]:
            fn = f"bucket/mingw_winlib_{tag_name_short}{'_without' if not with_llvm else ''}_llvm.json"
            with open(fn, "w", encoding="utf-8") as w:
                json.dump(version.gen_scoop_json(True), w, indent=2)
                w.write('\n')


if __name__ == "__main__":
    main()
