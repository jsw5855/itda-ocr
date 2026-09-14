# 소비기한 추출 OCR

## 1. 프로젝트 목적
- 상품 뒷면 이미지에서 소비기한 날짜를 추출하는 OCR 파이프라인
- 최종 출력: `image_id`, `year`, `month`, `day`, `final_date`

## 2. 대회 실행 환경
- Python 3.10 · Standard 4-Core vCPU
- GPU 없음(CPU-only 채점) · 오프라인 추론
- `predict.ipynb` Run All 방식으로 실행

## 3. 데이터 현황
- 총 **3,352장**: jpg 3,247장 · jpeg 101장 · png 4장
- 해상도 다양: 640×640 이미지 1,106장, 고해상도 원본 이미지도 다수 존재
- 손상 이미지 없음

## 4. 표본 이미지 관찰 결과
- 소비기한 위치가 일정하지 않고 날짜 표기 형식이 다양함
- 소비기한, EXP, BEST BEFORE 등 다양한 키워드 존재 가능
- 바코드, 전화번호, 영양정보 등 날짜와 혼동 가능한 숫자가 많음
- 회전, 반사, 과노출, 작은 글씨 등 실제 촬영 노이즈 존재

## 5. 현재 고려 중인 기본 아키텍처
이미지 → OCR → 날짜 후보 추출 → 주변 키워드/위치 기반 소비기한 후보 선택 → 날짜 유효성 검증 → `submission.csv`

## 6. 제출 재현 상태

**현재 clone만으로 실행할 수 있는 완성된 제출 상태는 아니다.** `weights/`는 Git 제외 대상이고, `download_weights.sh`는 비어 있으며, 검증된 weight 배포 URL이 아직 연결되지 않았다. 아래 weight 준비 단계를 완성한 뒤 오프라인 실행해야 한다. 최신 실행 모듈과 notebook 변경도 최종 제출 저장소에 포함해야 한다.

현재 Windows Python 3.10.11에서 실제 OCR 및 nbconvert 실행을 검증했다. 같은 100장에 대해 4개 논리 CPU로 제한한 직접 실행은 56.9초, nbconvert 전체는 64.6초였고 모든 worker가 종료했다. 이는 공식 Linux Standard 4-Core vCPU에서 전체 입력을 2400초 내 완료했다는 검증은 아니다. 상세 근거는 [실행 감사](docs/runtime_audit/REPORT.md), 제출 준비 상태는 [인프라 감사](docs/submission_infrastructure_audit.md)를 참고한다.

## 7. 운영진 재현 절차 (Linux, 저장소 루트)

### 1) Clone 및 Python 3.10 환경 준비 — 인터넷 연결 상태

```bash
git clone https://github.com/jsw5855/itda-ocr.git
cd itda-ocr
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip check
python -m ipykernel install --sys-prefix --name python3 --display-name "Python 3"
python -c "import cv2, numpy, PIL; print(cv2.__version__, numpy.__version__, PIL.__version__)"
```

직접 고정한 버전은 PaddleOCR 3.7.0, PaddlePaddle 3.2.2, PaddleX 3.7.2, NumPy 2.2.6, Pillow 12.3.0, opencv-contrib-python 4.10.0.84다. `nbconvert`와 `ipykernel`도 requirements에 포함되지만 현재 버전 고정은 되어 있지 않다. 검증 환경에서는 각각 7.17.1, 7.3.0이었다. 전이 의존성 전체를 고정한 lock 파일은 없으므로 새 Linux 환경 설치 검증이 필요하다.

PaddleX ocr-core가 요구하는 OpenCV 배포판 하나만 설치한다. headless를 추가 설치해 cv2 배포판을 중복시키지 않는다. Linux의 GUI 포함 OpenCV wheel이 요구하는 시스템 공유 라이브러리는 pip만으로 충족되지 않을 수 있으므로 위 import 검증을 통과해야 한다. 개발/검증 도구는 별도의 `requirements-dev.txt`이며 운영진 실행에는 필요하지 않다.

### 2) Weight 준비 — 인터넷을 차단하기 전

**BLOCKER: 현재 `download_weights.sh`는 0바이트이며 아무 weight도 준비하지 않는다.** 공개적으로 접근 가능한 고정 버전 URL, checksum 검증, 아래 경로로의 배치를 구현해야 한다. 현재는 다음 명령만 실행해도 준비가 완료된다고 볼 수 없다.

```bash
bash download_weights.sh
```

