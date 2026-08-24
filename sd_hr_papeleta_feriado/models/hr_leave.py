# -*- coding: utf-8 -*-
"""Datos de la papeleta de feriado legal.

Todo el armado vive aca y no en el QWeb a proposito: la plantilla se limita a
pintar un diccionario de cadenas ya formateadas. Dos razones concretas.

1. Varios de los campos son OPCIONALES segun que modulos tenga instalados el
   cliente (`l10n_cl_progressive_vacation_days` viene de la localizacion chilena
   de RRHH). En Python se pregunta por `_fields` y se decide; en QWeb un campo
   ausente revienta el render y el usuario solo ve "error al imprimir".

2. Los formatos son chilenos y fijos —RUT con puntos, fechas dd/mm/aaaa, coma
   decimal— y no los del idioma de quien imprime. Un comprobante que cambia de
   formato segun el usuario que apreta el boton no es un documento controlado.
"""
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError

#: Estados en los que la papeleta tiene sentido: el feriado ya fue concedido.
#: Emitir un comprobante de algo que todavia se puede rechazar es prometer un
#: feriado que no existe.
ESTADOS_IMPRIMIBLES = ("validate",)

#: Un texto que solo tiene puntuacion es un relleno que alguien escribio para
#: poder guardar el formulario (".-" es el que aparece en la base de Bokato), no
#: una observacion. Imprimirlo ensucia el documento.
_SOLO_RELLENO = ".,-–—_/*· \t\r\n"

#: Lo que entra en el recuadro de observaciones sin desbordarlo: son ~74
#: caracteres por linea a 9 pt en 318 pt de ancho, por tres lineas.
#:
#: El recorte va ACA y no en el CSS porque `overflow: hidden` sobre una celda de
#: tabla no lo respeta ningun motor de render: la celda crece igual y empuja el
#: documento a una segunda hoja que la propia cabecera declara que no existe
#: («Pagina 1 de 1»). Un limite en el dato es la unica forma de sostener esa
#: afirmacion.
LARGO_OBSERVACIONES = 220


def formatear_rut(valor):
    """RUT chileno con puntos y guion, venga con o sin ellos.

    La compania lo guarda pelado (`79635670-7`) y el empleado con puntos
    (`17.185.610-8`): los dos tienen que salir igual en el papel.
    """
    limpio = re.sub(r"[^0-9kK]", "", valor or "")
    if len(limpio) < 2:
        return (valor or "").strip()
    cuerpo, digito = limpio[:-1], limpio[-1].upper()
    grupos = []
    while len(cuerpo) > 3:
        grupos.insert(0, cuerpo[-3:])
        cuerpo = cuerpo[:-3]
    grupos.insert(0, cuerpo)
    return "%s-%s" % (".".join(grupos), digito)


def formatear_dias(valor):
    """Cantidad de dias en formato chileno: `4`, `10,25`, `0,5`.

    Se recortan los ceros de la derecha porque `4,00 dias habiles` en un
    formulario que se llena a mano se lee como un decimal que sobro.
    """
    if valor is None:
        return ""
    numero = round(float(valor), 2)
    if abs(numero - round(numero)) < 0.005:
        return "%d" % int(round(numero))
    return ("%.2f" % numero).rstrip("0").rstrip(".").replace(".", ",")


def formatear_fecha(valor):
    """dd/mm/aaaa — el mismo formato con el que Odoo ya nombra la solicitud."""
    return valor.strftime("%d/%m/%Y") if valor else ""


def texto_util(valor):
    """El texto, o vacio si es solo puntuacion de relleno."""
    limpio = (valor or "").strip()
    return "" if not limpio.strip(_SOLO_RELLENO) else limpio


def recortar(valor, largo=LARGO_OBSERVACIONES):
    """El texto acotado al recuadro, cortando en la ultima palabra que entra."""
    limpio = " ".join((valor or "").split())
    if len(limpio) <= largo:
        return limpio
    corte = limpio[:largo].rsplit(" ", 1)[0].rstrip(_SOLO_RELLENO)
    return "%s…" % (corte or limpio[:largo])


