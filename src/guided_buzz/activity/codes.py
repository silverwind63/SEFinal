"""組別代碼的產生、正規化與雜湊（data-model.md Team.code、Team.code_hash）。"""

import hashlib
import secrets

ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"  # 去除 0、1、I、O 等易混淆字元
LENGTH = 6


def new_code(existing: set[str]) -> str:
    """產生同一場活動內不重複的代碼。"""
    while True:
        code = "".join(secrets.choice(ALPHABET) for _ in range(LENGTH))
        if code not in existing:
            return code


def normalize(raw: str) -> str:
    return "".join(raw.split()).upper()


def is_well_formed(code: str) -> bool:
    return len(code) == LENGTH and all(c in ALPHABET for c in code)


def code_hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()
