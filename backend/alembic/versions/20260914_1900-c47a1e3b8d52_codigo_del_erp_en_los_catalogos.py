"""codigo del erp en los catalogos

El ERP academico nombra las unidades con codigos de dos letras —`FS`, `FD`,
`TT`— que no coinciden con los del consolidado del distributivo. Reconciliar los
dos mundos a mano, cada vez que llega un reporte del SICAF, era una traduccion
que nadie tenia escrita en ninguna parte.

`codigo_erp` se agrega a **los doce catalogos** y no solo a facultades: el
SICAF trae tambien `COD_CARRERA` y `COD_PERIODO`, y el dia que haga falta
reconciliarlos la columna ya estara.

**No es unico, y no puede serlo.** Dos unidades de aqui pueden ser una sola
alla:

    FCSEE  ─┐
            ├─► FS   CIENCIAS DE LA SALUD EUGENIO ESPEJO
    PFCSEE ─┘

    ETECH  ─┐
            ├─► TT   UNIDAD ACADEMICA ESPECIALIZADA EN LA FORMACION
    UAEFTT ─┘         TECNICA Y TECNOLOGICA

La identidad sigue siendo `codigo`; `codigo_erp` solo sirve para reconciliar.

De paso, las facultades reciben **nombre**: hasta ahora `nombre` repetia la
sigla —`FCSEE` se llamaba «FCSEE»— porque el consolidado no traia mas. Se les
pone el nombre oficial del ERP. No a todas se les antepone «Facultad de»: un
centro y una unidad academica no lo son, y llamar «Facultad de Centro de
Educacion en Linea» a `CEL` seria peor que dejarlo como esta.

La vuelta atras restaura los nombres anteriores —la sigla— y descarta la
columna.

Revision ID: c47a1e3b8d52
Revises: 1fe3adf26d90
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "c47a1e3b8d52"
down_revision: str | None = "1fe3adf26d90"
branch_labels: str | None = None
depends_on: str | None = None


#: Los doce catalogos. La columna va en todos porque el mixin es compartido:
#: dejarla solo en facultades obligaria a romper el modelo comun.
_TABLAS = (
    "cat_paos",
    "cat_facultades",
    "cat_carreras",
    "cat_sedes",
    "cat_titularidades",
    "cat_dedicaciones",
    "cat_categorias",
    "cat_niveles",
    "cat_titulos_profesionales",
    "cat_tipos_titulo",
    "cat_generos",
    "cat_asignaturas",
)

#: `codigo local -> (codigo del ERP, nombre oficial)`.
#:
#: El mapeo no se dedujo de las siglas sino de las carreras: se comprobo contra
#: los reportes del SICAF que las carreras de cada unidad local son las que el
#: ERP agrupa bajo ese codigo. `CEL` sale de Computacion y Talento Humano,
#: `FCIC` de Ingenieria Civil, `PFCSEE` de las especializaciones medicas.
_FACULTADES = {
    "CEL": ("CL", "Centro de Educación en Línea"),
    "ETECH": ("TT", "Unidad Académica Especializada en la Formación Técnica y Tecnológica"),
    "FAU": ("FU", "Facultad de Arquitectura y Urbanismo"),
    "FCGT": ("FG", "Facultad de Ciencias Gastronómicas y Turismo"),
    "FCIC": ("FC", "Facultad de Ciencias, Ingeniería y Construcción"),
    "FCII": ("FI", "Facultad de Ciencias de la Ingeniería e Industrias"),
    "FCSEE": ("FS", "Facultad de Ciencias de la Salud Eugenio Espejo"),
    "FDCAS": ("FD", "Facultad de Derecho, Ciencias Administrativas y Sociales"),
    "FMVA": ("FV", "Facultad de Medicina Veterinaria y Agronomía"),
    "FO": ("FO", "Facultad de Odontología"),
    "PEL": ("PL", "Posgrados en Línea"),
    "PFCSEE": ("FS", "Posgrados de la Facultad de Ciencias de la Salud Eugenio Espejo"),
    "UAEFTT": ("TT", "Unidad Académica Especializada en la Formación Técnica y Tecnológica"),
}


def upgrade() -> None:
    for tabla in _TABLAS:
        op.add_column(
            tabla,
            sa.Column("codigo_erp", sa.String(length=64), nullable=False, server_default=""),
        )
        # El `server_default` existe solo para poblar las filas que ya estaban;
        # se retira para que el valor lo ponga la aplicacion.
        op.alter_column(tabla, "codigo_erp", server_default=None)

    conexion = op.get_bind()
    for codigo, (erp, nombre) in _FACULTADES.items():
        conexion.execute(
            sa.text(
                "UPDATE cat_facultades SET codigo_erp = :erp, nombre = :nombre "
                "WHERE codigo = :codigo"
            ),
            {"erp": erp, "nombre": nombre, "codigo": codigo},
        )


def downgrade() -> None:
    conexion = op.get_bind()
    # El nombre anterior era la propia sigla: se restituye antes de perder la
    # columna que permitiria distinguir cual se habia tocado.
    conexion.execute(sa.text("UPDATE cat_facultades SET nombre = codigo WHERE codigo_erp <> ''"))
    for tabla in _TABLAS:
        op.drop_column(tabla, "codigo_erp")
