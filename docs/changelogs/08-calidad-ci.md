# Fase 08 · Calidad y pruebas

**Fecha:** 2026-09-04 · **Estado:** en curso

## Entregado hasta ahora

### 237 pruebas del backend

| Grupo | Cantidad | Que cubre |
|---|---|---|
| Arquitectura | 5 | La regla de dependencia, verificada analizando los `import` |
| Objetos de valor | 46 | Cedula, correo, contrasena, periodo, normalizacion |
| Reconciliador | 29 | Los cuatro casos de cambio y las categorias del proveedor |
| Planificacion | 29 | Franjas, jitter, presupuesto, retroceso, factibilidad |
| Cobertura y jobs | 31 | La regla de no repetir, maquina de estados, cortacircuitos |
| Autorizacion | 23 | Permisos por rol, bloqueo de cuenta, protecciones |
| Casos de uso | 28 | Flujos completos con dobles en memoria |
| Configuracion | 20 | Lectura del entorno y cerrojo de produccion |
| Integracion | 26 | API sobre PostgreSQL real, RBAC, reportes, migraciones |

Las unitarias corren **sin Docker, sin base y sin red**. Las de integracion se
omiten solas si no hay PostgreSQL disponible, para que `pytest` siga siendo util
en una maquina sin Docker.

### La prueba de arquitectura

Analiza los `import` de cada modulo y falla si el dominio importa
infraestructura. Cuando falla, el mensaje explica que la solucion casi nunca es
relajarla, sino definir un puerto.

Sin ella, la regla se erosiona en semanas: basta un `import` de conveniencia.

### Fallos encontrados por las pruebas

Registrados en el changelog de su fase:

1. Mitigacion de temporizacion inefectiva (Fase 02)
2. `seed` fallando con la contrasena de ejemplo (Fase 02)
3. Fallo de borde en la regla de cobertura (Fase 03)
4. Reparto de items duplicando el control de ritmo (Fase 04)
5. Clasificacion incorrecta del nivel academico (Fase 04)
6. `inject()` fuera de contexto en el interceptor (Fase 06)
7. `LOCALE_ID` sin datos de configuracion regional (Fase 06)
8. **`CORS_ORIGINS` abortando el arranque** con el formato documentado en el
   propio `.env.example`: pydantic intentaba interpretarlo como JSON antes de
   llegar al validador. Habria roto el primer despliegue.

El octavo es el mas ilustrativo: era un fallo en la ruta feliz de la
configuracion de ejemplo, y solo aparecio al arrancar la aplicacion con un
`.env` realista.

### Dos fallos en las propias pruebas

Se detectaron al ejecutar clases de integracion de forma aislada, algo que hasta
entonces no se habia hecho:

9. **La bateria pasaba por accidente del orden.** El fixture que crea el esquema
   importaba `Base` pero **no los modelos**, asi que `Base.metadata` estaba
   vacio y `create_all` no creaba ninguna tabla. Funcionaba solo porque la
   primera prueba —una comprobacion de salud que no toca tablas— construia la
   aplicacion, y eso importaba los modelos para las siguientes.

   Cualquier prueba de integracion ejecutada sola fallaba. Se corrigio con el
   import explicito de los modelos, igual que hace `alembic/env.py`, mas una
   asercion que falla de inmediato si el metadata queda vacio.

10. **Una prueba que solo pasaba en horario de oficina.** El ciclo de un job de
    cobertura dependia del reloj real: fuera de la franja configurada, la
    politica se niega a consultar —que es lo correcto— y la asercion fallaba.
    Se abrio la ventana a 24 horas en el entorno de pruebas de integracion; el
    comportamiento horario se verifica aparte, con un reloj congelado, en
    `test_planificacion.py`.

Ambos son el mismo tipo de error: una prueba que pasa por una razon distinta de
la que se cree.

### Limpieza de calidad estatica

- **`ruff`**: sin avisos, y el formateador aplicado a los 94 archivos.
- **`mypy --strict`**: sin errores en los 82 modulos.

Las correcciones no fueron cosmeticas. Entre otras: tipar los constructores de
consultas SQL —que estaban sin anotar y ocultaban el tipo real—, declarar los
repositorios de la unidad de trabajo con el tipo del **puerto** y no el de la
implementacion —sin eso la clase no satisfacia el protocolo—, y corregir una
anotacion `callable[[], AvanzarJob]` en minuscula que no era un tipo valido.

Las excepciones que quedan configuradas en `pyproject.toml` llevan su
justificacion escrita al lado. Son cuatro, y ninguna oculta un problema real.

## Lo que falta

- [ ] **Pruebas de componentes en Angular.** La arquitectura las hace faciles
      —los componentes dependen de puertos— pero no se han escrito.
- [ ] **Pipeline de integracion continua.** Hoy las pruebas se corren a mano.
      Deberia ejecutar `ruff`, `mypy`, `pytest` y `ng build` en cada cambio.
- [ ] **Cobertura medida.** Esta configurada (`pytest-cov`) pero sin umbral.
- [ ] **Pruebas de carga** del planificador con un padron grande.
- [ ] **Revision de seguridad independiente** antes de produccion.

## Como continuar

```bash
make test        # backend
make lint        # ruff + mypy
make test-front  # angular (pendiente de escribir pruebas)
```

Para las pruebas de integracion:

```bash
docker run -d --name ute_pg_test -e POSTGRES_USER=ute \
  -e POSTGRES_PASSWORD=ute -e POSTGRES_DB=ute_vice \
  -p 55432:5432 postgres:18-alpine
```
