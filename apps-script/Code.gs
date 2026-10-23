/**
 * Conector de Finanzas (Google Apps Script).
 * Corre en TU cuenta de Google: lee tu Gmail cada hora, extrae eventos
 * (Trii, Nu, Bancolombia) y los expone a la app. También guarda una copia
 * del estado de la app (respaldo + sincronización entre dispositivos)
 * y te envía un resumen semanal por correo.
 *
 * Instalación (una sola vez): ver README.md
 */

var LOOKBACK_DAYS = 45;      // ventana de búsqueda en cada escaneo
var MAX_EVENTS = 400;        // eventos que se conservan
var TZ = 'America/Bogota';
var EVENTS_FILE = 'finanzas-events.json';
var STATE_FILE = 'finanzas-state.json';

// ───────────────────────── Instalación ─────────────────────────
function setup() {
  var p = PropertiesService.getScriptProperties();
  if (!p.getProperty('TOKEN')) p.setProperty('TOKEN', Utilities.getUuid().replace(/-/g, ''));
  ScriptApp.getProjectTriggers().forEach(function (t) { ScriptApp.deleteTrigger(t); });
  ScriptApp.newTrigger('scan').timeBased().everyHours(1).create();
  ScriptApp.newTrigger('weeklyDigest').timeBased().onWeekDay(ScriptApp.WeekDay.SUNDAY).atHour(18).create();
  scan();
  Logger.log('TOKEN (pégalo en la app, Configuración): ' + p.getProperty('TOKEN'));
}

// ───────────────────────── Escaneo de Gmail ─────────────────────────
function scan() {
  var stored = readJson_(EVENTS_FILE, { events: [] });
  var seen = {};
  stored.events.forEach(function (e) { seen[e.id] = true; });
  var fresh = [];

  var sources = [
    { q: 'from:comunicaciones@trii.co', parse: parseTrii_ },
    { q: 'from:nu@nu.com.co', parse: parseNu_ },
    { q: 'from:alertasynotificaciones@an.notificacionesbancolombia.com', parse: parseBancolombia_ }
  ];

  sources.forEach(function (src) {
    var threads = GmailApp.search(src.q + ' newer_than:' + LOOKBACK_DAYS + 'd', 0, 100);
    threads.forEach(function (th) {
      th.getMessages().forEach(function (m) {
        var id = m.getId();
        if (seen[id]) return;
        var d = m.getDate();
        var ev = null;
        try { ev = src.parse(m.getSubject(), m.getPlainBody()); } catch (err) { ev = null; }
        if (!ev) return;
        ev.id = id;
        ev.ts = d.toISOString();
        ev.fecha = Utilities.formatDate(d, TZ, 'yyyy-MM-dd');
        fresh.push(ev);
        seen[id] = true;
      });
    });
  });

  if (fresh.length) {
    var all = stored.events.concat(fresh);
    all.sort(function (a, b) { return a.ts < b.ts ? -1 : 1; });
    stored.events = all.slice(-MAX_EVENTS);
  }
  stored.scannedAt = new Date().toISOString();
  writeJson_(EVENTS_FILE, stored);
}

// Trii: depósitos y órdenes completadas
function parseTrii_(subject, body) {
  if (/Dep[oó]sito aprobado/i.test(subject)) {
    var m = body.match(/Monto\s+\$?\s*([\d.,]+)/);
    return { tipo: 'trii_deposito', monto: m ? parseUS_(m[1]) : null, detalle: 'Depósito Trii' };
  }
  var c = subject.match(/(compra|venta) de ([A-Z0-9]+) fue completada/i);
  if (c) {
    var shares = body.match(/N[uú]mero de acciones\s+(\d+)/);
    var total = body.match(/Monto total\s+([\d.,]+)\s*COP/);
    return {
      tipo: /compra/i.test(c[1]) ? 'trii_compra' : 'trii_venta',
      monto: total ? parseUS_(total[1]) : null,
      detalle: c[2] + (shares ? ' · ' + shares[1] + ' acc.' : '')
    };
  }
  return null; // otros correos de Trii se ignoran
}

// Nu: apertura y vencimiento de CDT
function parseNu_(subject, body) {
  if (/Invertiste en un CDT Nu/i.test(subject)) {
    var m = body.match(/tus \$([\d.,]+) estar[aá]n creciendo a una tasa de ([\d,]+)% efectiva anual por (\d+) d[ií]as/);
    return {
      tipo: 'nu_cdt_apertura',
      monto: m ? parseCO_(m[1]) : null,
      detalle: m ? 'CDT ' + m[3] + ' días al ' + m[2] + '% EA' : 'CDT Nu'
    };
  }
  if (/disponible el dinero de tu CDT/i.test(subject)) {
    var t = body.match(/Recibiste en total \$([\d.,]+)/);
    return { tipo: 'nu_cdt_vencimiento', monto: t ? parseCO_(t[1]) : null, detalle: 'CDT vencido, dinero disponible' };
  }
  return null;
}

