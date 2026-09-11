"""Derivacion de claves con Argon2id."""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from argon2.low_level import Type


class HasherArgon2:
    """Implementacion del puerto `HasherContrasenas` con Argon2id.

    Argon2id es el algoritmo recomendado actualmente para contrasenas: resiste
    tanto ataques con GPU como los de canal lateral. Los parametros por defecto
    apuntan a ~64 MiB de memoria y tres pasadas, un coste asumible en el
    servidor y muy caro para quien intente fuerza bruta sobre un volcado.
    """

    def __init__(
        self,
        *,
        memoria_kib: int = 65_536,
        iteraciones: int = 3,
        paralelismo: int = 4,
        longitud_hash: int = 32,
        longitud_sal: int = 16,
    ) -> None:
        self._ph = PasswordHasher(
            time_cost=iteraciones,
            memory_cost=memoria_kib,
            parallelism=paralelismo,
            hash_len=longitud_hash,
            salt_len=longitud_sal,
            type=Type.ID,
        )

    def hashear(self, contrasena: str) -> str:
        return self._ph.hash(contrasena)

    def verificar(self, contrasena: str, hash_almacenado: str) -> bool:
        """Nunca propaga excepciones.

        Un hash corrupto o de otro algoritmo debe responder "no coincide", no
        reventar: un error distinto le diria al atacante algo sobre el estado
        interno de la cuenta.
        """
        try:
            return self._ph.verify(hash_almacenado, contrasena)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False

    def necesita_rehash(self, hash_almacenado: str) -> bool:
        try:
            return self._ph.check_needs_rehash(hash_almacenado)
        except (InvalidHashError, VerificationError):
            # Un hash ilegible se considera obsoleto por definicion.
            return True
