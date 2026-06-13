import json
import unittest

from uploader.bilibili_uploader.login import (
    AUTH_URL_PATTERN,
    _extract_auth_url,
    _make_qrcode_data_url,
    _user_message,
)


class BilibiliLoginTests(unittest.TestCase):
    def test_extract_auth_url_from_output(self):
        text = (
            "请使用浏览器打开\n"
            "https://passport.bilibili.com/x/passport-tv-login/h5/qrcode/auth?auth_code=abc123\n"
            "扫码授权"
        )
        self.assertEqual(
            _extract_auth_url(text),
            "https://passport.bilibili.com/x/passport-tv-login/h5/qrcode/auth?auth_code=abc123",
        )

    def test_auth_url_pattern_requires_auth_code(self):
        self.assertIsNone(AUTH_URL_PATTERN.search("https://passport.bilibili.com/login"))

    def test_make_qrcode_data_url(self):
        data_url = _make_qrcode_data_url(
            "https://passport.bilibili.com/x/passport-tv-login/h5/qrcode/auth?auth_code=test"
        )
        self.assertTrue(data_url.startswith("data:image/png;base64,"))

    def test_user_message_hides_technical_terms(self):
        self.assertIn("超时", _user_message("timeout"))
        self.assertNotIn("biliup", _user_message("github release failed").lower())

    def test_prepare_biliup_cookie_file_adds_sso_field(self):
        import tempfile
        from pathlib import Path

        from uploader.bilibili_uploader.login import prepare_biliup_cookie_file

        with tempfile.TemporaryDirectory() as tmp_dir:
            cookie_path = Path(tmp_dir) / "account.json"
            cookie_path.write_text(
                json.dumps(
                    {
                        "cookie_info": {
                            "cookies": [
                                {"name": "SESSDATA", "value": "abc", "domain": ".bilibili.com", "path": "/"},
                                {"name": "bili_jct", "value": "def", "domain": ".bilibili.com", "path": "/"},
                            ]
                        },
                        "token_info": {
                            "mid": 0,
                            "access_token": "",
                            "refresh_token": "",
                            "expires_in": 0,
                        },
                    }
                ),
                encoding="utf-8",
            )
            prepare_biliup_cookie_file(str(cookie_path))
            data = json.loads(cookie_path.read_text(encoding="utf-8"))
            self.assertIn("sso", data)


if __name__ == "__main__":
    unittest.main()