// Bancolombia: transferencias/pagos recibidos y enviados
function parseBancolombia_(subject, body) {
  var text = body.replace(/\s+/g, ' ');
  var m = text.match(/Recibiste un pago .*? de (.+?) por \$([\d.,]+)/i);
  if (m) return { tipo: 'bc_ingreso', monto: parseBC_(m[2]), detalle: m[1].trim() };
  m = text.match(/Recibiste una transferencia por \$([\d.,]+) de (.+?) en tu cuenta/i);
  if (m) return { tipo: 'bc_ingreso', monto: parseBC_(m[1]), detalle: m[2].trim() };
  m = text.match(/transferiste \$([\d.,]+) a la llave \d+ .*? a (.+?) el \d/i);
  if (m) return { tipo: 'bc_egreso', monto: parseBC_(m[1]), detalle: 'Transferencia a ' + m[2].trim() };
  m = text.match(/pagaste \$([\d.,]+) por codigo QR/i);
  if (m) return { tipo: 'bc_egreso', monto: parseBC_(m[1]), detalle: 'Pago QR' };
  return null;
}

// Formatos numéricos observados en cada fuente
function parseUS_(s) { return parseFloat(String(s).replace(/,/g, '')); }                      // 233,580 · 300,000.0
function parseCO_(s) { return parseFloat(String(s).replace(/\./g, '').replace(',', '.')); }   // 691.167,08
function parseBC_(s) { return parseFloat(String(s).replace(/,/g, '')); }                      // 225000.00 · 700000

// ───────────────────────── API para la app ─────────────────────────
function doGet(e) {
  if (!authOk_(e.parameter.token)) return json_({ error: 'token' });
  var action = e.parameter.action || 'events';
  if (action === 'events') {
    var data = readJson_(EVENTS_FILE, { events: [] });
    var since = e.parameter.since || '';
    var evs = data.events.filter(function (x) { return !since || x.ts > since; });
    return json_({ events: evs, scannedAt: data.scannedAt || null });
  }
  if (action === 'state') return json_(readJson_(STATE_FILE, { state: null }));
  return json_({ ok: true });
}

function doPost(e) {
  var body = {};
  try { body = JSON.parse(e.postData.contents); } catch (err) { return json_({ error: 'json' }); }
  if (!authOk_(body.token)) return json_({ error: 'token' });
  if (body.state) {
    var cur = readJson_(STATE_FILE, { state: null });
    var curTs = cur.state && cur.state.updatedAt ? cur.state.updatedAt : '';
    if (!curTs || (body.state.updatedAt || '') >= curTs) writeJson_(STATE_FILE, { state: body.state });
  }
  return json_({ ok: true });
}

function authOk_(t) {
  var real = PropertiesService.getScriptProperties().getProperty('TOKEN');
  return !!real && t === real;
}

// ───────────────────────── Resumen semanal por correo ─────────────────────────
function weeklyDigest() {
  var st = readJson_(STATE_FILE, { state: null }).state;
  var ev = readJson_(EVENTS_FILE, { events: [] }).events;
  var since = new Date(Date.now() - 7 * 86400000).toISOString();
  var week = ev.filter(function (x) { return x.ts > since; });
  var lines = ['Resumen semanal de tus finanzas', ''];
  if (st && st.lastSnapshotDate) {
    var days = Math.floor((Date.now() - new Date(st.lastSnapshotDate + 'T12:00:00').getTime()) / 86400000);
    lines.push('Último snapshot de saldos: ' + st.lastSnapshotDate + ' (hace ' + days + ' días)');
    if (days > 14) lines.push('→ Abre la app y haz el Snapshot rápido (3 números).');
  } else {
    lines.push('La app aún no ha sincronizado su estado. Ábrela una vez con el conector configurado.');
  }
  lines.push('', 'Movimientos detectados esta semana: ' + week.length);
  week.forEach(function (x) {
    lines.push('- ' + x.fecha + ' · ' + x.tipo + (x.monto ? ' · $' + Math.round(x.monto).toLocaleString('es-CO') : '') + ' · ' + (x.detalle || ''));
  });
  MailApp.sendEmail(Session.getActiveUser().getEmail(), 'Finanzas · resumen semanal', lines.join('\n'));
}

// ───────────────────────── Utilidades de Drive ─────────────────────────
function readJson_(name, fallback) {
  var it = DriveApp.getFilesByName(name);
  if (!it.hasNext()) return fallback;
  try { return JSON.parse(it.next().getBlob().getDataAsString()); } catch (e) { return fallback; }
}
function writeJson_(name, obj) {
  var it = DriveApp.getFilesByName(name);
  var s = JSON.stringify(obj);
  if (it.hasNext()) it.next().setContent(s); else DriveApp.createFile(name, s, MimeType.PLAIN_TEXT);
}
function json_(o) { return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON); }
