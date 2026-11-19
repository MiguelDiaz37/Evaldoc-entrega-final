class ErrorDominio(Exception):
    pass


class DatoInvalido(ErrorDominio):
    pass


class CorreoNoInstitucional(DatoInvalido):
    pass


class DocenteNoEncontrado(ErrorDominio):
    pass


class MateriaNoEncontrada(ErrorDominio):
    pass


class EvaluacionNoEncontrada(ErrorDominio):
    pass


class ReporteNoEncontrado(ErrorDominio):
    pass


class DocenteConEvaluaciones(ErrorDominio):
    pass


class EvaluacionDuplicada(ErrorDominio):
    pass


class ReporteDuplicado(ErrorDominio):
    pass


class NoAutenticado(ErrorDominio):
    pass


class SinPermiso(ErrorDominio):
    pass


class CodigoInvalido(ErrorDominio):
    pass


class DemasiadosIntentos(ErrorDominio):
    pass


class CorreoNoEnviado(ErrorDominio):
    pass


class IANoConfigurada(ErrorDominio):
    pass


class IALimiteAlcanzado(ErrorDominio):
    pass


class IATiempoAgotado(ErrorDominio):
    pass


class IAError(ErrorDominio):
    pass

