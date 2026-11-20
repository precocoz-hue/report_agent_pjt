# [개발 결과 보고서] Report Agent 백엔드 구축 및 API 통합 검증

* **작성일:** 2026년 11월 20일
* **프로젝트명:** Report Agent (`report_agent_pjt` v1.0.0)
* **구현 목표 범위:** Basic (`PROJECT_LEVEL=basic` 기준, `B-01` ~ `B-15`)
* **기술 스택:** Python 3.13, FastAPI, PostgreSQL (`pgvector`), SQLAlchemy, HuggingFace `intfloat/multilingual-e5-small` (384차원), OpenAI Responses API, Postman

---

## 1. 작업 개요 및 아키텍처 요약

보고서 데이터의 생성·조회·수정·삭제(CRUD), `pgvector` 기반 Keyword + Semantic 하이브리드 유사도 검색, 실제 OpenAI Responses API 기반 원문 요약, 그리고 명시적 Action 라우팅 Agent를 제공하는 FastAPI 백엔드 애플리케이션을 구축하고 전체 API 흐름을 검증했습니다.

### 계층형 아키텍처 구성 (`report_agent_pjt/`)
* **진입점 및 전역 예외 처리 (`app/main.py`)**
  * `reports`, `search`, `agent` 라우터 통합 및 `/health` 엔드포인트(DB 및 `pgvector` 확장 상태 점검) 구현
  * `DomainError`, `SQLAlchemyError`(503/500), `RequestValidationError`(422) 전역 예외 처리기를 통해 SQL 쿼리·접속 정보·잘못된 입력 원문의 외부 노출 차단
* **데이터베이스 및 벡터 색인 (`sql/`, `scripts/`, `app/db/`, `app/models/`, `app/repositories/`)**
  * `schema.sql`, `seed.sql` 기반 초기 테이블(6개 카테고리, 180건 시드 보고서) 구축
  * `scripts/index_overviews.py`를 통한 전체 보고서 개요(Overview) 384차원 E5 임베딩 일괄 색인 수행
* **비즈니스 로직 및 AI 연동 (`app/api/`, `app/services/`, `app/integrations/`)**
  * `embedding_client.py`: E5 모델(`passage:` / `query:`) 벡터 인코딩 처리
  * `llm_client.py`: OpenAI Responses API 연동, 원문 기반 프롬프트 격리, 토큰 사용량(`ContextVar`) 추적 및 재시도·예외 방어 로직 구현

---

## 2. 요구사항 체크리스트 수행 결과 (`7.1 Basic` 기준)

VS Code 터미널 실행 로그 및 API 응답 결과를 명세서 요구사항(`B-01` ~ `B-15`)과 대조하여 검증한 결과입니다.

