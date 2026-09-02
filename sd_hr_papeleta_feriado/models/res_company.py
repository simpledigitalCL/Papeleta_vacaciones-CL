# -*- coding: utf-8 -*-
"""El talonario de folios de cada empresa.

La papeleta la emite el EMPLEADOR, asi que en una base con varias empresas cada
una lleva su propio correlativo: dos empleadores distintos no comparten un
talonario, igual que no comparten un libro de remuneraciones.
"""
from odoo import api, models

from .hr_leave import CODIGO_FOLIO


class ResCompany(models.Model):
    _inherit = "res.company"

    @api.model_create_multi
    def create(self, vals_list):
        companias = super().create(vals_list)
        # La empresa estrena talonario en el acto y no cuando alguien imprime:
        # el numero de arranque se fija ANTES de la primera papeleta, y para
        # poder fijarlo la fila tiene que existir en el menu de configuracion.
        companias._papeleta_asegurar_secuencias()
        return companias

    def _papeleta_secuencia(self):
        """El talonario de esta empresa, creandolo si todavia no existe.

        Busca y crea en vez de depender de un registro de datos porque las
        empresas no se conocen a la hora de instalar: nacen despues, o ya
        estaban ahi antes. Que sea idempotente permite llamarlo desde el hook de
        instalacion, desde `create` y desde la emision misma, sin coordinar.

        Va con `sudo`: escribir `ir.sequence` esta reservado a Ajustes, y quien
        imprime una papeleta no tiene por que serlo.
        """
        self.ensure_one()
        Secuencia = self.env["ir.sequence"].sudo()
        existente = Secuencia.search([
            ("code", "=", CODIGO_FOLIO),
            ("company_id", "=", self.id),
        ], limit=1)
        if existente:
            return existente
        return Secuencia.create({
            "name": "Folio de la papeleta de feriado",
            "code": CODIGO_FOLIO,
            # `no_gap` y no `standard`: el correlativo de un documento laboral
            # no puede tener huecos. Con `standard` el numero sale de una
            # secuencia de Postgres, que NO se deshace si la impresion falla.
            "implementation": "no_gap",
            "padding": 1,
            "number_increment": 1,
            "number_next": 1,
            "use_date_range": False,
            "company_id": self.id,
        })

    def _papeleta_asegurar_secuencias(self):
        """Que ninguna empresa de `self` quede sin talonario."""
        for compania in self:
            compania._papeleta_secuencia()
