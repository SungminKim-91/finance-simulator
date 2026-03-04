#!/usr/bin/env python3
"""
KRX 로그인 세션 관리 + pykrx 세션 주입.

KRX(data.krx.co.kr) 인증 후 세션 쿠키를 pykrx 내부 HTTP 클라이언트에 주입하여
2025-02-27 이후 인증 필수 API를 사용 가능하게 함.

환경변수: KRX_USER_ID, KRX_USER_PW (.env)
"""
import os

import requests

LOGIN_PAGE = "https://data.krx.co.kr/comm/login/LoginForm.cmd"
LOGIN_JSP = "https://data.krx.co.kr/comm/sso/SsoLogin.jsp"
LOGIN_URL = "https://data.krx.co.kr/comm/sso/SsoLoginReq.cmd"
DUP_CHECK_URL = "https://data.krx.co.kr/comm/sso/SsoLoginReq.cmd"
STATUS_URL = "https://data.krx.co.kr/comm/login/LoginStat.cmd"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://data.krx.co.kr/",
}


def create_krx_session() -> requests.Session:
    """KRX 로그인 후 인증된 세션 반환."""
    user_id = os.environ.get("KRX_USER_ID")
    user_pw = os.environ.get("KRX_USER_PW")
    if not user_id or not user_pw:
        raise ValueError("KRX_USER_ID / KRX_USER_PW 환경변수가 설정되지 않음")

    session = requests.Session()
    session.headers.update(HEADERS)

    # 1. 로그인 페이지 방문 → 쿠키 획득
    session.get(LOGIN_PAGE)

    # 2. SSO 로그인 JSP
    session.get(LOGIN_JSP)

    # 3. 로그인 POST
    login_data = {"userId": user_id, "userPw": user_pw}
    resp = session.post(LOGIN_URL, data=login_data)

    # 4. 중복 로그인 처리 (CD011 → skipDup=Y)
    body = resp.text
    if "CD011" in body or "중복" in body:
        login_data["skipDup"] = "Y"
        resp = session.post(DUP_CHECK_URL, data=login_data)
        body = resp.text

    # 5. 로그인 상태 확인
    stat = session.get(STATUS_URL)
    if "CD001" in stat.text or user_id in stat.text:
        print(f"  [KRX] 로그인 성공: {user_id}")
        return session

    # CD001이 없어도 쿠키가 설정되었으면 성공으로 간주
    if session.cookies.get("JSESSIONID"):
        print(f"  [KRX] 세션 획득: {user_id} (JSESSIONID)")
        return session

    print(f"  [WARN] KRX 로그인 불확실 — 세션 반환 (응답: {body[:100]})")
    return session


def inject_pykrx_session(session: requests.Session):
    """pykrx의 webio.Post/Get.read를 인증 세션으로 교체."""
    try:
        from pykrx.website.comm import webio

        original_post_read = webio.Post.read
        original_get_read = webio.Get.read

        def patched_post_read(self, **params):
            return session.post(self.url, headers=self.headers, data=params)

        def patched_get_read(self, **params):
            return session.get(self.url, headers=self.headers, params=params)

        webio.Post.read = patched_post_read
        webio.Get.read = patched_get_read
        print("  [KRX] pykrx 세션 주입 완료")
    except ImportError:
        print("  [WARN] pykrx not installed — 세션 주입 생략")
    except Exception as e:
        print(f"  [WARN] pykrx 세션 주입 실패: {e}")