| 요구사항 ID | 수행 상태 | 구현 내용 및 완료 기준 | 관련 API / 테이블 | 터미널 로그 검증 근거 |
| :--- | :---: | :--- | :--- | :--- |
| **B-01** | ✅ 완료 | FastAPI 서버 실행 및 `/docs`, `/health` 정상 응답 | `API-00` | `GET /health` `200 OK`, `GET /docs` `200 OK`, `/openapi.json` `200 OK` 확인 |
| **B-02** | ✅ 완료 | DB 세션·ORM 연결, 제공된 DDL 실행, 6개 분류 확인 | `categories`, `reports` | `GET /api/v1/categories` `200 OK` 및 DB 연결 정상 확인 |
| **B-03** | ✅ 완료 | 180개 보고서·6종 상세·Prompt 버전 시드 데이터 확인 | `seed.sql` | `index_overviews.py` 실행 시 초기 180건 + 신규 3건(총 183건) 적재 확인 |
| **B-04** | ✅ 완료 | 카테고리 6건 조회 및 미등록 코드 입력 거부 | `API-01`, `API-02` | `GET /api/v1/categories` `200 OK`, 잘못된 요청 `422 Unprocessable Content` 확인 |
| **B-05** | ✅ 완료 | 공통 보고서 Create + 상세 1행 Transaction 처리 | `API-02` | `POST /api/v1/reports` `201 Created` (ID `181`~`192` 생성) 확인 |
| **B-06** | ✅ 완료 | ID 단일 조회, 존재 시 `200` / 미존재 시 `404` 반환 | `API-03` | `GET /api/v1/reports/1`, `/183`, `/184` `200 OK` / 존재하지 않는 ID `404 Not Found` 확인 |
| **B-07** | ✅ 완료 | 제목 부분 일치 목록 조회 및 페이징(`limit`, `offset`) | `API-04` | `GET /api/v1/reports?title=가중치&limit=20&offset=0` 및 `offset=2` `200 OK` 확인 |
| **B-08** | ✅ 완료 | 보고서 전체 수정·Revision 증가·상세행 갱신 | `API-05` | `PUT /api/v1/reports/183`, `PUT /api/v1/reports/184` `200 OK` 및 재조회 반영 확인 |
| **B-09** | ✅ 완료 | 보고서 삭제 후 원문·상세·벡터 참조 제거 | `API-06` | `DELETE /api/v1/reports/183`, `/185`, `/187`~`191` `204 No Content` 및 재조회 시 `404` 확인 |
| **B-10** | ✅ 완료 | E5 `passage:`/`query:` 및 384차원 개요 인덱싱 | `report_embeddings` | `encode(..., kind='passage')` 출력 차원 `384` 및 `index_overviews.py` 전체 색인 완료 |
| **B-11** | ✅ 완료 | 생성·Overview 수정·삭제 시 Vector 상태 연동 반영 | `API-02/05/06` | 신규 생성 시 `index_status: ready` 및 수정·삭제 트랜잭션 연동 검증 완료 |
| **B-12** | ✅ 완료 | Keyword + Semantic 후보 결합, 최고 1건 또는 `not_found` | `API-07` | `POST /api/v1/search/similar` 정상 `200 OK` 및 입력 검증 실패 `422` 확인 |
| **B-13** | ✅ 완료 | 원문 DB 조회 후 실제 OpenAI LLM API 요약 수행 | `API-08` | `POST /api/v1/reports/1/summarize`, `/184/summarize` `200 OK` / 미존재 ID `404` 확인 |
| **B-14** | ✅ 완료 | 명시적 `get_report`/`find_report`/`summarize_report` 라우팅 | `API-09` | `POST /api/v1/agent/run` 다수 시나리오 `200 OK` 실행 확인 |
| **B-15** | ⚠️ 확인 필요 | Postman 통합 검증 및 **최종 시드 180건 기준 검증 SQL 제출** | 테스트 증거 | API 통합 실행 완료했으나, **초기 180건 클린 상태 색인(`vectors=180, ready=180`) 재검증 및 `tests/` 테스트 코드 작성은 마무리 확인 필요** |

---

## 3. API 엔드포인트별 검증 요약 (`API-00` ~ `API-14`)

### 3.1 Basic 필수 구현 API 검증 현황
| API ID | Method · Endpoint | 수행 결과 | 확인된 HTTP 상태 코드 | 검증 비고 |
| :--- | :--- | :---: | :--- | :--- |
| **API-00** | `GET /health` | ✅ 완료 | `200 OK` | DB 및 `pgvector` 확장 `ready` 확인 |
| **API-01** | `GET /api/v1/categories` | ✅ 완료 | `200 OK` | 사전 정의 카테고리 목록 정상 조회 |
| **API-02** | `POST /api/v1/reports` | ✅ 완료 | `201 Created`, `422` | 정상 생성(`201`) 및 필수값 누락·유효성 위반 방어(`422`) |
| **API-03** | `GET /api/v1/reports/{report_id}` | ✅ 완료 | `200 OK`, `404 Not Found` | 시드 ID(`1`), 생성 ID(`183`, `184`) 조회 및 미존재 ID(`999999999999`) `404` 처리 |
| **API-04** | `GET /api/v1/reports` | ✅ 완료 | `200 OK`, `422` | `title=가중치` 검색·페이징 정상(`200`) 및 `limit=101` 초과 요청 차단(`422`) |
| **API-05** | `PUT /api/v1/reports/{report_id}` | ✅ 완료 | `200 OK` | 기존 보고서 전체 수정 및 변경 반영 확인 |
| **API-06** | `DELETE /api/v1/reports/{report_id}` | ✅ 완료 | `204 No Content`, `404` | 삭제 후 `204` 반환 및 동일 ID 재조회 시 `404 Not Found` 확인 |
| **API-07** | `POST /api/v1/search/similar` | ✅ 완료 | `200 OK`, `422` | 관련/무관 질의 검색 `200` 및 잘못된 요청 `422` 처리 |
| **API-08** | `POST /api/v1/reports/{report_id}/summarize` | ✅ 완료 | `200 OK`, `404 Not Found` | 실제 OpenAI API 연동 요약 성공(`200`) 및 삭제·미존재 ID 요약 요청 `404` 처리 |
| **API-09** | `POST /api/v1/agent/run` | ✅ 완료 | `200 OK` | 명시적 `action` 기반 도구 라우팅 정상 실행 |

