import sys
from datetime import date, timedelta

from app import config
from app.infrastructure.db.database import Base, SessionLocal, engine
from app.infrastructure.db.models import (
    DocenteORM,
    EvaluacionORM,
    FacultadORM,
    MateriaORM,
    UsuarioORM,
    VotoUtilORM,
)

FACULTAD = "Facultad de Ingenierías"

MATERIAS = [
    "Taller de Programación",
    "Bases de Datos",
    "Estructuras de Datos",
    "Análisis y Diseño de Software",
    "Cálculo Integral",
    "Probabilidad y Estadística",
    "Infraestructura de Redes",
]

DOCENTES = {
    "Andrea Rincón Torres": ["Taller de Programación", "Estructuras de Datos"],
    "Julián Castaño Mejía": ["Bases de Datos"],
    "Paola Herrera Quintero": ["Análisis y Diseño de Software", "Taller de Programación"],
    "Ricardo Salamanca Peña": ["Cálculo Integral"],
    "Marcela Ospina Vargas": ["Probabilidad y Estadística", "Cálculo Integral"],
    "Felipe Arango Duarte": ["Infraestructura de Redes"],
    "Natalia Beltrán Cruz": ["Estructuras de Datos", "Bases de Datos"],
    "Germán Pulido Rojas": ["Análisis y Diseño de Software"],
}

EJEMPLOS = [
    ("Andrea Rincón Torres", "Taller de Programación", 5,
     "Explica con ejemplos reales y siempre responde dudas por el chat.", 4),
    ("Andrea Rincón Torres", "Estructuras de Datos", 4,
     "Buena clase, aunque los talleres son bastante largos.", 1),
    ("Andrea Rincón Torres", "Taller de Programación", 4,
     "Organiza muy bien el curso desde la primera semana y cumple las fechas.", 2),
    ("Andrea Rincón Torres", "Estructuras de Datos", 3,
     "Los parciales son difíciles, conviene practicar con los ejercicios del aula virtual.", 6),
    ("Andrea Rincón Torres", "Taller de Programación", None,
     "Recomiendo ir a las asesorías de los jueves, ayudan mucho con el proyecto final.", 3),
    ("Andrea Rincón Torres", "Estructuras de Datos", 5, None, 0),
    ("Julián Castaño Mejía", "Bases de Datos", 3,
     "Sabe mucho del tema pero va muy rápido en las clases.", 2),
    ("Ricardo Salamanca Peña", "Cálculo Integral", 2,
     "Califica muy tarde y casi no deja ejercicios resueltos.", 5),
    ("Marcela Ospina Vargas", "Probabilidad y Estadística", 5, None, 0),
    ("Paola Herrera Quintero", "Análisis y Diseño de Software", None,
     "Los diagramas UML quedan muy claros con sus explicaciones.", 1),
]
VOTANTES = 6


def obtener_o_crear(db, modelo, **filtros):
    fila = db.query(modelo).filter_by(**filtros).first()
    if fila is None:
        fila = modelo(**filtros)
        db.add(fila)
        db.flush()
    return fila


def cargar(db, con_ejemplos=False):
    facultad = obtener_o_crear(db, FacultadORM, nombre=FACULTAD)

    materias = {
        nombre: obtener_o_crear(db, MateriaORM, nombre=nombre, id_facultad=facultad.id_facultad)
        for nombre in MATERIAS
    }

    docentes = {}
    for nombre, dicta in DOCENTES.items():
        docente = obtener_o_crear(db, DocenteORM, nombre=nombre)
        for materia in dicta:
            if materias[materia] not in docente.materias:
                docente.materias.append(materias[materia])
        docentes[nombre] = docente

    admin = obtener_o_crear(db, UsuarioORM, correo_institucional=config.ADMIN_CORREO.lower())
    admin.rol = "admin"

    if con_ejemplos:
        dominio = config.DOMINIOS_CORREO[0]
        votantes = [obtener_o_crear(db, UsuarioORM, correo_institucional=f"votante{v}.demo@{dominio}")
                    for v in range(1, VOTANTES + 1)]
        for i, (docente, materia, puntaje, comentario, votos) in enumerate(EJEMPLOS, start=1):
            estudiante = obtener_o_crear(db, UsuarioORM,
                                         correo_institucional=f"estudiante{i}.demo@{dominio}")
            evaluacion = db.query(EvaluacionORM).filter_by(
                id_usuario=estudiante.id_usuario, id_docente=docentes[docente].id_docente,
                id_materia=materias[materia].id_materia,
            ).first()
            if evaluacion is None:
                evaluacion = EvaluacionORM(id_usuario=estudiante.id_usuario,
                                           id_docente=docentes[docente].id_docente,
                                           id_materia=materias[materia].id_materia,
                                           puntaje=puntaje, comentario=comentario,
                                           fecha=date.today() - timedelta(days=3 * i))
                db.add(evaluacion)
                db.flush()
                for votante in votantes[:votos]:
                    db.add(VotoUtilORM(id_usuario=votante.id_usuario,
                                       id_evaluacion=evaluacion.id_evaluacion))
    db.commit()
    return {"materias": len(materias), "docentes": len(docentes)}


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    sesion = SessionLocal()
    try:
        resultado = cargar(sesion, con_ejemplos="--ejemplos" in sys.argv)
    finally:
        sesion.close()
    print(f"Listo: 1 facultad, {resultado['materias']} materias, {resultado['docentes']} docentes.")
    print(f"Administrador: {config.ADMIN_CORREO}")
