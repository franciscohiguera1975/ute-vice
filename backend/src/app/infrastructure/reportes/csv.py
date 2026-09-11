"""Exportador a CSV."""

from __future__ import annotations

import csv
from io import StringIO

from app.domain.enums import FormatoReporte
from app.domain.ports.reportes import ArchivoReporte, TablaReporte
from app.infrastructure.reportes.formato import a_local, formatear, nombre_archivo


class ExportadorCSV:
    """Implementacion del puerto `ExportadorReporte` para texto delimitado.

    Dos decisiones que evitan problemas reales:

    * **Separador `;`**. Excel en configuracion regional en espanol interpreta la
      coma como separador decimal; con `,` como delimitador, el archivo se abre
      todo en una sola columna.
    * **Codificacion UTF-8 con BOM**. Sin el BOM, Excel lee el archivo como
      Latin-1 y las tildes aparecen corrompidas.
    """

    def __init__(self, delimitador: str = ";", incluir_cabecera_informativa: bool = True) -> None:
        self._delimitador = delimitador
        self._cabecera = incluir_cabecera_informativa

    @property
    def formato(self) -> FormatoReporte:
        return FormatoReporte.CSV

    @property
    def tipo_mime(self) -> str:
        return "text/csv; charset=utf-8"

    @property
    def extension(self) -> str:
        return "csv"

    def exportar(self, tabla: TablaReporte) -> ArchivoReporte:
        buffer = StringIO()
        escritor = csv.writer(
            buffer,
            delimiter=self._delimitador,
            quoting=csv.QUOTE_MINIMAL,
            lineterminator="\r\n",
        )

        if self._cabecera and not tabla.solo_datos:
            escritor.writerow([f"# {tabla.titulo}"])
            if tabla.subtitulo:
                escritor.writerow([f"# {tabla.subtitulo}"])
            escritor.writerow(
                [f"# Generado: {a_local(tabla.generado_en).strftime('%d/%m/%Y %H:%M')}"]
            )
            if tabla.generado_por:
                escritor.writerow([f"# Por: {tabla.generado_por}"])
            if tabla.filtros_aplicados:
                filtros = "; ".join(f"{k}={v}" for k, v in tabla.filtros_aplicados.items())
                escritor.writerow([f"# Filtros: {filtros}"])
            escritor.writerow([])

        escritor.writerow([c.titulo for c in tabla.columnas])
        for fila in tabla.filas:
            escritor.writerow([formatear(fila.get(c.clave), c.tipo) for c in tabla.columnas])

        if tabla.totales:
            escritor.writerow([])
            for etiqueta, valor in tabla.totales.items():
                escritor.writerow([etiqueta, valor])

        # El BOM va delante para que Excel reconozca UTF-8.
        contenido = b"\xef\xbb\xbf" + buffer.getvalue().encode("utf-8")

        return ArchivoReporte(
            nombre_archivo=nombre_archivo(tabla.titulo, self.extension, tabla.generado_en),
            contenido=contenido,
            tipo_mime=self.tipo_mime,
            formato=self.formato,
        )
