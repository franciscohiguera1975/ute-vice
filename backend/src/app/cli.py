"""Comandos de consola.

    python -m app.cli seed        # roles, permisos y superusuario inicial
    python -m app.cli seed-demo   # datos ficticios para probar la aplicacion
    python -m app.cli importar-distributivo <archivo.xlsx>   # consolidado real
    python -m app.cli importar-materias <archivo.xlsx>       # materias por docente
    python -m app.cli limpiar     # mantenimiento: purga tokens vencidos
    python -m app.cli info        # configuracion efectiva, sin secretos

Los comandos usan los mismos casos de uso y repositorios que la API. No hay una
segunda via de escritura a la base: si una regla de negocio impide algo desde la
interfaz, tambien lo impide desde aqui.
"""

from __future__ import annotations

import asyncio
import json
import random
import sys
from datetime import date

from app.core.config import get_settings
from app.core.logging import configurar_logging, get_logger
from app.domain.entities.auth import Usuario
from app.domain.entities.persona import Persona
from app.domain.enums import (
    PERMISOS_POR_ROL,
    Permiso,
    RolCodigo,
    TipoVinculacion,
)
from app.domain.value_objects import Cedula, ContrasenaEnClaro, Email, NombrePersona
from app.infrastructure.contenedor import Contenedor
from app.infrastructure.db.modelos import PermisoModel, RolModel

log = get_logger("app.cli")


# ---------------------------------------------------------------------------
# Siembra inicial
# ---------------------------------------------------------------------------


async def sembrar() -> None:
    """Crea permisos, roles del sistema y el superusuario inicial.

    Es idempotente: ejecutarlo varias veces no duplica nada y actualiza los
    permisos de los roles del sistema si el catalogo crecio en una version
    nueva. Eso permite llamarlo en cada despliegue sin condicionales.
    """
    from sqlalchemy import select

    settings = get_settings()

    # Se valida antes de tocar la base: si la contrasena no cumple la politica,
    # es mejor no dejar la siembra a medias.
    try:
        ContrasenaEnClaro(
            settings.first_superuser_password,
            longitud_minima=settings.security.password_min_length,
        )
    except Exception as exc:
        print(f"  ERROR: FIRST_SUPERUSER_PASSWORD no cumple la politica: {exc}")
        print("  Ajuste la variable en el archivo .env y vuelva a ejecutar.")
        sys.exit(1)

    contenedor = Contenedor(settings)

    async with contenedor.fabrica_sesiones() as sesion:
        # --- Permisos ---
        existentes = {fila.codigo for fila in (await sesion.scalars(select(PermisoModel))).all()}
        nuevos = 0
        for permiso in Permiso:
            if permiso.value in existentes:
                continue
            modulo, accion = permiso.value.split(":", 1)
            sesion.add(
                PermisoModel(
                    codigo=permiso.value,
                    nombre=f"{accion.capitalize()} {modulo}",
                    descripcion=f"Permite {accion} en el modulo de {modulo}",
                    modulo=modulo,
                )
            )
            nuevos += 1
        await sesion.flush()
        print(f"  permisos: {len(list(Permiso))} en catalogo ({nuevos} nuevos)")

        # --- Roles ---
        catalogo_permisos = {
            fila.codigo: fila for fila in (await sesion.scalars(select(PermisoModel))).all()
        }
        from sqlalchemy.orm import selectinload

        for codigo, permisos in PERMISOS_POR_ROL.items():
            modelo = await sesion.scalar(
                select(RolModel)
                .options(selectinload(RolModel.permisos))
                .where(RolModel.codigo == codigo.value)
            )
            if modelo is None:
                modelo = RolModel(
                    codigo=codigo.value,
                    nombre=codigo.value.capitalize(),
                    descripcion=_DESCRIPCION_ROLES[codigo],
                    es_sistema=True,
                )
                sesion.add(modelo)
            # Se resincronizan siempre: si una version agrega un permiso, los
            # roles del sistema deben recibirlo sin intervencion manual.
            modelo.permisos = [
                catalogo_permisos[p.value] for p in permisos if p.value in catalogo_permisos
            ]
            print(f"  rol {codigo.value:12s} -> {len(modelo.permisos)} permisos")

        # Se confirma aqui: el superusuario se crea con la unidad de trabajo,
        # que abre su propia sesion y no veria estos roles sin confirmar.
        await sesion.commit()

        # --- Superusuario ---
        uow = contenedor.unidad_de_trabajo()
        async with uow:
            email = Email(settings.first_superuser_email)
            if await uow.usuarios.existe_email(email):
                print(f"  superusuario: ya existe ({email})")
            else:
                rol_admin = await uow.roles.obtener_por_codigo(RolCodigo.ADMIN.value)
                assert rol_admin is not None
                await uow.usuarios.agregar(
                    Usuario(
                        email=email,
                        nombre_completo=settings.first_superuser_name,
                        hash_contrasena=contenedor.hasher.hashear(
                            settings.first_superuser_password
                        ),
                        roles={rol_admin},
                        es_superusuario=True,
                        debe_cambiar_contrasena=True,
                    )
                )
                await uow.commit()
                print(f"  superusuario creado: {email}")
                print("  IMPORTANTE: cambie la contrasena en el primer acceso")

    await contenedor.cerrar()


