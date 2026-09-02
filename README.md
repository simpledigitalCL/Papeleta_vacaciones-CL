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
| Versión | `18.0.1.2.0` |
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

## El folio

Cada papeleta sale con un **número correlativo propio**, igual que un pedido de
venta de Odoo: un talonario (`ir.sequence`, código `sd.hr.papeleta.feriado`) que
avanza de a uno.

Hay **un talonario por empresa**. La papeleta la emite el empleador, y dos
empleadores no comparten correlativo, igual que no comparten un libro de
remuneraciones. Los abre el propio módulo: uno por compañía al instalarse, y uno
más cada vez que se da de alta una compañía nueva. La solicitud de un empleado de
la empresa B toma el folio de B aunque la imprima alguien de A — la compañía se
resuelve por la del **empleado**, no por la de quien aprieta el botón.

### Poner el número de arranque

*Tiempo personal → Configuración → **Folio de la papeleta***. Sale una fila por
empresa, y el número se edita ahí mismo en la lista: columna **Siguiente
número**.

Una empresa que venía numerando a mano y va en la 30 pone ahí un `31`, y de ahí
en adelante el correlativo avanza solo. El menú pide permisos de *Ajustes*
porque escribir secuencias está reservado a ese grupo en el propio Odoo: abrirlo
al responsable de RRHH significaría darle escritura sobre **todas** las
secuencias de la base —las de facturas y pedidos incluidas—, que es mucho más de
lo que este módulo tiene derecho a repartir.

### El folio se gasta al emitir, no al aprobar

El número se toma la **primera vez que se imprime** la papeleta y queda guardado
en la solicitud (`papeleta_folio`, visible junto a la duración y como columna
opcional en la lista). Tres consecuencias buscadas:

* **Reimprimir no gasta otro folio.** El papel que el trabajador firmó y el que
  se reimprime en enero llevan el mismo número.
* **Un feriado aprobado que nadie imprimió no consume número.** Numerar al
  aprobar dejaría en el talonario folios que no existen en ningún papel.
* **El talonario no tiene huecos.** La secuencia es `no_gap` y no `standard`: el
  número viaja dentro de la transacción, así que si la impresión falla el folio
  no se gastó. `standard` toma el número de una secuencia de PostgreSQL, que no
  se deshace, y el talonario saltaría del 31 al 33. El costo de `no_gap` es un
  bloqueo por emisión, y acá las papeletas se imprimen de a una.

El nombre del archivo PDF también lleva el folio (`Papeleta Feriado - Nombre -
31.pdf`), para poder cruzar lo guardado con el talonario.

### Por qué los talonarios no vienen en un archivo de datos

Se crean desde Python —un `post_init_hook` al instalar y un `create` en
`res.company` para las que nazcan después— y no como registros de datos. Un
registro de datos sólo puede nombrar compañías que existían cuando se escribió,
y este módulo está pensado para instalarse en bases ajenas, donde no se sabe ni
cuántas empresas hay ni cómo se llaman.

`_papeleta_secuencia()` busca y crea, así que es idempotente: lo llaman el hook,
el alta de compañía y la emisión misma, sin coordinarse. Una empresa que haya
entrado por un camino que no pasa por `create` —una importación, por ejemplo—
tampoco se queda sin folios.

El folio se pide con `next_by_id()` sobre el talonario de la empresa y **no** con
`next_by_code()`: este último resuelve la compañía por la del *usuario* que
imprime, y la papeleta la numera la que **emplea**.

> **Al actualizar, ningún correlativo se reinicia.** Los talonarios no son
> registros de datos, así que una actualización no los reescribe. La migración
> `18.0.1.2.0` convierte el talonario compartido de `18.0.1.1.0` en uno por
> empresa, y **arranca a todas en el número al que iba el compartido**, no en 1:
> bajo el talonario viejo cualquiera pudo haberse llevado un folio, y reiniciar
> haría que la primera papeleta de una empresa repitiera un número ya impreso en
> otra.

---

## De dónde sale cada dato

| Campo del comprobante | Origen |
|---|---|
| Empresa, R.U.T., dirección | `employee_id.company_id` (`name`, `vat`, `street`, `street2`, `city`) |
| Giro | `company_id.partner_id.l10n_cl_activity_description` |
| Fecha de emisión | El día de hoy, en la zona horaria de quien imprime |
| N° … / año | El **folio correlativo**, y el año de la fecha de inicio del feriado |
| Nombre del trabajador | `employee_id.name` |
| RUT | `employee_id.identification_id` |
| Cargo | `employee_id.job_title`, y si está vacío el nombre del puesto |
| Fecha de inicio / término | `request_date_from` / `request_date_to` |
| Días hábiles | `number_of_days` — los días que Odoo imputó a la solicitud |
| Días inhábiles | Días corridos del período **menos** los hábiles |
| Días progresivos | `employee_id.l10n_cl_progressive_vacation_days` |
| Días disponibles | Asignaciones validadas menos ausencias validadas del mismo tipo, sin contar esta |
| Período de vacaciones | `display_name` — el nombre con que Odoo identifica la solicitud |
| Observaciones | `name` — la nota de la solicitud |

Cinco de estos merecen una explicación, porque son decisiones y no lecturas.

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

### El período repite lo que dice la ficha, a propósito

Es el `display_name` completo de la solicitud —trabajador, tipo de ausencia, duración y
rango— y no sólo las fechas. Así el recuadro dice **lo mismo que la pantalla, palabra por
palabra**, y no hay dos redacciones del mismo período que puedan divergir. Ocupa dos
renglones y el resto de la hoja lo absorbe.

### Una nota que es sólo puntuación no se imprime

`texto_util()` descarta lo que no tiene más que puntos y guiones — `.-` es lo que aparece en
varias solicitudes de la base, escrito para poder guardar el formulario. En el recuadro de
un documento controlado eso se lee como un defecto, no como una observación. Si se prefiere
imprimirlo tal cual, es sacar esa llamada en `_papeleta_datos()`.

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
Lo que sostiene esa afirmación es el recorte de los dos campos de largo libre
—`LARGO_OBSERVACIONES` y `LARGO_PERIODO`—, no el alto de los recuadros: una celda
de tabla ignora `overflow` y crece igual, empujando el documento a una segunda
hoja que la cabecera dice que no existe.

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
├── hooks.py                               # abre los talonarios al instalar
├── migrations/
│   └── 18.0.1.2.0/post-migrate.py         # del talonario compartido a uno por empresa
├── models/
│   ├── hr_leave.py                        # folio, armado y formato de los datos
│   └── res_company.py                     # el talonario de cada empresa
├── report/
│   ├── hr_leave_papeleta.py               # parser del reporte
│   ├── hr_leave_papeleta_paperformat.xml  # Carta con los márgenes del modelo
│   ├── hr_leave_papeleta_report.xml       # ir.actions.report
│   └── hr_leave_papeleta_templates.xml    # QWeb
└── views/
    ├── hr_leave_views.xml                 # el botón, el folio en la ficha y en la lista
    └── ir_sequence_views.xml              # el menú donde se fija el correlativo
```

Nada del documento está escrito a mano: el membrete —razón social, RUT, dirección
y giro— sale de la compañía del empleado, así que el módulo se instala tal cual en
cualquier cliente.

Todo el armado del documento vive en `models/hr_leave.py` y la plantilla se
limita a pintar un diccionario de cadenas ya formateadas. Los formatos son
chilenos y **fijos** —RUT con puntos, fechas `dd/mm/aaaa`, coma decimal— y no los
del idioma de quien imprime: un comprobante que cambia de formato según el
usuario que aprieta el botón no es un documento controlado.
