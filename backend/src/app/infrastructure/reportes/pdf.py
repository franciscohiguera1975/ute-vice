"""Exportador a PDF."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.domain.enums import FormatoReporte
from app.domain.errors import ReporteDemasiadoAncho
from app.domain.ports.reportes import ArchivoReporte, ColumnaReporte, TablaReporte
from app.infrastructure.reportes.formato import a_local, formatear, nombre_archivo

_AZUL = colors.HexColor("#1F3864")
_GRIS = colors.HexColor("#F2F2F2")
_BORDE = colors.HexColor("#BFBFBF")

#: Un PDF no es el formato para volcar decenas de miles de filas: se corta y se
#: advierte en el propio documento, en lugar de generar un archivo inmanejable.
_MAX_FILAS_PDF = 5_000

#: Relleno lateral de cada celda, en puntos. Lo aplica el estilo de la tabla.
_RELLENO_CELDA = 8.0

#: Ancho minimo de una columna. Por debajo de esto no cabe ni un carácter entre
#: los rellenos, y `reportlab` aborta el armado con un ancho negativo.
_ANCHO_MINIMO_COLUMNA = _RELLENO_CELDA + 8.0


class ExportadorPDF:
    """Implementacion del puerto `ExportadorReporte` para documentos imprimibles.

    Orientacion apaisada y anchos de columna proporcionales a los declarados, de
    modo que una tabla ancha siga siendo legible en A4.
    """

    def __init__(self, max_filas: int = _MAX_FILAS_PDF) -> None:
        self._max_filas = max_filas

    @property
    def formato(self) -> FormatoReporte:
        return FormatoReporte.PDF

    @property
    def tipo_mime(self) -> str:
        return "application/pdf"

    @property
    def extension(self) -> str:
        return "pdf"

    def exportar(self, tabla: TablaReporte) -> ArchivoReporte:
        buffer = BytesIO()
        documento = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            leftMargin=12 * mm,
            rightMargin=12 * mm,
            topMargin=12 * mm,
            bottomMargin=14 * mm,
            title=tabla.titulo,
            author="UTE — Vicerrectorado",
        )

        elementos: list[Any] = []
        estilos = self._estilos()

        elementos.append(Paragraph("UNIVERSIDAD TECNOLOGICA EQUINOCCIAL", estilos["institucion"]))
        elementos.append(Paragraph(tabla.titulo, estilos["titulo"]))
        if tabla.subtitulo:
            elementos.append(Paragraph(tabla.subtitulo, estilos["subtitulo"]))

        marca = a_local(tabla.generado_en).strftime("%d/%m/%Y %H:%M")
        pie = f"Generado: {marca}"
        if tabla.generado_por:
            pie += f" &nbsp;·&nbsp; Por: {tabla.generado_por}"
        pie += f" &nbsp;·&nbsp; Registros: {tabla.total_filas:,}".replace(",", ".")
        elementos.append(Paragraph(pie, estilos["meta"]))

        if tabla.filtros_aplicados:
            filtros = " &nbsp;·&nbsp; ".join(
                f"<b>{k}</b>: {v}" for k, v in tabla.filtros_aplicados.items()
            )
            elementos.append(Paragraph(f"Filtros — {filtros}", estilos["filtros"]))

        elementos.append(Spacer(1, 6 * mm))

        filas = tabla.filas[: self._max_filas]
        truncado = len(tabla.filas) > self._max_filas

        if filas:
            elementos.append(self._construir_tabla(tabla, filas, estilos))
        else:
            elementos.append(
                Paragraph("No hay registros que coincidan con los filtros.", estilos["meta"])
            )

        if truncado:
            elementos.append(Spacer(1, 4 * mm))
            elementos.append(
                Paragraph(
                    f"<b>Aviso:</b> se muestran las primeras {self._max_filas:,} filas "
                    f"de {tabla.total_filas:,}. Para el conjunto completo, exporte "
                    "en Excel o CSV.".replace(",", "."),
                    estilos["aviso"],
                )
            )

        if tabla.totales:
            elementos.append(Spacer(1, 5 * mm))
            resumen = " &nbsp;&nbsp;|&nbsp;&nbsp; ".join(
                f"<b>{k}:</b> {v}" for k, v in tabla.totales.items()
            )
            elementos.append(Paragraph(resumen, estilos["totales"]))

        documento.build(elementos, onLaterPages=self._numerar, onFirstPage=self._numerar)

        return ArchivoReporte(
            nombre_archivo=nombre_archivo(tabla.titulo, self.extension, tabla.generado_en),
            contenido=buffer.getvalue(),
            tipo_mime=self.tipo_mime,
            formato=self.formato,
        )

    # ------------------------------------------------------------ internos
    def _estilos(self) -> dict[str, ParagraphStyle]:
        base = getSampleStyleSheet()
        return {
            "institucion": ParagraphStyle(
                "institucion",
                parent=base["Normal"],
                fontSize=12,
                textColor=_AZUL,
                alignment=TA_CENTER,
                spaceAfter=2,
                fontName="Helvetica-Bold",
            ),
            "titulo": ParagraphStyle(
                "titulo",
                parent=base["Normal"],
                fontSize=14,
                alignment=TA_CENTER,
                spaceAfter=2,
                fontName="Helvetica-Bold",
            ),
            "subtitulo": ParagraphStyle(
                "subtitulo",
                parent=base["Normal"],
                fontSize=9.5,
                alignment=TA_CENTER,
                textColor=colors.HexColor("#595959"),
                spaceAfter=3,
                fontName="Helvetica-Oblique",
            ),
            "meta": ParagraphStyle(
                "meta",
                parent=base["Normal"],
                fontSize=8,
                alignment=TA_CENTER,
                textColor=colors.HexColor("#808080"),
            ),
            "filtros": ParagraphStyle(
                "filtros",
                parent=base["Normal"],
                fontSize=8,
                alignment=TA_CENTER,
                textColor=colors.HexColor("#806000"),
                spaceBefore=3,
            ),
            "celda": ParagraphStyle(
                "celda",
                parent=base["Normal"],
                fontSize=7,
                leading=8.5,
                alignment=TA_LEFT,
            ),
            "celda_cabecera": ParagraphStyle(
                "celda_cabecera",
                parent=base["Normal"],
                fontSize=7.5,
                leading=9,
                alignment=TA_CENTER,
                textColor=colors.white,
                fontName="Helvetica-Bold",
            ),
            "totales": ParagraphStyle(
                "totales",
                parent=base["Normal"],
                fontSize=9,
                alignment=TA_LEFT,
            ),
            "aviso": ParagraphStyle(
                "aviso",
                parent=base["Normal"],
                fontSize=8,
                textColor=colors.HexColor("#9C4500"),
            ),
        }

    def _construir_tabla(
        self, tabla: TablaReporte, filas: list[dict[str, Any]], estilos: dict[str, ParagraphStyle]
    ) -> Table:
        datos: list[list[Any]] = [
            [Paragraph(c.titulo, estilos["celda_cabecera"]) for c in tabla.columnas]
        ]
        for fila in filas:
            datos.append(
                [
                    Paragraph(_escapar(formatear(fila.get(c.clave), c.tipo)), estilos["celda"])
                    for c in tabla.columnas
                ]
            )

        objeto = Table(datos, colWidths=self._anchos(tabla.columnas), repeatRows=1)
        objeto.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), _AZUL),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("GRID", (0, 0), (-1, -1), 0.4, _BORDE),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _GRIS]),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        return objeto

    @staticmethod
    def _anchos(columnas: list[ColumnaReporte]) -> list[float]:
        """Reparte el ancho util en proporcion al ancho declarado.

        Si alguna columna queda por debajo del minimo, la tabla no cabe en la
        pagina. Se dice asi, con la alternativa, en lugar de dejar que
        `reportlab` falle a mitad del armado con un ancho negativo.
        """
        disponible = landscape(A4)[0] - 24 * mm
        total = sum(c.ancho for c in columnas) or 1
        anchos = [disponible * c.ancho / total for c in columnas]

        if anchos and min(anchos) < _ANCHO_MINIMO_COLUMNA:
            raise ReporteDemasiadoAncho(len(columnas), int(disponible // _ANCHO_MINIMO_COLUMNA))
        return anchos

    @staticmethod
    def _numerar(lienzo: Any, documento: Any) -> None:
        lienzo.saveState()
        lienzo.setFont("Helvetica", 7)
        lienzo.setFillColor(colors.HexColor("#808080"))
        lienzo.drawCentredString(landscape(A4)[0] / 2, 8 * mm, f"Pagina {documento.page}")
        lienzo.drawRightString(landscape(A4)[0] - 12 * mm, 8 * mm, "Documento de uso interno — UTE")
        lienzo.restoreState()


def _escapar(texto: str) -> str:
    """Escapa los caracteres que ReportLab interpreta como marcado."""
    return texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