_DESCRIPCION_ROLES: dict[RolCodigo, str] = {
    RolCodigo.ADMIN: "Control total del sistema, incluida la gestion de usuarios y roles",
    RolCodigo.COORDINADOR: (
        "Gestiona personas y titulos, administra campanas de consulta y emite reportes"
    ),
    RolCodigo.ANALISTA: ("Edita titulos, resuelve desafios de verificacion y emite reportes"),
    RolCodigo.CONSULTA: "Acceso de solo lectura a personas, titulos y tablero",
}


# ---------------------------------------------------------------------------
# Datos de demostracion
# ---------------------------------------------------------------------------

_NOMBRES = (
    "Ana Maria",
    "Luis Fernando",
    "Carmen Elena",
    "Jorge Andres",
    "Maria Jose",
    "Diego Sebastian",
    "Patricia Alexandra",
    "Carlos Eduardo",
    "Veronica Isabel",
    "Santiago Rafael",
    "Gabriela Cristina",
    "Marco Antonio",
    "Silvia Beatriz",
    "Pablo Esteban",
    "Monica Lucia",
    "Ricardo Javier",
    "Elena Sofia",
    "Andres Felipe",
)
_APELLIDOS = (
    "Yepez Cordova",
    "Munoz Salazar",
    "Cevallos Ponce",
    "Andrade Villacis",
    "Jaramillo Vega",
    "Espinoza Tapia",
    "Zambrano Mera",
    "Guerrero Paredes",
    "Toapanta Chicaiza",
    "Valencia Ortiz",
    "Moreira Bravo",
    "Carrion Bustamante",
    "Naranjo Sandoval",
    "Freire Constante",
    "Lopez Aguirre",
    "Rivadeneira Salas",
)
_UNIDADES = (
    "Facultad de Ciencias de la Ingenieria e Industrias",
    "Facultad de Ciencias Sociales y Comunicacion",
    "Facultad de Ciencias de la Salud",
    "Facultad de Ciencias Economicas y Negocios",
    "Direccion de Talento Humano",
    "Direccion de Tecnologias de la Informacion",
    "Vicerrectorado Academico",
    "Secretaria General",
)
_CARGOS = (
    "Docente titular",
    "Docente ocasional",
    "Coordinador de carrera",
    "Analista administrativo",
    "Director de area",
    "Asistente academico",
    "Tecnico de laboratorio",
    "Especialista de sistemas",
)


def _cedula_valida(rng: random.Random) -> str:
    """Genera una cedula que pasa la verificacion de modulo 10.

    Se calcula el digito verificador en lugar de sortearlo: una cedula invalida
    seria rechazada por el dominio y el dato de demostracion no serviria.
    """
    provincia = rng.randint(1, 24)
    cuerpo = f"{provincia:02d}{rng.randint(0, 5)}{rng.randint(0, 999999):06d}"
    coeficientes = (2, 1, 2, 1, 2, 1, 2, 1, 2)
    total = 0
    for digito, coeficiente in zip(cuerpo, coeficientes, strict=True):
        producto = int(digito) * coeficiente
        total += producto - 9 if producto >= 10 else producto
    return cuerpo + str((10 - total % 10) % 10)


