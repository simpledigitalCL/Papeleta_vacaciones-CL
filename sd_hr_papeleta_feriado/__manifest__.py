# -*- coding: utf-8 -*-
{
    "name": "Papeleta de Feriado Legal (Chile)",
    "version": "18.0.1.3.0",
    "category": "Human Resources",
    "summary": "Comprobante de feriado legal en PDF, con los datos ya completos, "
               "descargable desde la solicitud de tiempo personal",
    "description": """
        Papeleta de Feriado Legal (Chile)
        =================================

        Agrega a la solicitud de tiempo personal (`hr.leave`) un boton
        **Papeleta de vacaciones** que descarga el Comprobante de Feriado Legal
        en PDF, con todos los datos tomados de Odoo: empresa, trabajador,
        fechas, dias habiles / inhabiles / progresivos / disponibles y periodo
        de vacaciones.

        Pensado para el flujo en que la firma se toma **presencial**: el
        documento sale completo y en un click, con las dos lineas de firma en
        blanco. No usa el modulo de firma digital ni envia nada por correo.

        Que agrega
        ----------
        * Reporte QWeb `Comprobante de Feriado Legal` sobre `hr.leave`, en
          formato Carta, replicando el formulario controlado de Gestion de
          Personas.
        * Boton en la cabecera del formulario de tiempo personal, visible
          cuando la solicitud esta aprobada.
        * Folio correlativo propio, como el de un pedido de venta: el numero se
          toma del talonario la primera vez que se imprime la papeleta y queda
          guardado en la solicitud, asi que reimprimirla no gasta otro.
        * Un talonario POR EMPRESA, creado solo al instalar y al dar de alta una
          compania nueva. La papeleta la emite el empleador, y dos empleadores
          no comparten correlativo. El numero de arranque de cada uno se define
          en Tiempo personal / Configuracion / Folio de la papeleta.
        * Entrada en el menu Imprimir, que tambien permite emitir varias
          papeletas de una (una hoja por solicitud).

        De donde sale cada dato
        -----------------------
        * Empresa, RUT, direccion y giro: la compania del empleado.
        * Trabajador, RUT y cargo: la ficha del empleado.
        * Dias habiles: los dias imputados a la solicitud (`number_of_days`).
        * Dias inhabiles: dias corridos del periodo menos los habiles.
        * Dias disponibles: asignaciones validadas menos ausencias validadas
          del mismo tipo, ESTA SOLICITUD INCLUIDA: el saldo que le queda al
          trabajador despues del feriado que ampara la papeleta.
        * Dias progresivos: `l10n_cl_progressive_vacation_days` del empleado,
          si la localizacion chilena de RRHH esta instalada.
        * Periodo de vacaciones: el `display_name` de la solicitud.
        * Folio: el correlativo `sd.hr.papeleta.feriado` de la empresa del
          empleado, guardado en la solicitud al emitirla.

        Nada del documento esta escrito a mano: el membrete —razon social, RUT,
        direccion y giro— sale de la compania del empleado, asi que el modulo
        sirve tal cual en cualquier cliente.
        * Observaciones: la nota de la solicitud (`name`).
    """,
    "author": "SimpleDigital.cl",
    "website": "https://simpledigital.cl",
    "license": "LGPL-3",
    "depends": [
        "hr_holidays",
    ],
    "data": [
        "report/hr_leave_papeleta_paperformat.xml",
        "report/hr_leave_papeleta_templates.xml",
        "report/hr_leave_papeleta_report.xml",
        "views/hr_leave_views.xml",
        "views/ir_sequence_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
    "auto_install": False,
}
