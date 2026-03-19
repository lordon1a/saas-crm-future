import base64
import hashlib
import hmac
import json
import time


class PortalAuth:
    @staticmethod
    def _b64url_encode(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b'=').decode('utf-8')

    @staticmethod
    def _b64url_decode(data: str) -> bytes:
        padding = '=' * (-len(data) % 4)
        return base64.urlsafe_b64decode((data + padding).encode('utf-8'))

    @staticmethod
    def encode_token(payload: dict, secret: str, exp_seconds: int) -> str:
        header = {'alg': 'HS256', 'typ': 'JWT'}
        body = dict(payload)
        body['exp'] = int(time.time()) + int(exp_seconds)

        header_part = PortalAuth._b64url_encode(json.dumps(header, separators=(',', ':')).encode('utf-8'))
        payload_part = PortalAuth._b64url_encode(json.dumps(body, separators=(',', ':')).encode('utf-8'))
        signing_input = f'{header_part}.{payload_part}'.encode('utf-8')

        signature = hmac.new(secret.encode('utf-8'), signing_input, hashlib.sha256).digest()
        signature_part = PortalAuth._b64url_encode(signature)

        return f'{header_part}.{payload_part}.{signature_part}'

    @staticmethod
    def decode_token(token: str, secret: str) -> dict | None:
        try:
            parts = token.split('.')
            if len(parts) != 3:
                return None

            header_part, payload_part, signature_part = parts
            signing_input = f'{header_part}.{payload_part}'.encode('utf-8')

            expected_signature = hmac.new(
                secret.encode('utf-8'),
                signing_input,
                hashlib.sha256
            ).digest()
            expected_signature_part = PortalAuth._b64url_encode(expected_signature)

            if not hmac.compare_digest(signature_part, expected_signature_part):
                return None

            payload = json.loads(PortalAuth._b64url_decode(payload_part).decode('utf-8'))
            exp = int(payload.get('exp', 0))
            if exp <= int(time.time()):
                return None

            return payload
        except Exception:
            return None
