-- EvalDoc - Esquema de la base de datos (PostgreSQL 16+)
-- Generado a partir de app/infrastructure/db/models.py (SQLAlchemy).
-- La aplicacion crea estas tablas sola al arrancar (Base.metadata.create_all);
-- este script sirve para documentarlas o crearlas a mano:
--     psql -U evaldoc -d evaldoc -f docs/esquema.sql

-- Tabla: docente
CREATE TABLE docente (
	id_docente SERIAL NOT NULL, 
	nombre VARCHAR(150) NOT NULL, 
	foto_perfil VARCHAR(300), 
	PRIMARY KEY (id_docente)
);

-- Tabla: facultad
CREATE TABLE facultad (
	id_facultad SERIAL NOT NULL, 
	nombre VARCHAR(150) NOT NULL, 
	PRIMARY KEY (id_facultad), 
	UNIQUE (nombre)
);

-- Tabla: usuario
CREATE TABLE usuario (
	id_usuario SERIAL NOT NULL, 
	correo_institucional VARCHAR(150) NOT NULL, 
	rol VARCHAR(20) NOT NULL, 
	fecha_registro DATE NOT NULL, 
	PRIMARY KEY (id_usuario), 
	CONSTRAINT chk_usuario_rol CHECK (rol IN ('estudiante', 'admin')), 
	UNIQUE (correo_institucional)
);

-- Tabla: codigo_otp
CREATE TABLE codigo_otp (
	id_codigo SERIAL NOT NULL, 
	id_usuario INTEGER NOT NULL, 
	codigo_hash VARCHAR(100) NOT NULL, 
	expira TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	intentos INTEGER NOT NULL, 
	usado BOOLEAN NOT NULL, 
	creado TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id_codigo), 
	FOREIGN KEY(id_usuario) REFERENCES usuario (id_usuario) ON DELETE CASCADE
);

-- Tabla: materia
CREATE TABLE materia (
	id_materia SERIAL NOT NULL, 
	nombre VARCHAR(150) NOT NULL, 
	id_facultad INTEGER NOT NULL, 
	PRIMARY KEY (id_materia), 
	FOREIGN KEY(id_facultad) REFERENCES facultad (id_facultad)
);

-- Tabla: docente_materia
CREATE TABLE docente_materia (
	id_docente INTEGER NOT NULL, 
	id_materia INTEGER NOT NULL, 
	PRIMARY KEY (id_docente, id_materia), 
	FOREIGN KEY(id_docente) REFERENCES docente (id_docente) ON DELETE CASCADE, 
	FOREIGN KEY(id_materia) REFERENCES materia (id_materia) ON DELETE CASCADE
);

-- Tabla: evaluacion
CREATE TABLE evaluacion (
	id_evaluacion SERIAL NOT NULL, 
	id_usuario INTEGER NOT NULL, 
	id_docente INTEGER NOT NULL, 
	id_materia INTEGER NOT NULL, 
	puntaje SMALLINT, 
	comentario VARCHAR(500), 
	fecha DATE NOT NULL, 
	estado VARCHAR(20) NOT NULL, 
	fecha_edicion TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id_evaluacion), 
	CONSTRAINT chk_evaluacion_puntaje CHECK (puntaje BETWEEN 1 AND 5), 
	CONSTRAINT chk_evaluacion_no_vacia CHECK (puntaje IS NOT NULL OR comentario IS NOT NULL), 
	CONSTRAINT uq_evaluacion_unica UNIQUE (id_usuario, id_docente, id_materia), 
	CONSTRAINT chk_evaluacion_estado CHECK (estado IN ('publicada', 'en_revision', 'oculta')), 
	FOREIGN KEY(id_usuario) REFERENCES usuario (id_usuario), 
	FOREIGN KEY(id_docente) REFERENCES docente (id_docente), 
	FOREIGN KEY(id_materia) REFERENCES materia (id_materia)
);

-- Tabla: reporte
CREATE TABLE reporte (
	id_reporte SERIAL NOT NULL, 
	id_evaluacion INTEGER NOT NULL, 
	id_usuario INTEGER, 
	categoria VARCHAR(30) NOT NULL, 
	origen VARCHAR(10) NOT NULL, 
	motivo VARCHAR(300) NOT NULL, 
	estado VARCHAR(20) NOT NULL, 
	fecha DATE NOT NULL, 
	resuelto_por INTEGER, 
	fecha_resolucion TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id_reporte), 
	CONSTRAINT chk_reporte_estado CHECK (estado IN ('pendiente', 'revisado', 'descartado')), 
	CONSTRAINT chk_reporte_categoria CHECK (categoria IN ('ofensivo', 'datos_personales', 'spam', 'falso', 'otro')), 
	CONSTRAINT chk_reporte_origen CHECK (origen IN ('usuario', 'ia')), 
	CONSTRAINT chk_reporte_usuario CHECK (origen = 'ia' OR id_usuario IS NOT NULL), 
	CONSTRAINT uq_reporte_unico UNIQUE (id_usuario, id_evaluacion), 
	FOREIGN KEY(id_evaluacion) REFERENCES evaluacion (id_evaluacion) ON DELETE CASCADE, 
	FOREIGN KEY(id_usuario) REFERENCES usuario (id_usuario), 
	FOREIGN KEY(resuelto_por) REFERENCES usuario (id_usuario)
);

-- Tabla: voto_util
CREATE TABLE voto_util (
	id_usuario INTEGER NOT NULL, 
	id_evaluacion INTEGER NOT NULL, 
	fecha TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id_usuario, id_evaluacion), 
	FOREIGN KEY(id_usuario) REFERENCES usuario (id_usuario) ON DELETE CASCADE, 
	FOREIGN KEY(id_evaluacion) REFERENCES evaluacion (id_evaluacion) ON DELETE CASCADE
);
