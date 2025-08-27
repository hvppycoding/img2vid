#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
img2vid-bounce
- 현재 폴더의 이미지들을 '알파벳(사전) 순'으로 인식
- 구간 [start, end] 또는 [from-name, to-name]을 '앞→뒤'로 만들되
  끝 프레임은 중복하지 않도록 end-1..start를 역순 복제
- Windows 친화: symlink 미사용, shutil.copy2만 사용
- 생성 파일명: <end_stem>_001<ext>, _002<ext>, ...
"""

import os
import sys
import argparse
import shutil
from typing import List, Optional, Set, Tuple

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"}

def list_images(ext_filter: Optional[Set[str]] = None) -> List[str]:
    files: List[str] = []
    for f in os.listdir("."):
        p = os.path.join(".", f)
        if os.path.isfile(p):
            ext = os.path.splitext(f)[1].lower()
            if (ext_filter and ext in ext_filter) or (not ext_filter and ext in IMAGE_EXTS):
                files.append(f)
    files.sort(key=str.casefold)  # 대소문자 무시 사전순
    return files

def index_from_name(files: List[str], name: str) -> int:
    try:
        return files.index(name)
    except ValueError:
        sys.exit(f"[오류] 지정한 파일을 찾을 수 없습니다: {name}")

def find_free_block(end_stem: str, end_ext: str, count: int) -> int:
    """
    end_stem_###.ext 형태에서, ###가 count개 연속으로 비어 있는 첫 시작 번호를 반환.
    """
    n = 1
    while True:
        ok = True
        for i in range(n, n + count):
            candidate = f"{end_stem}_{i:03d}{end_ext}"
            if os.path.exists(candidate):
                ok = False
                break
        if ok:
            return n
        n += 1  # 한 칸씩 뒤로 밀며 탐색

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog="img2vid-bounce",
        description="알파벳 순 이미지에서 특정 구간을 앞→뒤(끝 프레임 중복 없이)로 미러 복제. "
                    "인자 없으면 전체 구간(1~N)에 적용."
    )

    # 구간 지정: 인덱스(1부터) 또는 파일명
    ap.add_argument("--start", type=int, help="시작 인덱스 (1부터, 알파벳 정렬 기준)")
    ap.add_argument("--end", type=int, help="끝 인덱스 (1부터, 포함)")
    ap.add_argument("--from-name", type=str, help="시작 파일명 (알파벳 정렬 기준에 존재해야 함)")
    ap.add_argument("--to-name", type=str, help="끝 파일명 (알파벳 정렬 기준에 존재해야 함)")

    ap.add_argument("--exts", nargs="*", help="확장자 필터(예: --exts .png .jpg). 미지정 시 일반 이미지 확장자 전체.")
    ap.add_argument("--dry-run", action="store_true", help="복사하지 않고 계획만 출력")
    return ap.parse_args()

def resolve_range(files: List[str], args: argparse.Namespace) -> Tuple[int, int]:
    # 1) 파일명 기반이 우선
    if (args.__dict__.get("from_name") is not None) or (args.__dict__.get("to_name") is not None):
        if not (args.from_name and args.to_name):
            sys.exit("[오류] --from-name 과 --to-name 을 함께 지정하세요.")
        s0 = index_from_name(files, args.from_name)
        e0 = index_from_name(files, args.to_name)

    # 2) 인덱스 기반
    elif (args.start is not None) or (args.end is not None):
        if args.start is None or args.end is None:
            sys.exit("[오류] --start/--end 는 함께 지정해야 합니다.")
        s0, e0 = args.start - 1, args.end - 1

    # 3) 인자 없으면 전체 구간(1~N)
    else:
        s0, e0 = 0, len(files) - 1

    if s0 < 0 or e0 >= len(files) or s0 > e0:
        sys.exit("[오류] 인덱스/파일 범위가 올바르지 않습니다.")
    return s0, e0


def main() -> None:
    args = parse_args()

    # 확장자 필터
    ext_filter: Optional[Set[str]] = None
    if args.exts:
        ext_filter = set(e.lower() if e.startswith(".") else "." + e.lower() for e in args.exts)

    files = list_images(ext_filter)
    if not files:
        sys.exit("[오류] 현재 폴더에서 이미지 파일을 찾지 못했습니다.")

    s0, e0 = resolve_range(files, args)

    # 끝 프레임은 중복하지 않음 → e0-1 down to s0
    src_indices = list(range(e0 - 1, s0 - 1, -1))
    if not src_indices:
        print("[정보] 복제할 프레임이 없습니다(시작==끝). 종료합니다.")
        return

    end_file = files[e0]
    end_stem, end_ext = os.path.splitext(end_file)
    start_block = find_free_block(end_stem, end_ext, len(src_indices))

    print(f"[정보] 총 {len(files)}개 이미지")
    print(f"[정보] 구간(알파벳 정렬 기준): {s0+1} ~ {e0+1}")
    print(f"[정보] 끝 파일: {end_file}")
    print(f"[정보] 생성 예정: {len(src_indices)}개 (끝 프레임 중복 없음)")

    created = []
    for k, src_i in enumerate(src_indices, start=start_block):
        src = files[src_i]
        dst = f"{end_stem}_{k:03d}{end_ext}"
        if args.dry_run:
            print(f"[DRY] {src} -> {dst}")
        else:
            shutil.copy2(src, dst)
            print(f"{src} -> {dst}")
        created.append(dst)

    # 인접 미리보기
    preview = files[:e0+1] + created + files[e0+1:]
    window_start = max(0, e0 - 2)
    window_end   = min(len(preview), e0 + 3 + len(created))
    print("\n[정렬 시 인접 구간 미리보기]")
    print(" ... " + ", ".join(preview[window_start:window_end]) + " ...")

if __name__ == "__main__":
    main()
