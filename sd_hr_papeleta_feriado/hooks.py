# -*- coding: utf-8 -*-
"""Lo que hay que dejar listo al instalar.

Las empresas de la base ya existen cuando el modulo llega, asi que ninguna
tiene talonario todavia. Se crean aca y no en un archivo de datos porque un
registro de datos solo sabe de las companias que existian cuando se escribio, y
este modulo esta pensado para instalarse en bases ajenas.
"""


def post_init_hook(env):
    env["res.company"].sudo().search([])._papeleta_asegurar_secuencias()
