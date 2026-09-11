"""Reconciliacion entre lo que devuelve el proveedor y lo que ya tenemos.

Este servicio responde a la pregunta central del sistema: *¿que cambio desde la
ultima vez?*. Es logica pura —entra estado, sale un plan de cambios— sin base de
datos ni red, lo que permite probar exhaustivamente cada escenario de cambio.

Los cuatro casos que distingue:

* **Nuevo**: huella ausente en nuestro registro.
* **Modificado**: misma huella, algun campo comparable cambio.
* **Sin cambios**: misma huella, contenido identico.
* **Retirado**: teniamos un titulo vigente que el proveedor ya no reporta.

El ultimo es el mas delicado. Un titulo que desaparece del registro nacional no
se borra: se marca `RETIRADO` y se deja constancia, porque justamente ese es el
hallazgo que motiva una revision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.domain.entities.consulta import CambioDetectado
from app.domain.entities.titulo import Titulo
from app.domain.enums import EstadoTitulo, NivelTitulo, OrigenTitulo, TipoCambio
from app.domain.ports.senescyt import TituloExterno
from app.domain.value_objects import ahora_utc, normalizar_texto

#: Pistas del `tipo` que reporta el proveedor cuando identifica el nivel de
#: forma inequivoca. Se consultan antes que la denominacion.
_TIPO_ESPECIFICO: tuple[tuple[str, NivelTitulo], ...] = (
    ("doctor", NivelTitulo.DOCTORADO),
    ("phd", NivelTitulo.DOCTORADO),
    ("maestr", NivelTitulo.MAESTRIA),
    ("magister", NivelTitulo.MAESTRIA),
    ("especial", NivelTitulo.ESPECIALIZACION),
    ("diplomado", NivelTitulo.ESPECIALIZACION),
    ("tecnolog", NivelTitulo.TECNOLOGICO),
    ("tecnic", NivelTitulo.TECNICO),
)

#: Categorias amplias del registro nacional. Cada una agrupa varios niveles:
#: "CUARTO NIVEL" cubre por igual una especializacion, una maestria y un
#: doctorado.
#:
#: Se declaran con los niveles que admiten y con el valor a usar cuando la
#: denominacion no aporta nada. La categoria **acota** el resultado y la
#: denominacion lo **afina dentro** de ella: asi un "ESPECIALISTA EN MEDICINA
#: INTERNA" de cuarto nivel se clasifica como especializacion, mientras que un
#: "INGENIERO EN SISTEMAS" reportado —erroneamente— como cuarto nivel no se
#: degrada a tercer nivel contradiciendo al registro oficial.
_TIPO_GENERICO: tuple[tuple[str, frozenset[NivelTitulo], NivelTitulo], ...] = (
    (
        "cuarto nivel",
        frozenset({NivelTitulo.ESPECIALIZACION, NivelTitulo.MAESTRIA, NivelTitulo.DOCTORADO}),
        NivelTitulo.MAESTRIA,
    ),
    (
        "posgrado",
        frozenset({NivelTitulo.ESPECIALIZACION, NivelTitulo.MAESTRIA, NivelTitulo.DOCTORADO}),
        NivelTitulo.MAESTRIA,
    ),
    (
        "tercer nivel",
        frozenset({NivelTitulo.TECNICO, NivelTitulo.TECNOLOGICO, NivelTitulo.TERCER_NIVEL}),
        NivelTitulo.TERCER_NIVEL,
    ),
    (
        "pregrado",
        frozenset({NivelTitulo.TECNICO, NivelTitulo.TECNOLOGICO, NivelTitulo.TERCER_NIVEL}),
        NivelTitulo.TERCER_NIVEL,
    ),
)


@dataclass(slots=True)
class PlanDeReconciliacion:
    """Resultado del analisis. Describe que hacer, sin haberlo hecho aun.

    Separar el analisis de la escritura permite auditar la decision, mostrarla
    al usuario antes de aplicarla y probarla sin tocar la base.
    """

    nuevos: list[Titulo] = field(default_factory=list)
    actualizados: list[Titulo] = field(default_factory=list)
    """Entidades existentes, ya mutadas con el contenido nuevo."""
    confirmados: list[Titulo] = field(default_factory=list)
    """Sin cambios; solo se refresca la marca de ultima aparicion."""
    retirados: list[Titulo] = field(default_factory=list)
    cambios: list[CambioDetectado] = field(default_factory=list)

    @property
    def hubo_cambios(self) -> bool:
        return bool(self.nuevos or self.actualizados or self.retirados)

    @property
    def total_reportado(self) -> int:
        return len(self.nuevos) + len(self.actualizados) + len(self.confirmados)

    def resumen(self) -> dict[str, int]:
        return {
            "nuevos": len(self.nuevos),
            "actualizados": len(self.actualizados),
            "confirmados": len(self.confirmados),
            "retirados": len(self.retirados),
        }


class ReconciliadorTitulos:
    """Compara titulos externos contra los almacenados y arma el plan."""

    def __init__(self, *, marcar_ausentes_como_retirados: bool = True) -> None:
        # Se puede desactivar cuando la consulta fue parcial: si el proveedor
        # devolvio una pagina incompleta, tratar lo ausente como retirado
        # produciria falsos positivos alarmantes.
        self._marcar_retirados = marcar_ausentes_como_retirados

    # ------------------------------------------------------------------ api
    def reconciliar(
        self,
        *,
        persona_id: UUID,
        existentes: list[Titulo],
        externos: list[TituloExterno],
        momento: datetime | None = None,
    ) -> PlanDeReconciliacion:
        momento = momento or ahora_utc()
        plan = PlanDeReconciliacion()

        indice_existentes = {t.huella: t for t in existentes}
        huellas_reportadas: set[str] = set()

        for externo in externos:
            candidato = self.mapear(externo, persona_id=persona_id, momento=momento)
            huellas_reportadas.add(candidato.huella)

            actual = indice_existentes.get(candidato.huella)
            if actual is None:
                plan.nuevos.append(candidato)
                plan.cambios.append(
                    CambioDetectado(
                        tipo=TipoCambio.TITULO_NUEVO,
                        titulo_id=candidato.id,
                        denominacion=candidato.denominacion,
                        detalle={
                            "institucion": candidato.institucion,
                            "nivel": candidato.nivel.value,
                            "numero_registro": candidato.numero_registro,
                        },
                    )
                )
                continue

            diferencias = actual.diferencias_con(candidato)
            if diferencias:
                actual.aplicar_actualizacion(candidato, momento)
                plan.actualizados.append(actual)
                plan.cambios.append(
                    CambioDetectado(
                        tipo=TipoCambio.TITULO_MODIFICADO,
                        titulo_id=actual.id,
                        denominacion=actual.denominacion,
                        detalle={"campos": diferencias},
                    )
                )
            else:
                actual.confirmar_vigencia(momento)
                plan.confirmados.append(actual)

        if self._marcar_retirados:
            plan_retirados = self._detectar_retirados(existentes, huellas_reportadas, momento)
            plan.retirados.extend(plan_retirados)
            plan.cambios.extend(
                CambioDetectado(
                    tipo=TipoCambio.TITULO_RETIRADO,
                    titulo_id=t.id,
                    denominacion=t.denominacion,
                    detalle={
                        "institucion": t.institucion,
                        "numero_registro": t.numero_registro,
                        "motivo": "Ya no aparece en el registro consultado",
                    },
                )
                for t in plan_retirados
            )

        if not plan.cambios:
            plan.cambios.append(
                CambioDetectado(
                    tipo=(
                        TipoCambio.PRIMERA_CONSULTA if not existentes else TipoCambio.SIN_CAMBIOS
                    ),
                    titulo_id=None,
                    denominacion="",
                    detalle={"titulos": len(externos)},
                )
            )

        return plan

    # --------------------------------------------------------------- mapeo
    def mapear(
        self,
        externo: TituloExterno,
        *,
        persona_id: UUID,
        momento: datetime | None = None,
    ) -> Titulo:
        """Convierte el DTO del proveedor en una entidad del dominio."""
        momento = momento or ahora_utc()
        return Titulo(
            persona_id=persona_id,
            denominacion=externo.denominacion,
            institucion=externo.institucion,
            nivel=self._resolver_nivel(externo),
            numero_registro=(externo.numero_registro or "").strip() or None,
            fecha_registro=externo.fecha_registro,
            area_conocimiento=externo.area,
            observacion_registro=externo.observacion,
            pais=(externo.pais or "ECUADOR").upper(),
            origen=OrigenTitulo.SENESCYT,
            estado=EstadoTitulo.VIGENTE,
            datos_crudos=externo.datos_crudos,
            visto_primera_vez_en=momento,
            visto_ultima_vez_en=momento,
        )

    # ------------------------------------------------------------ internos
    @staticmethod
    def _resolver_nivel(externo: TituloExterno) -> NivelTitulo:
        """Deduce el nivel academico, en tres pasos.

        1. Si el `tipo` del proveedor es especifico ("MAESTRIA", "DOCTORADO"),
           se usa: es el dato mas fiable.
        2. Si el `tipo` es una categoria amplia ("CUARTO NIVEL"), la categoria
           acota el resultado y la denominacion lo afina **dentro** de ella.
           Sin este paso, un "ESPECIALISTA EN MEDICINA INTERNA" reportado como
           cuarto nivel quedaria como maestria, que es otro nivel; con el, una
           denominacion que contradice a la categoria no la anula.
        3. Sin `tipo` utilizable, se deduce solo de la denominacion.
        """
        tipo = normalizar_texto(externo.tipo or "")

        if tipo:
            for pista, nivel in _TIPO_ESPECIFICO:
                if pista in tipo:
                    return nivel

            for pista, admitidos, generico in _TIPO_GENERICO:
                if pista in tipo:
                    inferido = Titulo.inferir_nivel(externo.denominacion)
                    return inferido if inferido in admitidos else generico

        return Titulo.inferir_nivel(externo.denominacion)

    @staticmethod
    def _detectar_retirados(
        existentes: list[Titulo],
        huellas_reportadas: set[str],
        momento: datetime,
    ) -> list[Titulo]:
        """Titulos vigentes de origen externo que el proveedor ya no reporta.

        Solo se consideran los de origen SENESCYT: un titulo cargado a mano por
        un funcionario, con documentacion fisica de respaldo, no debe marcarse
        como retirado porque el registro nacional no lo liste.
        """
        retirados: list[Titulo] = []
        for titulo in existentes:
            if titulo.huella in huellas_reportadas:
                continue
            if titulo.origen is not OrigenTitulo.SENESCYT:
                continue
            if titulo.estado is EstadoTitulo.RETIRADO:
                continue
            titulo.marcar_retirado(momento)
            retirados.append(titulo)
        return retirados
