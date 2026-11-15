# blog-images
blog-images

## tools/minsom_format.py (민솜 서식 변환)

원고 텍스트와 지시 파일(형광펜·사진 위치)로 자동서식 틀(v2, 2026-11-15)의 HTML을 만든다. v2: 목차 없음, 서문 → 3줄 요약 → 소제목 순서, 본문 19px·소제목 24px, '|'로 시작하는 줄은 표, 제목 40자·분량·문단 길이 점검 알림. 사용법은 파일 맨 위 설명 참고.

    python3 tools/minsom_format.py 원고.txt 지시.txt -o index.html

## addressbook.tsv (공식 문서 주소록)

이미지 찾기에서 검색 전에 확인하는 공식 문서·쪽·쓴 사진 기록. 사용법은 파일 맨 위 주석 참고.

## tools/topic_scan.py (글감 스캔)

블로그에 올린 글 제목과 네이버 자동완성의 새 연관어를 읽어 글감 중복과 수요를 확인한다. 사용법은 파일 맨 위 설명 참고.