async def sembrar_demo(cantidad: int = 60) -> None:
    """Carga personas ficticias para poder recorrer la aplicacion."""
    settings = get_settings()
    if settings.environment.is_production:
        print("  ERROR: los datos de demostracion no se cargan en produccion")
        sys.exit(1)

    contenedor = Contenedor(settings)
    rng = random.Random(2026)
    uow = contenedor.unidad_de_trabajo()

    creadas = 0
    async with uow:
        vistas: set[str] = set()
        lote: list[Persona] = []
        while len(lote) < cantidad:
            texto = _cedula_valida(rng)
            if texto in vistas:
                continue
            vistas.add(texto)
            cedula = Cedula(texto)
            if await uow.personas.existe_cedula(cedula):
                continue

            nombres = rng.choice(_NOMBRES)
            apellidos = rng.choice(_APELLIDOS)
            usuario_correo = f"{nombres.split()[0].lower()}.{apellidos.split()[0].lower()}"
            lote.append(
                Persona(
                    cedula=cedula,
                    nombre=NombrePersona(nombres=nombres, apellidos=apellidos),
                    email_institucional=Email(f"{usuario_correo}@ute.edu.ec"),
                    telefono=f"09{rng.randint(10000000, 99999999)}",
                    tipo_vinculacion=rng.choice(list(TipoVinculacion)),
                    unidad=rng.choice(_UNIDADES),
                    cargo=rng.choice(_CARGOS),
                    codigo_empleado=f"UTE{rng.randint(1000, 9999)}",
                    fecha_ingreso=date(
                        rng.randint(2005, 2024), rng.randint(1, 12), rng.randint(1, 28)
                    ),
                    activo=rng.random() > 0.08,
                )
            )
        creadas = await uow.personas.agregar_muchas(lote)
        await uow.commit()

    print(f"  personas de demostracion creadas: {creadas}")
    print("  siguiente paso: cree un job de cobertura para poblar los titulos")
    print(
        '     POST /api/v1/consultas/jobs  {"nombre": "Carga inicial", '
        '"iniciar_inmediatamente": true}'
    )
    await contenedor.cerrar()


# ---------------------------------------------------------------------------
# Importacion del distributivo
# ---------------------------------------------------------------------------


async def importar_distributivo() -> None:
    """Carga un consolidado de distributivo docente desde un Excel.

        python -m app.cli importar-distributivo ../data/distributivo/distributivo.xlsx [hoja]

    Es idempotente en lo que importa: los docentes y los catalogos que ya
    existen se reutilizan. Las filas, en cambio, chocarian con la clave natural,
    asi que para recargar un consolidado hay que vaciar antes la tabla.
    """
    from app.application.base import ContextoEjecucion
    from app.application.casos_uso.importar_distributivo import (
        EntradaImportacion,
        ImportarDistributivo,
    )
    from app.infrastructure.importadores.distributivo_excel import LectorDistributivoExcel

    if len(sys.argv) < 3:
        print("  Uso: python -m app.cli importar-distributivo <archivo.xlsx> [hoja]")
        sys.exit(1)

    ruta = sys.argv[2]
    hoja = sys.argv[3] if len(sys.argv) > 3 else None

    contenedor = Contenedor(get_settings())
    print(f"  leyendo {ruta}…")
    filas = LectorDistributivoExcel().leer(ruta, hoja=hoja)
    print(f"  {len(filas):,} filas leidas".replace(",", "."))

    caso = ImportarDistributivo(contenedor.unidad_de_trabajo())
    resultado = await caso(EntradaImportacion(filas=tuple(filas)), ContextoEjecucion.sistema())

    print()
    print(f"  filas creadas        : {resultado.filas_creadas:,}".replace(",", "."))
    print(f"  docentes nuevos      : {resultado.docentes_creados:,}".replace(",", "."))
    print(f"  docentes ya existentes: {resultado.docentes_existentes:,}".replace(",", "."))
    print(f"  titulos profesionales : {resultado.titulos_creados:,}".replace(",", "."))

    if resultado.elementos_catalogo_creados:
        print("\n  catalogos poblados:")
        for tipo, cantidad in sorted(resultado.elementos_catalogo_creados.items()):
            print(f"      {tipo:24s} {cantidad:>6,}".replace(",", "."))

    if resultado.filas_consolidadas:
        print(
            f"\n  AVISO: {resultado.filas_consolidadas} fila(s) del origen compartian clave natural"
        )
        print("  (mismo docente, periodo, carrera y sede) y se sumaron sus horas.")
        for aviso in resultado.consolidaciones[:5]:
            filas_txt = ", ".join(str(n) for n in aviso.filas_origen)
            print(
                f"      {aviso.identificacion} {aviso.pao} {aviso.carrera[:34]:36s} "
                f"filas {filas_txt} -> {aviso.total_horas_resultante}h"
            )
        if len(resultado.consolidaciones) > 5:
            print(f"      … y {len(resultado.consolidaciones) - 5} mas")

    if resultado.rechazadas:
        print(f"\n  RECHAZADAS: {len(resultado.rechazadas)} fila(s)")
        for error in resultado.rechazadas[:10]:
            print(f"      fila {error.numero_fila:>6} {error.identificacion:12s} {error.motivo}")
        if len(resultado.rechazadas) > 10:
            print(f"      … y {len(resultado.rechazadas) - 10} mas")

    await contenedor.cerrar()


