-- init-db.sql
-- Ejecutado automáticamente por postgres al crear el contenedor por primera vez.
-- Solo se corre si el volumen postgres_data está vacío.

-- Extensiones requeridas
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Base de datos de tests (para pytest)
SELECT 'CREATE DATABASE slate_test OWNER slate'
  WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'slate_test')\gexec

\c slate_test
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
