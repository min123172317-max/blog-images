#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""한글(HWP/HWPX) 파일 안의 그림을 모두 꺼낸다.

실행:
    python3 -I tools/hwp_images.py 문서.hwp 출력폴더
출력: 출력폴더/BIN0001.jpg ... (HWPX는 image1.png ...) 와 각 그림 크기 목록
- HWP(5.0)는 olefile이 필요하다. 없으면 자동으로 pip 설치를 1회 시도한다.
- HWPX는 zip이라 추가 설치가 필요 없다.
"""
import os
import subprocess
import sys
import zipfile
import zlib


def need_olefile():
    try:
        import olefile  # noqa: F401
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "olefile"], check=False)
    import olefile
    return olefile


def main():
    if len(sys.argv) != 3:
        sys.exit("사용법: python3 -I tools/hwp_images.py 문서.hwp 출력폴더")
    src, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    saved = []
    if zipfile.is_zipfile(src):  # HWPX
        z = zipfile.ZipFile(src)
        for n in z.namelist():
            if n.startswith("BinData/") and not n.endswith("/"):
                p = os.path.join(out, os.path.basename(n))
                open(p, "wb").write(z.read(n))
                saved.append(p)
    else:  # HWP 5.0
        olefile = need_olefile()
        try:
            o = olefile.OleFileIO(src)
        except Exception as e:
            sys.exit("한글 파일이 아닙니다(웹페이지가 내려왔을 수 있음): %s" % e)
        for e in o.listdir():
            if e[0] == "BinData":
                d = o.openstream(e).read()
                try:
                    d = zlib.decompress(d, -15)  # 압축된 그림은 풀고, 아니면 그대로
                except zlib.error:
                    pass
                p = os.path.join(out, e[1])
                open(p, "wb").write(d)
                saved.append(p)
    try:
        from PIL import Image
    except ImportError:
        Image = None
    for p in saved:
        size = ""
        if Image:
            try:
                size = "%dx%d" % Image.open(p).size
            except Exception:
                size = "그림 아님"
        print(p, size)
    if not saved:
        print("그림 없음")


if __name__ == "__main__":
    main()
