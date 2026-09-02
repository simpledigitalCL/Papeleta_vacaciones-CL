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

#: Codigo de la `ir.sequence` que lleva el correlativo de folios. El talonario
#: se define en Tiempo personal -> Configuracion -> Folio de la papeleta, y el
#: modulo lo instala arrancando en 1: la empresa que ya venia numerando a mano
#: pone ahi el numero que sigue.
CODIGO_FOLIO = "sd.hr.papeleta.feriado"

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

#: Lo que entra en el renglon del periodo sin pasar de dos lineas. El
#: `display_name` lo arma Odoo con el nombre del trabajador adentro, asi que un
#: nombre largo puede estirarlo; el tope evita que un caso raro empuje la hoja.
LARGO_PERIODO = 140


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

    papeleta_folio = fields.Char(
        string="Folio de la papeleta",
        copy=False,
        readonly=True,
        index="btree_not_null",
        help="Numero del comprobante en el talonario. Se toma del correlativo "
             "la primera vez que se imprime la papeleta y despues no cambia: "
             "una reimpresion sale con el mismo numero que el papel que el "
             "trabajador ya firmo.",
    )

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
        # Se toma aca ademas de en el armado de los datos para que un
        # talonario sin configurar se avise en pantalla, antes de la descarga, y
        # no como un "error al imprimir" ya dentro del PDF.
        imprimibles._papeleta_asignar_folio()
        reporte = self.env.ref("sd_hr_papeleta_feriado.action_report_papeleta_feriado")
        return reporte.report_action(imprimibles)

    # ------------------------------------------------------------------
    # El folio
    # ------------------------------------------------------------------
    def _papeleta_compania(self):
        """La compania del documento: la que EMPLEA, no la de quien imprime.

        La papeleta la emite el empleador, asi que tanto los datos del membrete
        como el talonario del que sale el folio se resuelven por la compania del
        empleado. En un grupo con dos empresas, imprimir desde una no puede
        emitir el comprobante de la otra.
        """
        self.ensure_one()
        return self.employee_id.company_id or self.company_id or self.env.company

    def _papeleta_asignar_folio(self):
        """Toma el siguiente folio del correlativo, UNA sola vez por solicitud.

        Se llama desde el boton y tambien desde el armado de los datos, porque
        el menu Imprimir no pasa por el boton. Que sea idempotente es lo que
        sostiene las dos cosas: numerar una vez sola, y que reimprimir devuelva
        el mismo numero.

        El folio se gasta al EMITIR, no al aprobar. Un feriado aprobado que
        nadie imprimio no es una papeleta, y numerarlo dejaria en el talonario
        folios que no existen en ningun papel.
        """
        secuencia = self.env["ir.sequence"].sudo()
        # Con `sudo`: quien aprueba un feriado —el jefe directo, por ejemplo— no
        # siempre puede escribir la solicitud ya aprobada, y el folio no es un
        # dato suyo sino del documento. El motor de reportes ya exigio permiso
        # de lectura sobre la solicitud antes de llegar aca.
        for solicitud in self.sudo():
            if solicitud.papeleta_folio:
                continue
            folio = secuencia.with_company(
                solicitud._papeleta_compania()
            ).next_by_code(CODIGO_FOLIO)
            if not folio:
                raise UserError(_(
                    "No hay un correlativo de folios para la papeleta. "
                    "Se configura en Tiempo personal / Configuracion / "
                    "Folio de la papeleta."
                ))
            solicitud.papeleta_folio = folio

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
        """El periodo, tal como Odoo nombra la solicitud.

        Es el `display_name` completo —trabajador, tipo de ausencia, duracion y
        rango— y no solo las fechas: asi el recuadro dice lo MISMO que la ficha
        en pantalla, palabra por palabra, y no hay dos redacciones del mismo
        periodo que puedan divergir.
        """
        self.ensure_one()
        return recortar(self.display_name, LARGO_PERIODO)

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
        solicitud._papeleta_asignar_folio()
        empleado = solicitud.employee_id
        compania = solicitud._papeleta_compania()
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
            "folio": solicitud.papeleta_folio or "",
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
            # La nota de la solicitud (`name`), que es lo que se escribe en el
            # formulario. `notes` existe pero en esta base esta siempre vacio.
            "observaciones": recortar(texto_util(solicitud.name)),
        }