async def vaciar_distributivo() -> None:
    """Borra las filas del distributivo, conservando catalogos y docentes.

    Es el paso previo para recargar un consolidado corregido.
    """
    from typing import Any, cast

    from sqlalchemy import CursorResult, delete

    from app.infrastructure.db.modelos_distributivo import FilaDistributivoModel

    contenedor = Contenedor(get_settings())
    async with contenedor.fabrica_sesiones() as sesion:
        resultado = cast(CursorResult[Any], await sesion.execute(delete(FilaDistributivoModel)))
        await sesion.commit()
        print(f"  filas eliminadas: {resultado.rowcount:,}".replace(",", "."))
    await contenedor.cerrar()


# ---------------------------------------------------------------------------
# Mantenimiento e informacion
# ---------------------------------------------------------------------------


async def sincronizar_personas() -> None:
    """Crea registros de personas a partir del padron docente.

        python -m app.cli personas-desde-docentes

    Es idempotente: correrlo dos veces no duplica a nadie. Los docentes con
    pasaporte quedan fuera —`Persona` exige cedula, que es con lo que se
    consulta al registro nacional— y se informan al final.
    """
    from app.application.base import ContextoEjecucion
    from app.application.casos_uso.personas_desde_docentes import (
        SincronizarPersonasDesdeDocentes,
    )

    contenedor = Contenedor(get_settings())
    caso = SincronizarPersonasDesdeDocentes(contenedor.unidad_de_trabajo())
    resultado = await caso(None, ContextoEjecucion.sistema())

    print(f"  personas creadas   : {resultado.personas_creadas:,}".replace(",", "."))
    print(f"  docentes enlazados : {resultado.docentes_enlazados:,}".replace(",", "."))
    print(f"  ya tenian persona  : {resultado.ya_estaban:,}".replace(",", "."))
    print(f"  con pasaporte      : {resultado.sin_cedula:,}".replace(",", "."))

    if resultado.problemas:
        print()
        print(f"  SIN PROCESAR: {len(resultado.problemas)}")
        for detalle in resultado.problemas[:10]:
            print(f"      {detalle}")
        if len(resultado.problemas) > 10:
            print(f"      … y {len(resultado.problemas) - 10} mas")


