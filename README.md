# Papeleta de Feriado Legal (Chile)

Módulo Odoo 18 que agrega, a la solicitud de tiempo personal, un botón que
descarga el **Comprobante de Feriado Legal** en PDF con todos los datos ya
completos.

Está pensado para el flujo en que **la firma se toma presencial**: el documento
sale entero de un click, con las dos líneas de firma en blanco. No usa el módulo
de firma digital, no envía nada por correo y no espera a nadie.

| | |
|---|---|
| Módulo | `sd_hr_papeleta_feriado` |
| Versión | `18.0.1.0.0` |
| Depende de | `hr_holidays` |
| Licencia | LGPL-3 |

---

## Cómo se usa

1. Abrir una solicitud de tiempo personal **ya aprobada**
   (*Tiempo personal → Todo el tiempo personal*).
2. Apretar **Papeleta de vacaciones** en la barra de arriba.

El comprobante también queda en el menú **Imprimir**, que además permite emitir
varias de una: seleccionar filas en la lista e imprimir saca una hoja por
solicitud.

El botón aparece sólo cuando la solicitud está en estado `validate` (aprobada).
Emitir el comprobante de un feriado que todavía se puede rechazar sería prometer
un feriado que no existe. Para relajarlo, `ESTADOS_IMPRIMIBLES` en
[`models/hr_leave.py`](sd_hr_papeleta_feriado/models/hr_leave.py).

---

## De dónde sale cada dato

| Campo del comprobante | Origen |
|---|---|
| Empresa, R.U.T., dirección | `employee_id.company_id` (`name`, `vat`, `street`, `street2`, `city`) |
| Giro | `company_id.partner_id.l10n_cl_activity_description` |
| Fecha de emisión | El día de hoy, en la zona horaria de quien imprime |
| N° … / año | El **ID de la solicitud**, y el año de la fecha de inicio del feriado |
| Nombre del trabajador | `employee_id.name` |
| RUT | `employee_id.identification_id` |
| Cargo | `employee_id.job_title`, y si está vacío el nombre del puesto |
| Fecha de inicio / término | `request_date_from` / `request_date_to` |
| Días hábiles | `number_of_days` — los días que Odoo imputó a la solicitud |
| Días inhábiles | Días corridos del período **menos** los hábiles |
| Días progresivos | `employee_id.l10n_cl_progressive_vacation_days` |
| Días disponibles | Asignaciones validadas menos ausencias validadas del mismo tipo, sin contar esta |
| Período de vacaciones | Fechas de las asignaciones validadas de ese tipo |
| Observaciones | `notes`, y si está vacío la descripción de la solicitud |

Tres de estos merecen una explicación, porque son decisiones y no lecturas.

### Los días inhábiles se derivan, no se cuentan aparte

`inhábiles = días corridos − días hábiles`. Así la cuenta **cierra siempre**:
lo que dice el papel suma exactamente el período que se pidió. Contarlos por
separado —fines de semana más feriados— parece más directo, pero puede discrepar
de los días que Odoo efectivamente descontó del saldo, y entonces el comprobante
contradice al ERP sin que nadie sepa cuál de los dos tiene razón.

### Los días disponibles se recalculan

Es la misma cuenta que el módulo de nómina muestra en el formulario como *Días
Disponibles en Asignación*, y da el mismo número. Se recalcula en vez de leer ese
campo por dos razones: lo aporta un módulo que no todos los clientes tienen, y
donde está sólo lo llena para el tipo llamado exactamente
`Vacaciones Legales Chile`.

Es el saldo **sin contar esta solicitud** — el mismo criterio que el formulario.

### Los campos opcionales no se dan por sentados

`l10n_cl_progressive_vacation_days` y `l10n_cl_activity_description` vienen de la
localización chilena. Si no está instalada, el campo sale vacío y el documento se
emite igual. La comprobación es en Python (`in ._fields`) y no en la plantilla:
en QWeb un campo ausente revienta el render y el usuario sólo ve *error al
imprimir*.

---

## El documento

Replica el formulario controlado **PRORRHH004** de Gestión de Personas: Carta
(612×792 pt), márgenes de 72 pt, ancho útil 468 pt, filas de 23,7 pt, barras de
sección `#333333` y rótulos `#f2f2f2`. Las medidas del CSS salen de medir el PDF
original, y por eso están en `pt` y en porcentaje de ese ancho útil.

**Es siempre de una hoja**, y su propia cabecera lo declara (*Página 1 de 1*).
Lo que sostiene esa afirmación es el recorte de las observaciones a
`LARGO_OBSERVACIONES` caracteres, no el alto del recuadro: una celda de tabla
ignora `overflow` y crece igual, empujando el documento a una segunda hoja que la
cabecera dice que no existe.

### Dos cosas que se ven raras en el código y están así a propósito

* **El pie de página lleva los estilos en línea.** Odoo saca el `div.footer` del
  documento y se lo entrega a wkhtmltopdf como un HTML aparte; el `<style>` del
  cuerpo no viaja con él. Una clase ahí se pierde en silencio.
* **Se llama a `web.html_container` y no a `web.basic_layout`.** `basic_layout`
  mete todo dentro de un único `div.article`, y el pie tiene que quedar **fuera**
  de él para que Odoo lo reconozca como pie real en vez de como un párrafo más.

---

## Instalación

```bash
odoo -d <base> -i sd_hr_papeleta_feriado --stop-after-init
```

En Odoo.sh el módulo se engancha como **submódulo** del repositorio de addons de
la instancia, y el despliegue es mover el puntero del submódulo — no copiar
archivos:

```bash
git submodule add git@github.com:simpledigitalCL/Papeleta_vacaciones-CL.git simpledigitalCL/Papeleta_vacaciones-CL
```

Después, instalar el módulo desde *Aplicaciones* en el build.

> **La versión importa.** Odoo antepone la serie a lo que no empiece con ella, así
> que un `1.0.0` suelto queda como `18.0.1.0.0` pero un `19.0.x` en una 18 ordena
> mal para siempre. La convención acá es `18.0.x.y.z`, igual que el resto de los
> módulos de la instancia. Y al cambiar el módulo hay que **subir la versión** o
> Odoo.sh despliega el código nuevo sin actualizar nada, y parece que el arreglo
> no funcionó.

---

## Estructura

```
sd_hr_papeleta_feriado/
├── __manifest__.py
├── models/
│   └── hr_leave.py                        # armado y formato de los datos
├── report/
│   ├── hr_leave_papeleta.py               # parser del reporte
│   ├── hr_leave_papeleta_paperformat.xml  # Carta con los márgenes del modelo
│   ├── hr_leave_papeleta_report.xml       # ir.actions.report
│   └── hr_leave_papeleta_templates.xml    # QWeb
└── views/
    └── hr_leave_views.xml                 # el botón en la cabecera
```

Todo el armado del documento vive en `models/hr_leave.py` y la plantilla se
limita a pintar un diccionario de cadenas ya formateadas. Los formatos son
chilenos y **fijos** —RUT con puntos, fechas `dd/mm/aaaa`, coma decimal— y no los
del idioma de quien imprime: un comprobante que cambia de formato según el
usuario que aprieta el botón no es un documento controlado.
