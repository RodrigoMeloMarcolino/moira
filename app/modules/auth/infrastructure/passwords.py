import bcrypt


class BcryptPasswordHasher:
    def hash(self, password: str) -> str:
        password_bytes = password.encode('utf-8')
        password_hash = bcrypt.hashpw(password_bytes, bcrypt.gensalt())

        return password_hash.decode('utf-8')

    def verify(self, password: str, password_hash: str) -> bool:
        password_bytes = password.encode('utf-8')
        password_hash_bytes = password_hash.encode('utf-8')

        return bcrypt.checkpw(password_bytes, password_hash_bytes)
