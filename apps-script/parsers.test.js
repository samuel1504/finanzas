const fs = require('fs'), vm = require('vm');
const code = fs.readFileSync('/home/claude/finanzas/apps-script/Code.gs','utf8');
const ctx = {}; vm.createContext(ctx); vm.runInContext(code, ctx);
const eq = (a,b,l)=>{ const ok = JSON.stringify(a)===JSON.stringify(b); console.log(ok?'OK  ':'FAIL', l, ok?'':JSON.stringify(a)+' != '+JSON.stringify(b)); if(!ok) process.exitCode=1; };

eq(ctx.parseTrii_('trii | Depósito aprobado ✅', 'Estado\n\nAprobado\n\nMonto\n\n$300,000.0\n\nTu depósito'), {tipo:'trii_deposito', monto:300000, detalle:'Depósito Trii'}, 'trii depósito');
eq(ctx.parseTrii_('trii | ¡Tu compra de PFCIBEST fue completada! 🤑', 'Número de acciones\n\n3\n\nPrecio\n\n77,860 COP\n\nComisión\n\n0 COP\n\nMonto total\n\n233,580 COP\n'), {tipo:'trii_compra', monto:233580, detalle:'PFCIBEST · 3 acc.'}, 'trii compra');
eq(ctx.parseTrii_('trii | Tu orden de compra para PFCIBEST fue colocada ✅', 'x'), null, 'trii orden colocada se ignora');
eq(ctx.parseNu_('¡Felicitaciones, Samuel! Invertiste en un CDT Nu', 'Nos emociona contarte que tus $691.167,08 estarán creciendo a una tasa de 9,50% efectiva anual por 60 días, hasta el 04 de agosto'), {tipo:'nu_cdt_apertura', monto:691167.08, detalle:'CDT 60 días al 9,50% EA'}, 'nu apertura');
eq(ctx.parseNu_('Ya tienes disponible el dinero de tu CDT Nu.', 'Recibiste en total $701.139,79.'), {tipo:'nu_cdt_vencimiento', monto:701139.79, detalle:'CDT vencido, dinero disponible'}, 'nu vencimiento');
eq(ctx.parseBancolombia_('Alertas y Notificaciones', '¡Listo! Todo salió bien con tus movimientos Bancolombia: Recibiste un pago PROVEEDOR de AGROGANADERA LA por $225000.00 en tu cuenta de Ahorros el 05/10/2026 a las 17:29.'), {tipo:'bc_ingreso', monto:225000, detalle:'AGROGANADERA LA'}, 'bc pago recibido');
eq(ctx.parseBancolombia_('Alertas y Notificaciones', 'Recibiste una transferencia por $700000 de CARLOS ECHEVERRI en tu cuenta **4226, el 30/09/2026 a las 08:53.'), {tipo:'bc_ingreso', monto:700000, detalle:'CARLOS ECHEVERRI'}, 'bc transferencia recibida');
eq(ctx.parseBancolombia_('Alertas y Notificaciones', 'SAMUEL, transferiste $207454.00 a la llave 3214804989 desde tu cuenta *4226 a SAMUEL ECHEVERRI MONTOYA el 08/10/26 a las 07:54.'), {tipo:'bc_egreso', monto:207454, detalle:'Transferencia a SAMUEL ECHEVERRI MONTOYA'}, 'bc transferencia enviada');
eq(ctx.parseBancolombia_('Alertas y Notificaciones', 'SAMUEL ECHEVERRI MONTOYA pagaste $70000.00 por codigo QR desde tu cuenta *4226 a la llave 0093399735'), {tipo:'bc_egreso', monto:70000, detalle:'Pago QR'}, 'bc QR');
