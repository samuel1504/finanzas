# Mis Finanzas

App personal (un solo `index.html`, sin dependencias) + conector de Gmail (`apps-script/Code.gs`).

## Qué hace sola

- **Cierre de mes automático**: al abrir la app en un mes nuevo archiva el anterior y abre el siguiente con su plan (Nov 2026: 200k Trii → 500 Acciones US, 150k Bancolombia → Fidurenta, 100k FE; Dic 2026: parqueadero en $0).
- **Conector de Gmail** (cada hora, en tu cuenta de Google): detecta depósitos y compras de Trii, CDT de Nu y transferencias de Bancolombia. La app marca sola el aporte a Trii cuando entra el depósito y los ingresos cuando llega un pago de igual monto.
- **Respaldo y sincronización**: la app sube su estado (sin la URL ni el token) al Drive del conector y lo recupera en otro dispositivo.
- **Resumen semanal por correo** (domingos 6 pm) con movimientos y aviso si los saldos tienen más de 14 días.

## Lo que no se puede automatizar

Los saldos de Trii, Bancolombia y Nu llegan solo en PDFs protegidos con contraseña, no en el cuerpo de los correos. Por eso existe el **Snapshot rápido**: 3 números (Trii, Bancolombia, FE) cada 1–2 semanas. Entre snapshots la app suma los aportes y marca los valores como estimados.

## Instalar el conector (una vez, ~3 minutos)

1. Abre <https://script.google.com> → *Nuevo proyecto* → pega el contenido de `apps-script/Code.gs`.
2. Ejecuta la función `setup` y acepta los permisos (Gmail, Drive, correo). Al terminar, el registro de ejecución muestra el `TOKEN`.
3. *Implementar* → *Nueva implementación* → tipo *Aplicación web* → ejecutar como **tú**, acceso **Cualquier usuario** → copia la URL que termina en `/exec`.
4. En la app: *Inversiones → Conector* → pega la URL y el token.

## Pruebas

`node apps-script/parsers.test.js` valida los parsers contra el texto real de los correos.
