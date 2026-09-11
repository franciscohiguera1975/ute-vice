# Agregar una tabla nueva

> Procedimiento para la Fase 09, cuando el Vicerrectorado confirme que tablas
> adicionales incorporar.

## Por que esto es mecanico

La arquitectura esta pensada para esto. Una tabla nueva es una entidad, un
puerto, un adaptador, unos casos de uso y un router. **No toca nada de lo
existente**: es el principio abierto/cerrado en la practica.

El ejemplo que sigue agrega una tabla `capacitaciones` (cursos y certificaciones
no titulantes). Sustituya el nombre por el que corresponda.

---

## Backend

### 1. Entidad de dominio

`backend/src/app/domain/entities/capacitacion.py`

Una entidad con comportamiento, no un contenedor de campos. Si hay reglas
—«una capacitacion vencida no cuenta para el escalafon»— viven aqui.

```python
@dataclass(slots=True)
class Capacitacion:
    persona_id: UUID
    nombre: str
    institucion: str
    horas: int
    fecha_inicio: date
    fecha_fin: date | None = None
    certificado_numero: str | None = None
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if self.horas <= 0:
            raise ErrorValidacion("Las horas deben ser positivas", campo="horas")
        if self.fecha_fin and self.fecha_fin < self.fecha_inicio:
            raise ErrorValidacion("El fin no puede preceder al inicio", campo="fecha_fin")

    @property
    def esta_vigente(self) -> bool: ...
```

Registrela en `domain/entities/__init__.py`.

### 2. Permisos

En `domain/enums.py`, agregue al enum `Permiso`:

```python
CAPACITACIONES_LEER = "capacitaciones:leer"
CAPACITACIONES_ESCRIBIR = "capacitaciones:escribir"
```

Y asigneles roles en `PERMISOS_POR_ROL`. `ADMIN` los recibe automaticamente
(`frozenset(Permiso)`).

> `make seed` es idempotente y resincroniza los roles del sistema: al desplegar,
> los permisos nuevos llegan solos.

### 3. Puerto de repositorio

En `domain/ports/repositorios.py`:

```python
@dataclass(frozen=True, slots=True)
class FiltroCapacitaciones:
    persona_id: UUID | None = None
    institucion: str | None = None
    vigentes: bool | None = None


class RepositorioCapacitaciones(Protocol):
    async def obtener(self, id: UUID) -> Capacitacion | None: ...
    async def listar(self, filtro, paginacion) -> Pagina[Capacitacion]: ...
    async def listar_por_persona(self, persona_id: UUID) -> list[Capacitacion]: ...
    async def agregar(self, c: Capacitacion) -> Capacitacion: ...
    async def actualizar(self, c: Capacitacion) -> Capacitacion: ...
    async def eliminar(self, id: UUID) -> None: ...
```

Agreguelo tambien al protocolo `UnidadDeTrabajo` en `domain/ports/uow.py`.

### 4. Modelo ORM

En `infrastructure/db/modelos.py`. Recuerde la clave foranea a `personas` con
`ondelete="CASCADE"` y los indices que soporten los filtros del punto anterior.

### 5. Mapeadores

En `infrastructure/db/mapeadores.py`, un par `capacitacion_a_dominio` /
`capacitacion_a_modelo`, siguiendo el patron de los existentes.

### 6. Repositorio

En `infrastructure/db/repositorios/nucleo.py`, implementando el puerto. Si
admite ordenamiento, agregue un diccionario de columnas permitidas como
`_ORDEN_PERSONAS`: **el `ORDER BY` nunca debe aceptar texto libre.**

Registrelo en `UnidadDeTrabajoSQL._construir_repositorios()`.

### 7. Migracion

```bash
make migration m="agregar tabla capacitaciones"
```

**Revise el archivo generado antes de aplicarlo.** El autogenerador acierta casi
siempre, y el «casi» es lo que rompe un despliegue.

```bash
make migrate
```

### 8. Casos de uso

`application/casos_uso/capacitaciones.py`. Cada uno declara su permiso:

```python
class CrearCapacitacion(CasoDeUso[EntradaCrearCapacitacion, Capacitacion]):
    nombre = "capacitaciones.crear"
    descripcion = "Registra una capacitacion de una persona"
    permiso_requerido = Permiso.CAPACITACIONES_ESCRIBIR

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(self, entrada, contexto) -> Capacitacion:
        async with self._uow:
            ...
            await self._uow.commit()
            return creada
```

> Hay una prueba que **falla** si un caso de uso no declara `permiso_requerido`
> y no esta en la lista de exentos justificados. Es intencional.

### 9. Esquemas y router

`api/esquemas/` y `api/v1/routers/capacitaciones.py`, siguiendo el patron de
`titulos.py`. Registre el router en `api/v1/__init__.py`.

### 10. Pruebas

Como minimo:

- Unitarias de las reglas de la entidad (sin base de datos).
- Unitarias de los casos de uso con el doble en memoria.
- Un doble `RepoCapacitaciones` en `tests/conftest.py`, siguiendo el patron de
  los existentes.
- Integracion del ciclo CRUD por la API.

---

## Frontend

### 1. Modelo y puerto

En `domain/modelos/entidades.ts` la interfaz, en `domain/modelos/enums.ts` las
enumeraciones y etiquetas, y en `domain/puertos/repositorios.ts` la clase
abstracta.

### 2. Repositorio HTTP

En `data/repositorios.ts`, y registrelo en `PROVEEDORES_DATOS`. La conversion
`snake_case` ↔ `camelCase` es automatica.

### 3. Componentes y rutas

Una carpeta en `features/capacitaciones/` con sus rutas, y una entrada en
`app.routes.ts` con carga diferida y guarda de permiso.

Para que aparezca en el menu, agregue la seccion en
`shared/layout/layout.component.ts` declarando los permisos que la habilitan; la
directiva `*utePermiso` se encarga de ocultarla a quien no corresponda.

---

## Lista de verificacion

- [ ] Entidad con sus reglas, exportada en `__init__.py`
- [ ] Permisos en el enum y asignados a roles
- [ ] Puerto de repositorio y entrada en la unidad de trabajo
- [ ] Modelo ORM con indices y claves foraneas
- [ ] Mapeadores en ambos sentidos
- [ ] Repositorio con lista blanca de ordenamiento
- [ ] Migracion generada **y revisada**
- [ ] Casos de uso con `permiso_requerido`
- [ ] Esquemas y router registrados
- [ ] Doble en memoria en `conftest.py`
- [ ] Pruebas unitarias y de integracion
- [ ] Modelo, puerto y repositorio en el frontend
- [ ] Componentes, rutas y entrada de menu
- [ ] `make test` y `make lint` en verde
- [ ] Changelog de la fase en `docs/changelogs/`

---

## Errores a evitar

**Poner reglas de negocio en el repositorio o en el router.** Van en la entidad
o en el caso de uso. Si estan en el borde, no se pueden probar sin levantar todo.

**Importar SQLAlchemy en el dominio.** La prueba de arquitectura lo detecta. La
solucion es definir un puerto, no relajar la prueba.

**Aceptar texto libre en el `ORDER BY`.** Use una lista blanca de columnas.

**Olvidar la migracion.** La prueba `test_migraciones.py` compara el esquema de
las migraciones contra el de los modelos y falla si divergen — pero solo si se
ejecuta. Corra `make test` antes de dar por terminado.
