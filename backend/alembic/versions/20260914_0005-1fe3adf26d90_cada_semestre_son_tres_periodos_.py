"""cada semestre son tres periodos academicos

La institucion planifica por separado la oferta tecnologica, la de grado y la de
posgrado. Un semestre calendario —`2026-1`— no es un periodo academico sino
tres, cada uno con su codigo institucional de seis digitos:

    2 6 1 65 1
    │ │ │ │  └─ constante
    │ │ │ └──── nivel: 15 tecnologia · 65 grado · 75 posgrado
    │ │ └────── periodo del anio (1 o 2)
    └─┴──────── dos ultimos digitos del anio

Esta migracion parte los trece periodos existentes en los treinta y uno que
corresponden —no son treinta y nueve: no todos los semestres tienen los tres
niveles— y reasigna cada fila del distributivo al suyo.

**A que periodo va cada fila**, en este orden:

1. Facultad `ETECH` o `UAEFTT` → tecnologia, sin mirar el nivel. Esas unidades
   imparten tecnologia aunque sus filas vengan etiquetadas como grado.
2. Si no, manda la columna `NIVEL`.
3. Si `NIVEL` esta vacia —pasa en las 731 filas de 2026-1— se toma del segmento
   central del nombre de la carrera, que ahi tiene la forma
   `SEDE:NOMBRE - NIVEL - MODALIDAD`.
4. Sin ninguna de las dos, grado, que es el caso mayoritario.

El `orden` **no** distingue el nivel: los tres periodos de un semestre comparten
`anio * 10 + periodo`. Es deliberado, porque el reporte deriva el anio
dividiendo `orden` entre diez y esa division debe seguir dando el anio.

La vuelta atras rehace los trece periodos originales y devuelve cada fila al
suyo, leyendo el semestre de los atributos. No se pierde nada en ninguna
direccion.

ID de revision: 1fe3adf26d90
Revision anterior: e0bca8427c85
Fecha: 2026-09-14 00:05:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "1fe3adf26d90"
down_revision: str | None = "e0bca8427c85"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


#: Facultades cuya oferta es tecnologica.
_TECNOLOGICAS = ("ETECH", "UAEFTT")

#: Digitos centrales del codigo, por nivel.
_DIGITOS = {"TECNOLOGIA": "15", "GRADO": "65", "POSGRADO": "75"}
_ETIQUETAS = {"TECNOLOGIA": "TECNOLOGÍA", "GRADO": "GRADO", "POSGRADO": "POSGRADO"}


def _clasificar(facultad: str | None, nivel: str | None, carrera: str | None) -> str:
    """Reproduce en la migracion la regla de `clasificar_periodo`."""
    if (facultad or "").strip().upper() in _TECNOLOGICAS:
        return "TECNOLOGIA"

    limpio = (nivel or "").strip().upper()
    if limpio in ("GRADO", "POSGRADO"):
        return limpio

    # El segmento central de «SEDE:NOMBRE - NIVEL - MODALIDAD». Solo los
    # segmentos, no el texto entero: buscar «MAESTRIA» en cualquier parte
    # clasificaria como posgrado carreras de grado que la mencionan.
    for segmento in [p.strip().upper() for p in str(carrera or "").split(" - ")][1:]:
        if segmento in ("GRADO", "POSGRADO"):
            return segmento
    return "GRADO"


def upgrade() -> None:
    conexion = op.get_bind()

    # --- Que periodos hacen falta, y a cual va cada fila -------------------
    filas = (
        conexion.execute(
            sa.text(
                """
            SELECT d.id            AS fila_id,
                   p.atributos->>'anio'    AS anio,
                   p.atributos->>'periodo' AS periodo,
                   f.codigo        AS facultad,
                   n.nombre        AS nivel,
                   c.codigo        AS carrera
              FROM distributivo AS d
              JOIN cat_paos       AS p ON p.id = d.pao_id
              JOIN cat_facultades AS f ON f.id = d.facultad_id
              LEFT JOIN cat_niveles  AS n ON n.id = d.nivel_id
              LEFT JOIN cat_carreras AS c ON c.id = d.carrera_id
            """
            )
        )
        .mappings()
        .all()
    )

    destino: dict[str, list[str]] = {}
    for fila in filas:
        nivel = _clasificar(fila["facultad"], fila["nivel"], fila["carrera"])
        anio, periodo = int(fila["anio"]), int(fila["periodo"])
        codigo = f"{anio % 100:02d}{periodo}{_DIGITOS[nivel]}1"
        destino.setdefault(codigo, []).append(str(fila["fila_id"]))

    # --- Se crean los periodos nuevos -------------------------------------
    for codigo in sorted(destino):
        anio = 2000 + int(codigo[:2])
        periodo = int(codigo[2])
        nivel = next(k for k, v in _DIGITOS.items() if v == codigo[3:5])
        semestre = f"{anio}-{periodo}"
        conexion.execute(
            sa.text(
                """
                INSERT INTO cat_paos
                       (codigo, nombre, descripcion, clave_busqueda, activo, orden, atributos)
                VALUES (:codigo, :nombre, '', :clave, true, :orden, CAST(:atributos AS jsonb))
                ON CONFLICT (codigo) DO NOTHING
                """
            ),
            {
                "codigo": codigo,
                "nombre": f"{semestre} {_ETIQUETAS[nivel]}",
                "clave": f"{codigo} {semestre} {_ETIQUETAS[nivel]}".lower(),
                "orden": anio * 10 + periodo,
                "atributos": (
                    f'{{"anio": {anio}, "periodo": {periodo}, '
                    f'"nivel": "{nivel}", "semestre": "{semestre}"}}'
                ),
            },
        )

    # --- Se reasigna cada fila --------------------------------------------
    for codigo, ids in destino.items():
        conexion.execute(
            sa.text(
                """
                UPDATE distributivo
                   SET pao_id = (SELECT id FROM cat_paos WHERE codigo = :codigo)
                 WHERE id = ANY(CAST(:ids AS uuid[]))
                """
            ),
            {"codigo": codigo, "ids": ids},
        )

    # --- Fuera los periodos viejos, que ya no referencia nadie -------------
    conexion.execute(sa.text("DELETE FROM cat_paos WHERE codigo LIKE '____-_'"))


def downgrade() -> None:
    conexion = op.get_bind()

    # Se rehacen los semestres originales a partir de los atributos.
    semestres = (
        conexion.execute(
            sa.text("SELECT DISTINCT atributos->>'semestre' AS semestre FROM cat_paos")
        )
        .scalars()
        .all()
    )

    for semestre in sorted(s for s in semestres if s):
        anio, periodo = semestre.split("-")
        conexion.execute(
            sa.text(
                """
                INSERT INTO cat_paos
                       (codigo, nombre, descripcion, clave_busqueda, activo, orden, atributos)
                VALUES (:codigo, :nombre, '', :clave, true, :orden, CAST(:atributos AS jsonb))
                ON CONFLICT (codigo) DO NOTHING
                """
            ),
            {
                # Tres parametros distintos y no uno repetido: las columnas son
                # de tipos distintos y el driver no puede deducir uno solo.
                "codigo": semestre,
                "nombre": semestre,
                "clave": semestre,
                "orden": int(anio) * 10 + int(periodo),
                "atributos": f'{{"anio": {int(anio)}, "periodo": {int(periodo)}}}',
            },
        )

    conexion.execute(
        sa.text(
            """
            UPDATE distributivo AS d
               SET pao_id = viejo.id
              FROM cat_paos AS nuevo
              JOIN cat_paos AS viejo ON viejo.codigo = nuevo.atributos->>'semestre'
             WHERE d.pao_id = nuevo.id
            """
        )
    )

    conexion.execute(sa.text("DELETE FROM cat_paos WHERE codigo NOT LIKE '____-_'"))