### 3.2 Intermediate / Advanced 확장 API 현황 (`PROJECT_LEVEL=basic` 기준 미실행)
* `API-10` (`POST /api/v1/prompts/{report_id}/versions`), `API-11` (`GET /api/v1/prompts/{report_id}/versions`): Intermediate 범위
* `API-12` (`PUT /api/v1/prompts/{report_id}/active-version`), `API-13` (`POST /api/v1/reports/{report_id}/reindex`), `API-14` (`GET /api/v1/agent/runs`): Advanced 범위

---

## 4. 트러블슈팅 내역

1. **OpenAI API 인증 오류 (`401 invalid_api_key` -> `503 LLM_UNAVAILABLE`) 해결**
   * **현상:** `/api/v1/reports/{id}/summarize` 호출 시 `llm_client.py`에서 `DomainError(503, 'LLM_UNAVAILABLE')` 발생.
   * **원인:** `.env` 파일 내 `OPENAI_API_KEY` 값 오기입/만료로 인해 OpenAI `AuthenticationError(401)` 발생.
   * **해결:** 유효한 `OPENAI_API_KEY`로 갱신 후 단건 LLM 호출 테스트 및 API `200 OK` 응답 검증 완료.
2. **Postman 환경 변수(`{{created_report_id}}`) 미치환 및 삭제 ID 참조 해결**
   * **현상:** `DELETE` 요청으로 테스트용 보고서(`183` 등)를 삭제한 이후 동일 ID 변수를 참조하는 `GET`·`POST /summarize` 요청이 `404` 또는 미전송 상태 발생.
   * **해결:** Postman Environment 내 `created_report_id` 값을 살아있는 유효 보고서 ID로 동기화하여 정상 요청 흐름 복구.

---

## 5. 부족한 점 및 향후 개선 필요 사항

1. **초기 시드 180건 클린 상태 기준 색인 재검증 필요 (`B-15` 마무리)**
   * 개발·테스트 중 생성된 보고서(`184`번 등)가 남아 있거나 `index_overviews.py` 실행 시 `vectors=183, ready=183` 상태로 기록되었습니다.
   * 명세서 가이드(`seed 초기 상태라면 각각 180이어야 합니다`)에 따라 최종 검증 시 테스트용 잔여 보고서 정리 후 **`vectors=180, ready=180`** 상태와 검색 품질(5개 질의 원문 대조 및 임계값 `0.75` 적정성)을 최종 확인해야 합니다.
2. **자동화 테스트 코드(`tests/`) 부재**
   * `mkdir -p tests`로 디렉터리는 생성되었으나 내부에 `pytest` 기반 단위·통합 테스트 스크립트가 아직 작성되지 않았습니다.
   * 수동 Postman 검증 외에 회귀 테스트 자동화를 위해 `tests/test_reports.py`, `tests/test_search.py` 등의 테스트 케이스 추가가 필요합니다.
3. **고도화 기능(`Intermediate` / `Advanced`) 확장 여지**
   * 현재 `PROJECT_LEVEL=basic`으로 동작 중이므로, 운영 환경 적용 시 다음 기능의 단계적 활성화를 권장합니다.
     * **Intermediate:** `structured` JSON 요약 지원, 프롬프트 버전 관리(`API-10`, `API-11`), 검색·요약 결합 에이전트(`search_and_summarize`)
     * **Advanced:** 낙관적 락 기반 동시 수정 충돌 방지(`expected_revision`, `409 REVISION_CONFLICT`), 개별 보고서 재색인(`API-13`), Agent 실행 이력 조회(`API-14`)
