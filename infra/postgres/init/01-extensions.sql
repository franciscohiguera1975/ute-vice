-- Extensiones requeridas por el esquema de UTE-VICE.
-- Se ejecuta una sola vez, cuando el volumen de datos esta vacio.

-- Generacion de UUID v4 del lado del servidor.
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Busqueda por similitud sobre nombres y titulos (ILIKE acelerado, trigramas).
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Normalizacion de acentos para busquedas de personas ("Munoz" == "Munoz").
CREATE EXTENSION IF NOT EXISTS "unaccent";
