# -*- coding: utf-8 -*-
"""De un talonario compartido a uno por empresa.

`18.0.1.1.0` instalaba UNA secuencia con la compania vacia, igual que la de
pedidos de venta. Desde `18.0.1.2.0` hay una por empresa, porque la papeleta la
emite el empleador y dos empleadores no comparten talonario.

El codigo va escrito a mano y no importado del modulo a proposito: un script de
migracion describe el estado del mundo en el momento en que se escribio, y tiene
que seguir corriendo igual aunque manana la constante cambie de valor.
"""
from odoo import SUPERUSER_ID, api

CODIGO_FOLIO = "sd.hr.papeleta.feriado"
XMLID_COMPARTIDA = "sd_hr_papeleta_feriado.seq_papeleta_feriado"


def migrate(cr, version):
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    compartida = env["ir.sequence"].search([
        ("code", "=", CODIGO_FOLIO),
        ("company_id", "=", False),
    ], limit=1)

    # Todas las empresas arrancan donde iba el talonario compartido, y no en 1.
    # Bajo el talonario viejo cualquiera de ellas pudo haberse llevado un folio,
    # asi que reiniciar en 1 haria que la primera papeleta de una empresa
    # repitiera un numero ya impreso en otra.
    arranque = compartida.number_next_actual if compartida else 1
    for compania in env["res.company"].search([]):
        secuencia = compania._papeleta_secuencia()
        if secuencia.number_next_actual < arranque:
            secuencia.number_next_actual = arranque

    if compartida:
        # El registro venia con `noupdate`, y `_process_end` NO borra los
        # huerfanos marcados asi: si no se saca a mano, la secuencia compartida
        # sobrevive a la actualizacion y aparece en el menu como un talonario
        # sin empresa que ya no numera nada.
        env["ir.model.data"].search([
            ("module", "=", XMLID_COMPARTIDA.split(".")[0]),
            ("name", "=", XMLID_COMPARTIDA.split(".")[1]),
        ]).unlink()
        compartida.unlink()