class HrLeave(models.Model):
    _inherit = "hr.leave"

    puede_imprimir_papeleta = fields.Boolean(
        string="Papeleta disponible",
        compute="_compute_puede_imprimir_papeleta",
        help="Tecnico: gobierna la visibilidad del boton de la papeleta.",
    )

    @api.depends("state")
    def _compute_puede_imprimir_papeleta(self):
        for solicitud in self:
            solicitud.puede_imprimir_papeleta = solicitud.state in ESTADOS_IMPRIMIBLES

    # ------------------------------------------------------------------
    # Accion del boton
    # ------------------------------------------------------------------
    def action_imprimir_papeleta(self):
        """Descarga el comprobante de las solicitudes seleccionadas."""
        imprimibles = self.filtered(lambda s: s.state in ESTADOS_IMPRIMIBLES)
        if not imprimibles:
            raise UserError(_(
                "La papeleta se emite sobre un feriado ya aprobado. "
                "Esta solicitud todavia no lo esta."
            ))
        reporte = self.env.ref("sd_hr_papeleta_feriado.action_report_papeleta_feriado")
        return reporte.report_action(imprimibles)

    # ------------------------------------------------------------------
    # Los datos del documento
    # ------------------------------------------------------------------
    def _papeleta_asignaciones(self):
        """Las asignaciones validadas que alimentan este tipo de ausencia."""
        self.ensure_one()
        if not (self.employee_id and self.holiday_status_id):
            return self.env["hr.leave.allocation"]
        return self.env["hr.leave.allocation"].search([
            ("employee_id", "=", self.employee_id.id),
            ("holiday_status_id", "=", self.holiday_status_id.id),
            ("state", "=", "validate"),
        ], order="date_from asc")

    def _papeleta_dias_disponibles(self):
        """Saldo del tipo de ausencia SIN contar esta solicitud.

        Es a proposito la misma cuenta que muestra el formulario en «Dias
        Disponibles en Asignacion»: si el papel y la pantalla no dicen el mismo
        numero, el papel pierde.

        Se recalcula aca en vez de leer ese campo porque lo aporta el modulo de
        nomina, que no todos los clientes tienen — y donde esta, solo lo llena
        para el tipo llamado exactamente «Vacaciones Legales Chile».
        """
        self.ensure_one()
        asignaciones = self._papeleta_asignaciones()
        if not asignaciones:
            return 0.0
        tomadas = self.env["hr.leave"].search([
            ("employee_id", "=", self.employee_id.id),
            ("holiday_status_id", "=", self.holiday_status_id.id),
            ("state", "=", "validate"),
            ("id", "!=", self.id),
        ])
        return sum(asignaciones.mapped("number_of_days")) - sum(tomadas.mapped("number_of_days"))

    def _papeleta_periodo(self):
        """El periodo al que se imputa el feriado, segun las asignaciones.

        Una asignacion sin fecha de termino es una vigencia abierta, no un
        error: en ese caso se dice desde cuando corre y no se inventa un cierre.
        """
        self.ensure_one()
        asignaciones = self._papeleta_asignaciones()
        desde = [a.date_from for a in asignaciones if a.date_from]
        if not desde:
            return ""
        hasta = [a.date_to for a in asignaciones]
        if hasta and all(hasta):
            return "%s al %s" % (formatear_fecha(min(desde)), formatear_fecha(max(hasta)))
        return _("Desde el %s") % formatear_fecha(min(desde))

    def _papeleta_dias_progresivos(self):
        """Dias progresivos del art. 68, si la localizacion chilena los lleva."""
        self.ensure_one()
        empleado = self.employee_id
        if empleado and "l10n_cl_progressive_vacation_days" in empleado._fields:
            return empleado.l10n_cl_progressive_vacation_days or 0.0
        return 0.0

    def _papeleta_direccion(self, compania):
        """La direccion de la compania en una linea, tal como esta cargada."""
        calle = ", ".join(p for p in (compania.street, compania.street2) if p)
        ciudad = compania.city or ""
        if calle and ciudad:
            return "%s — %s" % (calle, ciudad)
        return calle or ciudad

    def _papeleta_datos(self):
        """Todo el documento, ya formateado, listo para que el QWeb lo pinte.

        Se lee con `sudo()`: el RUT del empleado (`identification_id`) esta
        reservado a `hr.group_hr_user`, y quien aprueba un feriado no siempre lo
        tiene —el jefe directo, por ejemplo—. Sin esto el boton le contesta un
        AccessError en vez del PDF. No abre nada: el motor de reportes ya exigio
        permiso de lectura sobre la solicitud antes de llegar aca, y de ahi no se
        sale: todo lo que se lee cuelga de este mismo registro.
        """
        self.ensure_one()
        solicitud = self.sudo()
        empleado = solicitud.employee_id
        compania = empleado.company_id or solicitud.company_id or self.env.company
        socio = compania.partner_id

        inicio = solicitud.request_date_from
        termino = solicitud.request_date_to or inicio
        corridos = (termino - inicio).days + 1 if (inicio and termino) else 0
        habiles = solicitud.number_of_days or 0.0
        # Los inhabiles se derivan en vez de contarse aparte para que la cuenta
        # cierre siempre: habiles + inhabiles = dias corridos del periodo. Un
        # conteo independiente puede discrepar del que ya se imputo al saldo.
        inhabiles = max(corridos - habiles, 0.0)

        giro = ""
        if socio and "l10n_cl_activity_description" in socio._fields:
            giro = socio.l10n_cl_activity_description or ""

        # La fecha se toma del usuario que imprime, no del superusuario: si el
        # documento se emite un lunes a las 8 en Santiago, dice ese lunes.
        hoy = fields.Date.context_today(self)

        return {
            "empresa": compania.name or "",
            "empresa_rut": formatear_rut(compania.vat),
            "empresa_direccion": solicitud._papeleta_direccion(compania),
            "empresa_giro": giro,
            "emision": formatear_fecha(hoy),
            "pagina": _("1 de 1"),
            "folio": str(solicitud.id),
            # El anio identifica el feriado, no la impresion: una papeleta
            # reemitida en enero sigue perteneciendo al feriado que ampara.
            "anio": (inicio or hoy).strftime("%Y"),
            "trabajador": empleado.name or "",
            "trabajador_rut": formatear_rut(empleado.identification_id),
            "trabajador_cargo": empleado.job_title or (empleado.job_id.name or ""),
            "fecha_inicio": formatear_fecha(inicio),
            "fecha_termino": formatear_fecha(termino),
            "dias_habiles": formatear_dias(habiles),
            "dias_inhabiles": formatear_dias(inhabiles),
            "dias_progresivos": formatear_dias(solicitud._papeleta_dias_progresivos()),
            "dias_disponibles": formatear_dias(solicitud._papeleta_dias_disponibles()),
            "periodo": solicitud._papeleta_periodo(),
            "observaciones": recortar(
                texto_util(solicitud.notes) or texto_util(solicitud.name)
            ),
        }
