# blog-images
blog-images

## tools/minsom_format.py (민솜 서식 변환)

원고 텍스트와 지시 파일(형광펜·사진 위치)로 자동서식 틀(v2, 2026-11-15)의 HTML을 만든다. v2: 목차 없음, 서문 → 3줄 요약 → 소제목 순서, 본문 19px·소제목 24px, '|'로 시작하는 줄은 표, 제목 40자·분량·문단 길이 점검 알림. 사용법은 파일 맨 위 설명 참고.

    python3 tools/minsom_format.py 원고.txt 지시.txt -o index.html

## addressbook.tsv (공식 문서 주소록)

이미지 찾기에서 검색 전에 확인하는 공식 문서·쪽·쓴 사진 기록. 사용법은 파일 맨 위 주석 참고.

## tools/topic_scan.py (글감 스캔)

블로그에 올린 글 제목과 네이버 자동완성의 새 연관어를 읽어 글감 중복과 수요를 확인한다. 사용법은 파일 맨 위 설명 참고.

## tools/hwp_images.py (한글 파일 그림 꺼내기)

    python3 -I tools/hwp_images.py 문서.hwp 출력폴더

HWP는 olefile을 쓰며 없으면 자동 설치한다. HWPX도 된다.

## tools/cap.py (캡처 마무리)

    python3 -I tools/cap.py 입력이미지 출력.jpg [x0 y0 x1 y1] [여백px]

영역 자르기 → 흰 여백 깎기 → 상하좌우 같은 여백 → 1080폭 JPEG(300KB 이하). 작은 원본은 키우지 않는다.

## data/blocked_sites.md (막힌 사이트 기록)

접속이 막힌 공식 사이트와 그때 필요했던 자료 목록. 민국이 모아서 한꺼번에 해결할 용도.
