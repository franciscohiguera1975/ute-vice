"""matricula estudiantil

Tres tablas nuevas para cargar el reporte de matricula estudiantil de Banner
(`ReporteAcademico-*.xlsx`, hoja `RptEstBannerMatriculas`): `estudiantes`,
`matriculas_estudiante` y `becas_estudiante`. Alimentan al futuro Tablero
Docente, que calculara la relacion estudiantes/docente por carrera; esta
migracion solo crea el almacenamiento, no ese calculo.

`estudiantes.cedula` **no lleva `UniqueConstraint`**, a diferencia de
`docentes.identificacion`: Banner permite que un mismo estudiante aparezca dos
veces en el mismo periodo cuando tiene doble matricula -distinta carrera o
sede-, y el importador no debe forzar una identidad unica que el origen no
garantiza.

`matriculas_estudiante.carrera_id` es nullable y apunta a `cat_carreras`: se
resuelve por igualdad exacta de nombre contra el catalogo del distributivo
docente, y queda en blanco cuando no hay coincidencia -nunca se crea una
carrera nueva desde esta carga-. `periodo` es el codigo de seis digitos que
trae Banner (`262651`), sin relacion con `cat_paos` -ese catalogo usa el
digito de nivel `15`/`65`/`75`, los esquemas no calzan-.

`(estudiante_id, periodo, carrera, sede)` es la clave natural de una
matricula: `postgresql_nulls_not_distinct` evita que dos matriculas sin sede
del mismo estudiante y periodo se traten como distintas solo por tener la
sede en blanco.

`becas_estudiante` guarda una fila por beca individual: el origen puede traer
varias en una misma celda -beca deportiva y descuento por hermano a la vez-,
separadas por coma.

ID de revision: de8cdc0be23e
Revision anterior: b54f7072c10c
Fecha: 2026-10-27 02:52:32.945200+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "de8cdc0be23e"
down_revision: str | None = "b54f7072c10c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "estudiantes",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("cedula", sa.String(length=20), nullable=False),
        sa.Column("id_banner", sa.String(length=20), nullable=True),
        sa.Column("nombre", sa.String(length=200), nullable=False),
        sa.Column("genero_id", sa.UUID(), nullable=True),
        sa.Column("mail_personal", sa.String(length=200), nullable=True),
        sa.Column("mail_ute", sa.String(length=200), nullable=True),
        sa.Column("telefono_celular", sa.String(length=32), nullable=True),
        sa.Column("telefono_fijo", sa.String(length=32), nullable=True),
        sa.Column("fecha_nacimiento", sa.Date(), nullable=True),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["genero_id"],
            ["cat_generos.id"],
            name=op.f("fk_estudiantes_genero_id_cat_generos"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_estudiantes")),
    )
    # Sin `unique=True`: Banner repite la misma cedula cuando el estudiante
    # tiene doble matricula -distinta carrera o sede- el mismo periodo.
    op.create_index("ix_estudiantes_cedula", "estudiantes", ["cedula"], unique=False)

    op.create_table(
        "matriculas_estudiante",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("estudiante_id", sa.UUID(), nullable=False),
        sa.Column("periodo", sa.String(length=6), nullable=False),
        sa.Column("sede", sa.String(length=100), nullable=True),
        sa.Column("facultad", sa.String(length=200), nullable=True),
        sa.Column("carrera", sa.String(length=255), nullable=True),
        sa.Column("carrera_id", sa.UUID(), nullable=True),
        sa.Column("tipo_carrera", sa.String(length=64), nullable=True),
        sa.Column("modalidad", sa.String(length=64), nullable=True),
        sa.Column("nivel_formacion_1", sa.String(length=64), nullable=True),
        sa.Column("nivel_formacion_2", sa.String(length=100), nullable=True),
        sa.Column("tipo_estudiante", sa.String(length=32), nullable=True),
        sa.Column("sistema", sa.String(length=32), nullable=True),
        sa.Column("matriculado", sa.String(length=32), nullable=True),
        sa.Column("solicitud_retiro", sa.Text(), nullable=True),
        sa.Column("bloqueo_plataforma", sa.Boolean(), nullable=False),
        sa.Column("estado", sa.String(length=16), nullable=True),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["estudiante_id"],
            ["estudiantes.id"],
            name=op.f("fk_matriculas_estudiante_estudiante_id_estudiantes"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["carrera_id"],
            ["cat_carreras.id"],
            name=op.f("fk_matriculas_estudiante_carrera_id_cat_carreras"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_matriculas_estudiante")),
        sa.UniqueConstraint(
            "estudiante_id",
            "periodo",
            "carrera",
            "sede",
            name="uq_matriculas_estudiante_natural",
            postgresql_nulls_not_distinct=True,
        ),
    )
    op.create_index(
        "ix_matriculas_estudiante_periodo", "matriculas_estudiante", ["periodo"], unique=False
    )
    op.create_index(
        "ix_matriculas_estudiante_carrera", "matriculas_estudiante", ["carrera_id"], unique=False
    )

    op.create_table(
        "becas_estudiante",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("matricula_id", sa.UUID(), nullable=False),
        sa.Column("codigo_beca", sa.String(length=32), nullable=True),
        sa.Column("financiamiento", sa.String(length=32), nullable=True),
        sa.Column("tipo_beca", sa.String(length=100), nullable=True),
        sa.Column("porcentaje", sa.Float(), nullable=True),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["matricula_id"],
            ["matriculas_estudiante.id"],
            name=op.f("fk_becas_estudiante_matricula_id_matriculas_estudiante"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_becas_estudiante")),
    )
    op.create_index(
        "ix_becas_estudiante_matricula", "becas_estudiante", ["matricula_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_becas_estudiante_matricula", table_name="becas_estudiante")
    op.drop_table("becas_estudiante")

    op.drop_index("ix_matriculas_estudiante_carrera", table_name="matriculas_estudiante")
    op.drop_index("ix_matriculas_estudiante_periodo", table_name="matriculas_estudiante")
    op.drop_table("matriculas_estudiante")

    op.drop_index("ix_estudiantes_cedula", table_name="estudiantes")
    op.drop_table("estudiantes")
