# -*- coding: utf-8 -*-
"""El parser del comprobante.

Existe para que la plantilla reciba diccionarios ya armados en vez de tener que
llamar metodos del registro: QWeb no deja tocar atributos privados
(`doc._papeleta_datos()`), y hacerlos publicos solo para el render seria abrir
API del modelo por una limitacion de la plantilla.
"""
from odoo import api, models


class ReportPapeletaFeriado(models.AbstractModel):
    _name = "report.sd_hr_papeleta_feriado.report_papeleta_feriado"
    _description = "Comprobante de Feriado Legal"

    @api.model
    def _get_report_values(self, docids, data=None):
        solicitudes = self.env["hr.leave"].browse(docids)
        return {
            "doc_ids": docids,
            "doc_model": "hr.leave",
            "docs": solicitudes,
            "papeletas": [
                dict(solicitud._papeleta_datos(), id=solicitud.id)
                for solicitud in solicitudes
            ],
        }