async def restablecer_contrasena() -> None:
    """Devuelve el acceso a una cuenta que perdio su contrasena.

        python -m app.cli reset-password --email admin@ute.edu.ec [--contrasena X]

    Existe porque la contrasena del `.env` solo sirve para el alta inicial: una
    vez cambiada, ese valor ya no abre nada, y sin esta salida recuperar el
    acceso obligaria a escribir SQL contra la tabla de usuarios.

    Sin `--contrasena` genera una y la imprime. La cuenta queda obligada a
    cambiarla en el proximo acceso: una clave que paso por una terminal y por un
    registro de shell no deberia seguir siendo valida manana.
    """
    import secrets
    import string

    from app.domain.value_objects import ContrasenaEnClaro, Email

    argumentos = dict(zip(sys.argv[2::2], sys.argv[3::2], strict=False))
    correo = argumentos.get("--email")
    if not correo:
        print("  Uso: python -m app.cli reset-password --email <correo> [--contrasena <clave>]")
        sys.exit(1)

    # Con mayusculas, minusculas, digito y simbolo: la politica los exige.
    alfabeto = string.ascii_letters + string.digits
    nueva = argumentos.get("--contrasena") or (
        "".join(secrets.choice(alfabeto) for _ in range(18)) + "#7z"
    )

    contenedor = Contenedor(get_settings())
    uow = contenedor.unidad_de_trabajo()

    async with uow:
        usuario = await uow.usuarios.obtener_por_email(Email(correo))
        if usuario is None:
            print(f"  ERROR: no existe ninguna cuenta con el correo {correo}")
            sys.exit(1)

        clara = ContrasenaEnClaro(
            nueva, longitud_minima=contenedor.settings.security.password_min_length
        )
        usuario.hash_contrasena = contenedor.hasher.hashear(clara.valor)
        usuario.debe_cambiar_contrasena = True
        usuario.intentos_fallidos = 0
        usuario.bloqueado_hasta = None
        await uow.usuarios.actualizar(usuario)
        await uow.commit()

    print(f"  cuenta      : {correo}")
    print(f"  contrasena  : {nueva}")
    print("  la cuenta debera cambiarla en el proximo acceso")


async def limpiar() -> None:
    """Purga tokens de refresco vencidos."""
    from app.application.base import ContextoEjecucion
    from app.application.casos_uso.autenticacion import LimpiarTokensExpirados

    contenedor = Contenedor(get_settings())
    caso = LimpiarTokensExpirados(contenedor.unidad_de_trabajo(), contenedor.reloj)
    eliminados = await caso(None, ContextoEjecucion.sistema())
    print(f"  tokens eliminados: {eliminados}")
    await contenedor.cerrar()


async def info() -> None:
    """Imprime la configuracion efectiva, sin secretos."""
    contenedor = Contenedor(get_settings())
    print(json.dumps(contenedor.resumen_configuracion(), indent=2, ensure_ascii=False))

    politica = contenedor.politica_planificacion
    ahora_local = contenedor.reloj.ahora_local()
    franja = politica.franja_de(ahora_local)
    print(f"\n  hora local: {ahora_local:%Y-%m-%d %H:%M} ({franja.value})")
    print(f"  en horario operativo: {politica.esta_en_horario(ahora_local)}")

    uow = contenedor.unidad_de_trabajo()
    try:
        async with uow:
            activas = await uow.personas.contar_activas()
        evaluacion = politica.evaluar_factibilidad(activas)
        print(f"\n  personas activas: {activas}")
        print(f"  capacidad del periodo: {evaluacion.capacidad_del_periodo}")
        print(f"  dias necesarios para cubrirlas: {evaluacion.dias_necesarios}")
        if evaluacion.advertencia:
            print(f"\n  ADVERTENCIA: {evaluacion.advertencia}")
    except Exception as exc:
        print(f"\n  (sin acceso a la base de datos: {exc})")

    await contenedor.cerrar()


# ---------------------------------------------------------------------------