준비 완료 시 저장소 루트에 다음 구조가 있어야 한다. 두 모델의 `inference.json`, `inference.pdiparams`, `inference.yml` 6개는 런타임이 필수로 확인한다. 검증한 원본 번들의 config.json, README.md와 manifest도 함께 전달한다.

```text
weights/paddleocr/
  SHA256_MANIFEST.json
  PP-OCRv5_mobile_det/
    inference.json
    inference.pdiparams
    inference.yml
    config.json
    README.md
  korean_PP-OCRv5_mobile_rec/
    inference.json
    inference.pdiparams
    inference.yml
    config.json
    README.md
```

저장소 루트에서 준비된 번들의 크기와 SHA256을 확인한다.

```bash
python - <<'PY'
import hashlib
import json
from pathlib import Path
manifest = json.loads(Path("weights/paddleocr/SHA256_MANIFEST.json").read_text())
for name, expected in manifest.items():
    content = Path(name).read_bytes()
    if len(content) != expected["bytes"] or hashlib.sha256(content).hexdigest() != expected["sha256"]:
        raise SystemExit(f"Weight checksum mismatch: {name}")
print(f"Verified {len(manifest)} model files")
PY
```

manifest 자체의 신뢰성은 공개할 배포물의 고정 checksum으로 별도 보장해야 한다.

### 3) 인터넷 차단 후 환경변수 주입 및 Run All

위 준비를 마친 환경에서 운영진이 네트워크를 차단한 다음 실행한다. 설치 및 weight 준비는 notebook 실행 전에 완료하며 notebook은 이를 호출하지 않는다.

```bash
export ITDA_INPUT_DIR=./val_images
export ITDA_OUTPUT_PATH=./submission.csv
jupyter nbconvert --to notebook --execute predict.ipynb \
    --ExecutePreprocessor.timeout=2400 \
    --output /tmp/executed.ipynb
```

첫 CONFIG 셀은 위 두 환경변수를 그대로 읽는다. 별도의 사용자 입력은 없다. 기본 제출 경로는 `predict.ipynb → ocr_pipeline.run_submission → submission_runtime`이며 두 독립 worker가 로컬 PaddleOCR를 CPU에서 실행한다. 기본 2-process × 2-thread 설정을 사용하며, 개발용 `ITDA_OCR_PROCESSES` override는 공식 실행에 필요하지 않다.

입력 디렉터리 바로 아래의 jpg/jpeg/png 파일을 처리하고 파일명 확장자를 뺀 stem을 `image_id`로 사용한다. 입력이 없거나 stem이 중복되면 오류로 종료한다. 출력은 입력 파일 수와 같은 행 수의 UTF-8 BOM CSV이며 컬럼 순서는 다음과 같다.

```text
image_id,year,month,day,final_date
```

OCR 모델 경로를 명시하고 보조 방향/문서 모델을 비활성화했다. 필수 모델 파일이 없으면 다운로드로 대체하지 않고 오류를 낸다. `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True`는 접속 확인을 건너뛰는 설정이며 모든 HTTP 요청을 차단하는 방화벽은 아니다. 코드 감사에서는 정상 경로의 다운로드 호출이 발견되지 않았고, 실제 네트워크 차단 재현 검증은 별도다. PaddleX 캐시용 `weights/paddlex/`와 출력 디렉터리에 쓰기 권한이 필요할 수 있다.

worker의 180초 무응답 또는 worker 구간 2300초 초과는 실패 처리한다. 이는 부분 예측을 만들어 성공으로 처리하는 기능이 아니며 공식 전체 wall-clock 2400초 성공을 보장하지 않는다.

## 8. 제출 파일 구분

최종 저장소에 `predict.ipynb`, `ocr_pipeline.py`, **`submission_runtime.py`**, `date_parser/` 전체, `requirements.txt`, 완성된 `download_weights.sh`, `README.md`가 필요하다. 모델은 별도 사전 배포 경로로 준비한다. 운영진 Run All은 `data/`, `labels/`, 개발 notebook이나 benchmark 결과를 참조하지 않는다.

`tmp_*`, 로컬 submission CSV, 실행 완료 notebook, benchmark 입력 복사본·결과·로그, `.venv/`는 제출 실행에 불필요하다. 현재 `.gitignore`는 data/labels/weights와 가상환경 등을 제외하지만 tmp/출력 일부는 제외하지 않으므로 일괄 추가 전에 구분해야 한다. 자세한 Git 상태 분류는 [인프라 감사](docs/submission_infrastructure_audit.md)에 기록했다.
