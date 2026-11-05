import json, sys
from playwright.sync_api import sync_playwright

URL = 'file:///home/claude/finanzas/index.html'
fails = []
def check(cond, label, extra=''):
    print(('OK   ' if cond else 'FAIL ') + label + (' ' + str(extra) if (extra and not cond) else ''))
    if not cond: fails.append(label)

def fake_date(iso):
    return f"""(() => {{ const R = Date; const fixed = new R('{iso}').getTime();
      class D extends R {{ constructor(...a) {{ if (a.length) super(...a); else super(fixed); }} static now() {{ return fixed; }} }}
      window.Date = D; }})();"""

with sync_playwright() as p:
    b = p.chromium.launch()
    def newpage(date=None, init=None):
        ctx = b.new_context(viewport={'width':390,'height':844})
        pg = ctx.new_page()
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'ERR_TUNNEL' not in m.text else None)
        if date: pg.add_init_script(fake_date(date))
        if init: pg.add_init_script(init)
        return pg, errs

    # 1) Carga limpia, 5 nov (plan nuevo, saldos del 1 nov)
    pg, errs = newpage('2026-11-05T13:00:00-05:00')
    pg.goto(URL)
    check(not errs, 'sin errores de consola (nov)', errs)
    pg.evaluate("goScreen('inversiones')")
    metas = pg.inner_text('#metasCard')
    check('$14.707.834' in metas, 'patrimonio líquido $14.707.834', metas)
    check('$39.707.834' in metas, 'patrimonio total con préstamo $39.707.834', metas)
    check('$25.000.000' in metas and '$5.000.000 por entregar' in metas, 'préstamo 25M + 5M por entregar', metas)
    check('51,3%' in metas and '38,5%' in metas, 'metas: sin FE 51,3% (15M) y 38,5% (20M)', metas)
    check('64,7%' in metas and '48,5%' in metas, 'metas: con FE 64,7% y 48,5%', metas)
    check('$7.305.470' in metas and '$5.292.167' in metas, 'metas: faltan 7.305.470 sin FE / 5.292.167 con FE', metas)
    check('67,1%' in metas and '$986.696' in metas, 'FE 67,1% de 3M, faltan 986.696', metas)
    check('7 meses a $150.000' in metas, 'FE: 7 meses a $150.000', metas)
    trasl = pg.inner_text('#trasladoCard')
    check('$5.000.000 reservados' in trasl and '$3.299.162' in trasl and '$1.700.838' in trasl, 'tarjeta de préstamo pendiente', trasl)
    lst = pg.inner_text('#instrumentList')
    check('Fidurenta' in lst and '$263.346' in lst and 'estimado' in lst, 'lista: Fidurenta $263.346 marcado estimado', lst[:300])
    pg.evaluate("goScreen('diaadia')")
    eg = pg.inner_text('#egresosContent')
    check('Nu (liquidez)' not in eg, 'nov sin Nu', eg[:200])
    st = pg.evaluate("S")
    amt = {e['id']: e['amount'] for e in st['egresos']}
    check(amt['inv_trii'] == 300000 and amt['inv_fic'] == 150000 and amt['fe'] == 150000, 'nov: 300k Trii / 150k BC / 150k FE', amt)
    check(amt['parq'] == 150000 and amt['lavada'] == 100000, 'nov: parqueadero y lavada vigentes', amt)
    check(pg.evaluate("localStorage.getItem('samuel_finanzas_v6')") is not None, 'estado v6 persistido en la primera carga')
    # entregar préstamo
    pg.on('dialog', lambda d: d.accept())
    pg.evaluate("goScreen('inversiones')")
    antes = pg.evaluate("patrimonioTotal()")
    pg.evaluate("entregarPrestamo()")
    s1 = pg.evaluate("S")
    check(s1['prestamo']['capital'] == 30000000 and s1['prestamo']['entregado'], 'entrega: préstamo = 30M')
    check(abs(pg.evaluate("patrimonioTotal()") - antes) < 1, 'entrega: patrimonio total se conserva', (antes, pg.evaluate("patrimonioTotal()")))
    check(abs(pg.evaluate("totalInstrumentos()") - 7694529.67) < 1 and pg.evaluate("reservadoTotal()") == 0, 'entrega: reservado 0, portafolio invertido 7.694.530')
    check(pg.inner_text('#trasladoCard').strip() == '', 'entrega: desaparece la tarjeta')
    pg.screenshot(path='shot_nov_inv.png', full_page=True)

    # 2) Octubre → noviembre: rollover desde estado de octubre
    pgo, errso = newpage('2026-10-22T15:00:00-05:00')
    pgo.goto(URL)
    eg = pgo.evaluate("S.egresos.map(e=>e.id)")
    check('inv_nu' in eg, 'octubre conserva plan viejo (Nu)', eg)
    ctx_state = pgo.evaluate("localStorage.getItem('samuel_finanzas_v6')")
    pg2, errs2 = newpage('2026-11-03T09:00:00-05:00', init=f"if(!localStorage.getItem('samuel_finanzas_v6')) localStorage.setItem('samuel_finanzas_v6', {json.dumps(ctx_state)});")
    pg2.goto(URL)
    check(not errs2, 'sin errores (rollover)', errs2)
    st = json.loads(pg2.evaluate("localStorage.getItem('samuel_finanzas_v6')"))
    check(st['month'] == '2026-11', 'rollover automático a 2026-11', st['month'])
    check(len(st['meses']) == 1 and st['meses'][0]['mes'] == '2026-10', 'octubre archivado')
    check('inv_nu' not in [e['id'] for e in st['egresos']], 'noviembre sin Nu')

    # 3) Diciembre: parqueadero libre
    pg3, errs3 = newpage('2026-12-05T09:00:00-05:00')
    pg3.goto(URL)
    st3 = json.loads(pg3.evaluate("localStorage.getItem('samuel_finanzas_v6')"))
    amt3 = {e['id']: e['amount'] for e in st3['egresos']}
    check(st3['month'] == '2026-12' and amt3['parq'] == 0 and amt3['lavada'] == 100000, 'dic: parqueadero 0', amt3)

    # 4) Conector simulado + reglas automáticas (en noviembre)
    events = {'events': [
        {'id':'e1','ts':'2026-11-02T14:00:00Z','fecha':'2026-11-02','tipo':'trii_deposito','monto':300000,'detalle':'Depósito Trii'},
        {'id':'e2','ts':'2026-11-02T15:00:00Z','fecha':'2026-11-02','tipo':'bc_ingreso','monto':700000,'detalle':'CARLOS ECHEVERRI'},
        {'id':'e0','ts':'2026-09-30T15:00:00Z','fecha':'2026-09-30','tipo':'trii_deposito','monto':300000,'detalle':'Depósito Trii'},
    ], 'scannedAt':'x'}
    pg4, errs4 = newpage('2026-11-03T09:00:00-05:00')
    posts = []
    def route(r):
        req = r.request
        if req.method == 'POST':
            posts.append(req.post_data); r.fulfill(status=200, body='{"ok":true}', headers={'access-control-allow-origin':'*'}); return
        if 'action=state' in req.url: r.fulfill(status=200, body='{"state":null}', headers={'access-control-allow-origin':'*','content-type':'application/json'}); return
        r.fulfill(status=200, body=json.dumps(events), headers={'access-control-allow-origin':'*','content-type':'application/json'})
    pg4.route('https://script.google.com/**', route)
    pg4.goto(URL)
    pg4.evaluate("S.cfg.feedUrl='https://script.google.com/macros/s/TEST/exec'; S.cfg.token='tok'; save();")
    pg4.evaluate("syncAll(true)")
    pg4.wait_for_timeout(800)
    st4 = pg4.evaluate("S")
    trii = [e for e in st4['egresos'] if e['id']=='inv_trii'][0]
    cme = [i for i in st4['ingresos'] if i['id']=='cme'][0]
    us = [i for i in st4['instrumentos'] if i['id']=='acc500us'][0]
    check(trii['paid'] and trii.get('autoEv')=='e1', 'depósito Trii marca el aporte como pagado (auto)', trii)
    check(abs(us['valorActual'] - (2293691.68 + 300000)) < 0.01 and us['aportesPeriodo'] == 300000, 'aporte suma a 500 US', us)
    check(cme['paid'] and cme.get('autoEv')=='e2', 'ingreso 700.000 marca CME recibido (auto)', cme)
    check(len(st4['movimientos']) == 3, '3 movimientos registrados', len(st4['movimientos']))
    check(st4['cfg']['lastSync'] and not st4['cfg']['lastError'], 'sync OK', st4['cfg'])
    # idempotencia
    pg4.evaluate("syncAll(true)"); pg4.wait_for_timeout(500)
    st4b = pg4.evaluate("S")
    us2 = [i for i in st4b['instrumentos'] if i['id']=='acc500us'][0]
    check(abs(us2['valorActual'] - 2593691.68) < 0.01 and len(st4b['movimientos']) == 3, 'reintento no duplica eventos ni aportes', us2['valorActual'])
    pg4.wait_for_timeout(3300)
    check(len(posts) >= 1 and json.loads(posts[-1])['state']['cfg'] == {}, 'respaldo se sube sin URL ni token', posts[-1][:80] if posts else 'sin POST')
    check(not errs4, 'sin errores (sync)', errs4)

    # 5) Token inválido
    events_bak = events
    events = {'error':'token'}
    pg4.evaluate("syncAll(true)"); pg4.wait_for_timeout(500)
    err = pg4.evaluate("S.cfg.lastError")
    check(err and 'token' in err, 'token inválido se reporta', err)
    events = events_bak

    # 6) Snapshot rápido
    pg5, errs5 = newpage('2026-11-05T13:00:00-05:00')
    pg5.goto(URL)
    pg5.evaluate("goScreen('inversiones')")
    pg5.evaluate("openQuick()")
    pg5.fill('#qTrii', '7400000'); pg5.fill('#qBc', '300000'); pg5.fill('#qFe', '2000000')
    pg5.evaluate("saveQuick()")
    s5 = pg5.evaluate("S")
    check(abs(pg5.evaluate("totalInstrumentos()") - 7700000) < 1, 'snapshot rápido: portafolio invertido 7.700.000', pg5.evaluate("totalInstrumentos()"))
    check(abs(pg5.evaluate("reservadoTotal()") - 5000000) < 1, 'snapshot rápido: reservado se conserva ~5M', pg5.evaluate("reservadoTotal()"))
    check(s5['lastSnapshotDate'] == '2026-11-05' and s5['historial'][-1]['fecha'] == '2026-11-05', 'historial registra el snapshot', s5['historial'][-1])
    check(s5['historial'][-1].get('prestamo') == 25000000, 'historial guarda préstamo')
    check(s5['fe']['actual'] == 2000000, 'FE actualizado')
    check(not errs5, 'sin errores (snapshot)', errs5)

    # 7) Migración
    old = {'month':'2026-11','ingresos':[{'id':'cme','label':'CME','amount':700000,'paid':True}],'egresos':[{'id':'fe','label':'FE','amount':150000,'paid':False,'cat':'ahorro'}],'gastos':[{'id':'g1','label':'Almuerzo','amount':30000,'cat':'comida'}],
           'fe':{'actual':2100000,'meta':5541000,'lastUpdate':'2026-11-03'},'instrumentos':[{'id':'acc500us','nombre':'X','plataforma':'Trii','valorActual':1,'valorAnterior':1,'aportesPeriodo':0,'benchmark':'','proximo':''}],'lastSnapshotDate':'2026-11-03','aporteEstimadoAcumulacion':80000}
    pg6, errs6 = newpage('2026-11-05T13:00:00-05:00', init=f"localStorage.setItem('samuel_finanzas_v4', {json.dumps(json.dumps(old))});")
    pg6.goto(URL)
    s6 = pg6.evaluate("S")
    check(s6['instrumentos'][0]['valorActual'] == 1 and s6['fe']['actual'] == 2100000 and s6['fe']['meta'] == 3000000, 'migración v4 más reciente: conserva saldos y corrige meta FE', s6['fe'])
    check(s6['gastos'][0]['label'] == 'Almuerzo' and s6['ingresos'][0]['paid'] is True, 'migración conserva gastos e ingresos del mes')
    check(not errs6, 'sin errores (migración v4)', errs6)
    old['lastSnapshotDate'] = '2026-10-04'
    pg7, errs7 = newpage('2026-11-05T13:00:00-05:00', init=f"localStorage.setItem('samuel_finanzas_v4', {json.dumps(json.dumps(old))});")
    pg7.goto(URL)
    s7 = pg7.evaluate("S")
    check(len(s7['instrumentos']) == 9 and s7['lastSnapshotDate'] == '2026-11-01', 'v4 viejo se reemplaza por capturas del 1 nov', s7['lastSnapshotDate'])
    # v5 con conector configurado conserva cfg
    v5 = dict(old, v=5, cfg={'feedUrl':'https://script.google.com/macros/s/X/exec','token':'t','lastSync':None,'lastError':None,'lastEventTs':'2026-11-02T00:00:00Z'}, movimientos=[{'id':'m1','tipo':'trii_deposito','monto':300000,'fecha':'2026-11-02','detalle':'x'}], eventosVistos=['e1'], meses=[])
    pg8, errs8 = newpage('2026-11-05T13:00:00-05:00', init=f"localStorage.setItem('samuel_finanzas_v5', {json.dumps(json.dumps(v5))});")
    pg8.goto(URL)
    s8 = pg8.evaluate("S")
    check(s8['cfg']['feedUrl'].endswith('/X/exec') and s8['cfg']['token'] == 't' and s8['eventosVistos'] == ['e1'] and len(s8['movimientos']) == 1, 'migración v5 conserva conector, eventos y movimientos', s8['cfg'])
    check(not errs7 and not errs8, 'sin errores (migración v5)', errs7 + errs8)
    b.close()

print('\nFALLAS:', fails if fails else 'ninguna')
sys.exit(1 if fails else 0)