async def importar_materias() -> None:
    """Carga las materias que imparte cada docente desde un Excel.

        python -m app.cli importar-materias ../data/materias/materias_docentes.xlsx [hoja]

    Es idempotente: reemplaza las materias de cada fila que aparezca en el
    reporte, de modo que volver a cargar el mismo archivo deja el mismo
    resultado. Las filas que el reporte no menciona no se tocan.
    """
    from app.application.base import ContextoEjecucion
    from app.application.casos_uso.importar_materias import (
        EntradaImportacionMaterias,
        ImportarMaterias,
    )
    from app.infrastructure.importadores.materias_excel import LectorMateriasExcel

    if len(sys.argv) < 3:
        print("  Uso: python -m app.cli importar-materias <archivo.xlsx> [hoja]")
        sys.exit(1)

    ruta = sys.argv[2]
    hoja = sys.argv[3] if len(sys.argv) > 3 else None

    contenedor = Contenedor(get_settings())
    print(f"  leyendo {ruta}…")
    filas = LectorMateriasExcel().leer(ruta, hoja=hoja)
    print(f"  {len(filas):,} filas leidas".replace(",", "."))

    caso = ImportarMaterias(contenedor.unidad_de_trabajo())
    resultado = await caso(
        EntradaImportacionMaterias(filas=tuple(filas)), ContextoEjecucion.sistema()
    )

    print()
    print(f"  asignaturas nuevas       : {resultado.asignaturas_creadas:,}".replace(",", "."))
    print(f"  asignaturas ya existentes: {resultado.asignaturas_existentes:,}".replace(",", "."))
    print(f"  filas del distributivo   : {resultado.filas_enlazadas:,}".replace(",", "."))
    print(f"  enlaces creados          : {resultado.enlaces_creados:,}".replace(",", "."))

    if resultado.semestres_sin_periodo:
        print("\n  sin periodo academico (no son un semestre):")
        for semestre, cuantas in sorted(resultado.semestres_sin_periodo.items()):
            print(f"      {semestre:12s} {cuantas:>6}")

    if resultado.sin_destino:
        total = f"{resultado.materias_sin_destino:,}".replace(",", ".")
        print(
            f"\n  SIN DESTINO: {total} materia(s) de {len(resultado.sin_destino)} "
            "docente(s) que no constan en el distributivo de ese periodo"
        )
        for aviso in resultado.sin_destino[:10]:
            print(
                f"      {aviso.identificacion:12s} {aviso.semestre:8s} "
                f"{aviso.nombre_docente[:34]:36s} {aviso.materias:>3} materia(s)"
            )
        if len(resultado.sin_destino) > 10:
            print(f"      … y {len(resultado.sin_destino) - 10} mas")

    await contenedor.cerrar()


_COMANDOS = {
    "seed": (sembrar, "Crea permisos, roles y el superusuario inicial"),
    "seed-demo": (sembrar_demo, "Carga personas ficticias para pruebas"),
    "importar-distributivo": (
        importar_distributivo,
        "Carga un consolidado de distributivo desde un Excel",
    ),
    "importar-materias": (
        importar_materias,
        "Carga las materias que imparte cada docente desde un Excel",
    ),
    "vaciar-distributivo": (
        vaciar_distributivo,
        "Borra las filas del distributivo (conserva catalogos y docentes)",
    ),
    "personas-desde-docentes": (
        sincronizar_personas,
        "Crea registros de personas a partir del padron docente",
    ),
    "reset-password": (
        restablecer_contrasena,
        "Devuelve el acceso a una cuenta que perdio su contrasena",
    ),
    "limpiar": (limpiar, "Elimina tokens de refresco vencidos"),
    "info": (info, "Muestra la configuracion efectiva"),
}


def main() -> None:
    configurar_logging(nivel="WARNING", json_output=False)

    if len(sys.argv) < 2 or sys.argv[1] in {"-h", "--help", "help"}:
        print("\nComandos disponibles:\n")
        for nombre, (_, descripcion) in _COMANDOS.items():
            print(f"  {nombre:24s} {descripcion}")
        print("\nUso: python -m app.cli <comando>\n")
        sys.exit(0)

    comando = sys.argv[1]
    if comando not in _COMANDOS:
        print(f"Comando desconocido: {comando}")
        print(f"Validos: {', '.join(_COMANDOS)}")
        sys.exit(1)

    funcion, descripcion = _COMANDOS[comando]
    print(f"\n{descripcion}\n")
    try:
        asyncio.run(funcion())
    except KeyboardInterrupt:
        print("\nInterrumpido")
        sys.exit(130)
    print()


if __name__ == "__main__":
    main()
