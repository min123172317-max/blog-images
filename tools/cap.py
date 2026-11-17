#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""캡처 마무리: 영역 자르기 → 흰 여백 깎기 → 상하좌우 같은 여백 → 1080폭 JPEG(300KB 이하)

실행:
    python3 -I tools/cap.py 입력이미지 출력.jpg                 # 그림 전체
    python3 -I tools/cap.py 입력이미지 출력.jpg x0 y0 x1 y1      # 비율(0~1) 또는 픽셀로 영역 지정
    python3 -I tools/cap.py 입력이미지 출력.jpg x0 y0 x1 y1 0    # 마지막 숫자 = 여백 px(사진은 0)
- PDF 쪽은 먼저 `pdftoppm -r 250 -f 쪽 -l 쪽 -png 문서.pdf 쪽` 으로 그림을 만든 뒤 넣는다.
- 원본이 1080보다 작으면 키우지 않는다(저해상도 확대 금지 규칙).
"""
import os
import sys
from PIL import Image, ImageOps, ImageChops
src,dst=sys.argv[1],sys.argv[2]
im=Image.open(src).convert('RGB')
W,H=im.size
if len(sys.argv)>=7:
    x0,y0,x1,y1=[float(v) for v in sys.argv[3:7]]
    if max(x0,y0,x1,y1)>1:  # 픽셀 좌표로 넣은 경우(2026-11-17)
        x0,x1,y0,y1=x0/W,x1/W,y0/H,y1/H
    im=im.crop((int(x0*W),int(y0*H),int(x1*W),int(y1*H)))
pad=int(sys.argv[7]) if len(sys.argv)>7 else 24
g=ImageOps.invert(im.convert('L')).point(lambda v:255 if v>25 else 0)
bb=g.getbbox()
if not bb: sys.exit('빈 영역')
im=im.crop(bb)
w,h=im.size
canvas=Image.new('RGB',(w+2*pad,h+2*pad),'white');canvas.paste(im,(pad,pad))
if canvas.width>1080:
    canvas=canvas.resize((1080,round(canvas.height*1080/canvas.width)),Image.LANCZOS)
q=88
while True:
    canvas.save(dst,'JPEG',quality=q,optimize=True)
    if os.path.getsize(dst)<=300*1024 or q<=70: break
    q-=3
print(dst,canvas.size,os.path.getsize(dst)//1024,'KB q',q, '원본폭',w)
