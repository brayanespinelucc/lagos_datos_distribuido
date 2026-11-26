"use strict";
window.createLakeViews = function createLakeViews(ctx) {
  const {data,icon,esc,norm,fmt,sizeName,fileUrl,fileMap,bySuffix,reqs,pageHead,linkButton,fileList,definition,chip,routeLink,buttonView,download,getParams}=ctx;
  const files=data.files;
  let timer;
  const state={layer:"",table:"",query:"",catalog:"",flow:0,metric:"",lab:1,minio:[true,true,true],worker:[true,true],phase:0};
  const tableKey=table=>table.layer+"/"+table.name;
  const first=(array,key,val)=>array.find(item=>key(item)===val) || array[0];
  const list=values=>values.filter(Boolean);
  const help=text=>'<p class="section-note">'+esc(text)+'</p>';
  const head=(title,body)=>'<div class="section-head"><h2>'+esc(title)+'</h2></div>'+(body ? '<p class="section-description">'+esc(body)+'</p>':'');
  const darkCard=(label,text)=>'<div class="mini-stat"><small>'+esc(label)+'</small><strong>'+esc(text)+'</strong></div>';
  const choose=(key,title,items,value)=>'<label class="field"><span>'+esc(title)+'</span><select data-choice="'+key+'">'+items.map(([v,l])=>'<option value="'+esc(v)+'"'+(v===value?' selected':'')+'>'+esc(l)+'</option>').join("")+'</select></label>';
  const action=(key,label,options='')=>'<button type="button" class="button" data-action="'+key+'" '+options+'>'+esc(label)+'</button>';
  const tagged=(label)=>'<span class="chip">'+esc(label)+'</span>';
  const pathFile=(path)=>fileMap.get(path);
  const toText=(v)=>typeof v==="object" ? JSON.stringify(v):String(v??"");
  const actions=assets=>assets.length?fileList(assets):'';
  function tableGrid(columns,rows,caption="Tabla de datos") {
    if (!columns?.length) return '<p class="empty">La exportación no incluye columnas.</p>';
    const names=columns.map(col=>typeof col==="string" ? col:col.name);
    return '<div class="list-rows table-wrap" tabindex="0" aria-label="'+esc(caption)+'"><table><thead><tr>'+names.map(name=>'<th scope="col">'+esc(name)+'</th>').join("")+'</tr></thead><tbody>'+rows.map(row=>'<tr>'+names.map((name,i)=>'<td>'+esc(toText(Array.isArray(row)?row[i]:row[name]))+'</td>').join("")+'</tr>').join("")+'</tbody></table></div>';
  }
  function unavailable(text) {return help(text)+linkButton("Consultar trazabilidad","#trazabilidad","plain-button");}
  function sampleMetric(records,keys) {
    for(const key of keys) if(records[key]!==undefined) return records[key];
    return undefined;
  }
  function lake() {
    const tables=data.lake?.tables || [];
    const prefix=pageHead("Momento 2 · Exportación","Explorador del lago","Revise los archivos físicos de las tres capas. Las vistas previas proceden del lote exportado y se pueden consultar sin una conexión a MinIO.");
    if(!tables.length) return prefix+unavailable("Este paquete todavía no incluye un manifiesto del lote de datos.");
    const layerNames=[...new Set(tables.map(t=>t.layer))];
    const selectedLayer=layerNames.includes(state.layer)?state.layer:layerNames[0];
    const subset=tables.filter(t=>t.layer===selectedLayer);
    const t=first(subset,tableKey,state.table);
    const filesForTable=t.files.map(item=>pathFile(item.path)).filter(Boolean);
    const choices=layerNames.map(l=>[l,l.charAt(0).toUpperCase()+l.slice(1)]);
    const selected=tableKey(t);
    return prefix+'<div class="tools">'+choose("layer","Capa",choices,selectedLayer)+choose("table","Dataset",subset.map(t=>[tableKey(t),t.name]),selected)+'</div>'+
      '<div class="stat-row">'+darkCard("Registros",fmt(t.rows))+darkCard("Columnas",fmt(t.columns.length))+darkCard("Formato",String(t.format).toUpperCase())+'</div>'+
      head("Vista previa",Math.min((t.preview||[]).length,t.rows)+" de "+fmt(t.rows)+" registros de "+t.name+".")+tableGrid(t.columns,t.preview||[],t.name)+
      head("Esquema")+tableGrid(["Columna","Tipo"],t.columns.map(c=>[c.name,c.type]),"Esquema de "+t.name)+
      head("Archivos del dataset","Cada descarga conserva el archivo generado por el laboratorio.")+actions(filesForTable);
  }
  const steps=[
    {service:"Fuentes",name:"Sistemas comerciales",detail:"El generador crea un lote sintético de ventas, inventario y catálogos relacionados."},
    {service:"Airflow",name:"Orquestación",detail:"El DAG ordena la generación, ingesta, transformación, control de calidad y publicación de metadatos."},
    {service:"Bronze",name:"Objetos originales",detail:"La carga conserva la copia cruda de los archivos de origen en el primer nivel del lago."},
    {service:"Spark",name:"Validación y limpieza",detail:"El procesamiento tipa campos, aplica reglas de negocio y separa los registros rechazados."},
    {service:"Silver",name:"Datos depurados",detail:"Las tablas conservan filas aceptadas y relaciones normalizadas para análisis."},
    {service:"Spark",name:"Agregación",detail:"Las transformaciones calculan indicadores por fecha y producto a partir de las tablas depuradas."},
    {service:"Gold",name:"Indicadores",detail:"Las tablas de consumo reúnen los resultados analíticos en archivos Parquet."},
    {service:"Trino",name:"Consulta SQL",detail:"El motor consulta los datos del lago. Sus resultados se pueden revisar en el módulo SQL."},
    {service:"DataHub",name:"Catálogo y linaje",detail:"Los metadatos describen tablas, columnas, responsables y relaciones entre capas."}
  ];
  function jsonFile(path) {
    const f=pathFile(path);
    if(!f?.preview || f.truncated) return null;
    try {return JSON.parse(f.preview)} catch{return null}
  }
  function flowPicture() {
    const step=steps[state.flow];
    return '<div id="flow-picture" class="interactive-block">'+
      '<ol class="steps">'+steps.map((s,i)=>'<li><button data-scene="'+i+'" aria-pressed="'+(i===state.flow)+'">'+esc(s.service)+'</button></li>').join("")+'</ol>'+
      '<div class="step-body" aria-live="polite"><strong>'+esc(step.name)+'</strong><p>'+esc(step.detail)+'</p></div>'+
      '<div class="control-row">'+action("flow-play",timer?"Pausar animación":"Reproducir animación")+action("flow-next","Siguiente etapa")+action("flow-reset","Volver al inicio")+'</div></div>';
  }
  function flow() {
    const record=jsonFile("evidence/moment-02/airflow/dagrun.json");
    const dag=bySuffix("/dags/lago_medallion.py");
    let run=record ? '<div class="stat-row">'+darkCard("DagRun",record.state)+darkCard("Tareas registradas",fmt(record.tasks?.length||0))+darkCard("Inicio",record.started_at || record.logical_date || "Sin fecha")+'</div><p class="data-source">'+esc(record.dag_id)+' · '+esc(record.run_id)+'</p>'+
      tableGrid(["Tarea","Estado","Duración (s)"],(record.tasks || []).map(t=>[t.task_id,t.state,t.duration_seconds??""]), "Tareas registradas del DAG") :
      help("Este paquete todavía carece del registro de DagRun. La animación explica el diseño del flujo.");
    const related=files.filter(f=>f.path.startsWith("evidence/moment-02/airflow/"));
    return pageHead("Momento 2 · Procesamiento","Flujo de datos","Siga la ruta de un lote y contraste sus etapas con las tareas registradas del DAG de Airflow.")+
      head("Recorrido ilustrado","Animación explicativa de la arquitectura Medallion.")+flowPicture()+head("Ejecución registrada de Airflow")+run+head("Código y registros")+actions(list([dag,...related]));
  }
  function chartPreview(rows,cols) {
    if(!rows.length || cols.length<2) return '';
    const numeric=cols.find(c=>rows.every(r=>r[c]!=="" && r[c]!=null && Number.isFinite(Number(r[c]))) && !/id|fecha|año|year/i.test(c));
    if(!numeric) return '';
    const label=cols.find(c=>c!==numeric);
    const slice=rows.slice(0,6), max=Math.max(...slice.map(r=>Math.abs(Number(r[numeric]))));
    if(!max) return '';
    return head("Vista gráfica",numeric+" por "+label+" en las primeras "+slice.length+" filas de la salida.")+
      '<div class="bars">'+slice.map(r=>'<div class="bar"><span>'+esc(r[label])+'</span><div><i style="width:'+Math.max(1,Math.abs(Number(r[numeric]))/max*100)+'%"></i></div><strong>'+esc(fmt(r[numeric]))+'</strong></div>').join("")+'</div>';
  }
  function sql() {
    const model=data.sql||{}, qs=model.queries||[];
    const intro=pageHead("Momento 2 · Resultados exportados","Consultas SQL","Seleccione una consulta para revisar su código, su identificador de ejecución y el resultado CSV que produjo el motor.");
    if(!qs.length) return intro+unavailable("Todavía no se incorporó un índice de consultas ejecutadas en esta copia.");
    const q=first(qs,x=>x.id,state.query);
    const source=pathFile(q.sql), csv=pathFile(q.csv), cols=q.columns||[], rows=q.preview||[];
    return intro+'<div class="tools">'+choose("query","Consulta",qs.map(x=>[x.id,x.title]),q.id)+'</div>'+
      '<div class="stat-row">'+darkCard("Motor",(model.engine||"Trino")+" "+(model.version||""))+darkCard("Filas de salida",fmt(q.rows))+darkCard("Consultas registradas",fmt(qs.length))+'</div>'+
      head(q.title)+
      '<p class="data-source">Ejecución '+esc(q.query_id||"sin ID exportado")+' · '+esc(model.executed_at||"")+'</p>'+
      (source?'<pre class="sql-code"><code>'+esc(source.preview)+'</code></pre>':'')+
      head("Resultado registrado",(q.rows>rows.length?"Se muestran "+rows.length+" de "+q.rows+" filas. ":"")+"Descargue el CSV para consultar la salida completa.")+tableGrid(cols,rows,q.title)+
      chartPreview(rows,cols)+head("Archivos de la consulta")+actions(list([csv,source]));
  }
  function catalog() {
    const model=data.catalog||{}, ds=model.datasets||[];
    const intro=pageHead("Momento 2 · Catálogo exportado","Gobierno de datos","Consulte el diccionario, la clasificación y las dependencias de los datasets definidos en el catálogo académico.");
    if(!ds.length) return intro+unavailable("Todavía no se incorporó el catálogo exportado a este paquete.");
    const selected=first(ds,item=>item.id,state.catalog);
    const parents=selected.upstream||[], children=ds.filter(d=>(d.upstream||[]).includes(selected.id));
    const label=id=>ds.find(t=>t.id===id)?.name||id;
    const sibling=(id)=>'<button class="button" data-dataset="'+esc(id)+'">'+esc(label(id))+'</button>';
    return intro+'<div class="tools">'+choose("catalog","Dataset",ds.map(d=>[d.id,d.layer+" · "+d.name]),selected.id)+'</div><section class="panel panel-pad"><h2>'+esc(selected.name)+'</h2><p>'+esc(selected.description)+'</p>'+
      definition([["Capa",String(selected.layer||"")],["Dominio",toText(selected.domain)],["Responsable",toText(selected.owner)],["Clasificación",toText(selected.classification)],["Ruta física",toText(selected.physical_path)],["URN",toText(selected.urn)]])+'</section>'+
      head("Relaciones de linaje","Seleccione un dataset relacionado para recorrer sus orígenes o destinos.")+
      '<div class="lineage"><div><small>Orígenes directos</small>'+(parents.length?parents.map(sibling).join(""):'<span>Fuente inicial</span>')+'</div><b aria-hidden="true">→</b><div class="selected"><small>Dataset seleccionado</small><strong>'+esc(selected.name)+'</strong></div><b aria-hidden="true">→</b><div><small>Destinos directos</small>'+(children.length?children.map(d=>sibling(d.id)).join(""):'<span>Sin dependientes registrados</span>')+'</div></div>'+
      head("Diccionario de columnas")+tableGrid(["Nombre","Tipo","Definición"],(selected.columns||[]).map(c=>[c.name,c.type,c.description]),"Diccionario de datos")+
      (model.glossary?.length?head("Glosario")+tableGrid(["Término","Definición"],model.glossary.map(t=>[t.term,t.definition])):'')+head("Exportaciones de gobierno")+actions(files.filter(f=>f.path.startsWith("results/catalog/")));
  }
  function monitor() {
    const dashboards=files.filter(f=>f.path.startsWith("monitoring/grafana/dashboards/") && f.format==="JSON");
    const series=data.metrics || jsonFile("evidence/moment-03/monitoring/mediciones.json");
    const evidence=files.filter(f=>f.path.startsWith("evidence/moment-03/monitoring/"));
    const picture=evidence.find(f=>f.path.endsWith("captura-grafana.png"));
    const queries = series?.queries || {};
    const qEntries=Array.isArray(queries)?queries.map((entry,i)=>[entry.nombre || entry.query || String(i+1),entry]):Object.entries(queries);
    const selected=qEntries.find(([key])=>key===state.metric)||qEntries[0];
    let view=help("Aún no se incorporó una exportación de métricas a esta copia. Los tableros disponibles pueden descargarse en JSON.");
    if (selected) {
      const item=selected[1];
      const raw=item.result || item.data?.result || item.respuesta?.data?.result || item.resultado || (Array.isArray(item)?item:[]);
      const flat=Array.isArray(raw)?raw.flatMap(series=>{
        const labels=series.metric || series.etiquetas || {};
        const samples=series.values || (series.value?[series.value]:[]);
        return samples.slice(-18).map(([stamp,value])=>[Object.entries(labels).filter(([k])=>k!=="__name__").map(([k,v])=>k+"="+v).join(", "), Number.isFinite(Number(stamp))?new Date(Number(stamp)*1000).toISOString():stamp, value]);
      }):[];
      view='<p class="data-source">'+esc(series.inicio_utc || "")+' — '+esc(series.fin_utc || "")+' (UTC)</p><div class="tools">'+choose("metric","Consulta de métricas",qEntries.map(([k])=>[k,k]),selected[0])+'</div>'+
        (flat.length?tableGrid(["Serie","Hora UTC","Valor observado"],flat,"Métricas históricas exportadas"):help("La exportación no contiene muestras visibles para esta consulta. Consulte el registro original."))+
        (item.promql || item.expression ? '<pre class="sql-code">'+esc(item.promql||item.expression)+'</pre>':'');
    }
    return pageHead("Momento 3 · Observaciones históricas","Monitoreo","Los tableros de Grafana y las mediciones de Prometheus se presentan como exportaciones. Las horas corresponden a la ejecución registrada.")+
      head("Métricas registradas")+view+
      (picture?head("Vista registrada de Grafana")+'<button class="thumb-button" data-view="'+esc(picture.path)+'"><img alt="Captura de un tablero de Grafana del laboratorio" src="'+esc(fileUrl(picture))+'"><span>Ampliar captura real</span></button>':'')+
      head("Dashboards importables","Archivos JSON de Grafana incluidos en esta compilación.")+actions(dashboards)+head("Evidencias de monitoreo")+actions(evidence);
  }
  const scenarioNames=["Ingesta con Airflow","Consulta con Trino","Caída de MinIO","Recuperación de MinIO","Caída de un worker","Métricas en Grafana"];
  function lab() {
    const selected=Number(state.lab);
    const row=reqs.find(r=>r.id==="M3-P"+selected);
    const nodeCount=state.minio.filter(Boolean).length;
    const disks=nodeCount*2;
    let model='';
    if(selected===3 || selected===4) {
      const ops=disks>=4;
      model='<p>Tres nodos aportan dos discos cada uno. El conjunto EC:2 distribuye cuatro fragmentos de datos y dos de paridad. El modelo supone discos sanos en cada nodo conectado y ausencia de otros fallos.</p><div class="control-row">'+state.minio.map((up,i)=>action("minio-"+i,(up?"Apagar":"Recuperar")+" minio-"+(i+1),'aria-pressed="'+up+'"')).join("")+'</div><div class="stat-row">'+darkCard("Nodos conectados",nodeCount+" / 3")+darkCard("Discos accesibles",disks+" / 6")+darkCard("Quórum de lectura y escritura",ops?"Disponible · 4 requeridos":"Insuficiente")+'</div>';
    } else if(selected===5) {
      const available=state.worker.filter(Boolean).length;
      model='<p>El control plane permanece activo. El ejercicio modela dos workers con capacidad suficiente para una réplica sin estado. Un volumen ligado al nodo o falta de recursos puede impedir la reprogramación real.</p><div class="control-row">'+state.worker.map((up,i)=>action("worker-"+i,(up?"Apagar":"Recuperar")+" worker-"+(i+1),'aria-pressed="'+up+'"')).join("")+'</div><div class="stat-row">'+darkCard("Workers disponibles",available+" / 2")+darkCard("Reprogramación esperada",available?"Posible según capacidad":"Sin destino")+'</div>';
    } else {
      const controls={1:["Generar lote","Ingestar Bronze","Transformar Silver y Gold","Validar lote"],2:["Seleccionar consulta","Leer catálogo","Consultar Gold","Revisar resultado"],6:["Seleccionar fuente","Consultar series","Representar panel","Revisar intervalo"]}[selected];
      const target={1:["flujo","Ver DagRun registrado"],2:["consultas","Ver resultados SQL"],6:["monitoreo","Ver métricas históricas"]}[selected];
      model='<ol class="steps">'+controls.map((name,i)=>'<li><span class="'+(i===state.phase?"active ":"")+'phase">'+esc(name)+'</span></li>').join("")+'</ol><p class="step-body">Etapa '+(state.phase+1)+' de '+controls.length+' · '+esc(controls[state.phase])+'</p><div class="control-row">'+action("lab-next","Avanzar una etapa") +linkButton(target[1],"#"+target[0],"plain-button")+'</div>';
    }
    const related=files.filter(f=>f.references.includes("M3-P"+selected));
    return pageHead("Momento 3 · Simulación","Laboratorio de pruebas","Explore la respuesta esperada de seis escenarios. Los controles modifican el modelo en este navegador. La evidencia de ejecución se consulta por separado.")+
      '<div class="tools">'+choose("lab","Escenario",scenarioNames.map((n,i)=>[String(i+1),(i+1)+". "+n]),String(selected))+'</div>'+
      '<section class="panel panel-pad"><div class="heading-inline"><h2>'+esc(scenarioNames[selected-1])+'</h2>'+tagged("Simulación")+'</div>'+model+'<div class="control-row">'+action("lab-reset","Restablecer escenario")+'</div></section>'+
      head("Registro de la prueba")+(row?'<p>'+chip(row.estado)+' '+esc(row.limitaciones)+'</p>'+linkButton("Abrir requisito "+row.id,routeLink("trazabilidad",{q:row.id}),"plain-button"):'')+actions(related)+
      actions(list([bySuffix("docs/moment-03/entrega/pruebas.pdf")]));
  }
  function support() {
    const video=pathFile("video/sustentacion.mp4"), src=video?fileUrl(video):data.videoUrl;
    const caption=pathFile("video/subtitulos.vtt"), pptx=pathFile("presentation/sustentacion.pptx");
    const docs=list([pptx,pathFile("presentation/sustentacion.pdf"),pathFile("docs/final/entrega/informe-final.pdf"),pathFile("docs/final/entrega/preguntas.pdf"),pathFile("video/guion.md"),pathFile("video/storyboard.csv"),pathFile("video/subtitulos.srt"),video]);
    return pageHead("Entrega integral","Sustentación","Revise la presentación, siga el guion y contraste los resultados con las pruebas de cada momento.")+
      (video?'<video controls preload="metadata" aria-label="Video de sustentación" src="'+esc(src)+'">'+(caption?'<track kind="captions" srclang="es" label="Español" src="'+esc(fileUrl(caption))+'">':'')+'</video>':src?'<a class="button" href="'+esc(src)+'" target="_blank" rel="noopener">Abrir video publicado '+icon("external")+'</a>':help("La compilación consultada no contiene un MP4 reproducible. Los materiales disponibles aparecen en esta sección."))+
      head("Material de sustentación")+actions(docs)+head("Recorrido de revisión")+'<div class="control-row">'+linkButton("1 · Arquitectura","#infraestructura")+linkButton("2 · Flujo","#flujo")+linkButton("3 · Validación","#laboratorio")+'</div>';
  }
  const renderers={lago:lake,flujo:flow,consultas:sql,gobierno:catalog,monitoreo:monitor,laboratorio:lab,sustentacion:support};
  function refresh(section,focusKey) {
    document.querySelector("#contenido").innerHTML=renderers[section]();
    if(focusKey) document.querySelector('[data-choice="'+focusKey+'"]')?.focus({preventScroll:true});
  }
  function stop() {if(timer) clearInterval(timer);timer=undefined;}
  function flowUpdate() {
    const old=document.querySelector("#flow-picture");
    if(old) old.outerHTML=flowPicture();
  }
  function click(section,event) {
    const hit=event.target.closest("[data-action],[data-dataset],[data-scene]");
    if(!hit) return false;
    if(hit.dataset.dataset!==undefined) {state.catalog=hit.dataset.dataset;refresh(section,"catalog");return true;}
    if(hit.dataset.scene!==undefined) {stop();state.flow=Number(hit.dataset.scene);flowUpdate();return true;}
    const name=hit.dataset.action;
    if(name.startsWith("flow-")) {
      if(name==="flow-reset") {stop();state.flow=0;}
      if(name==="flow-next") {stop();state.flow=(state.flow+1)%steps.length;}
      if(name==="flow-play") {
        if(timer) stop(); else timer=setInterval(()=>{if(state.flow>=steps.length-1) {stop();state.flow=0;} else state.flow++;flowUpdate();},1800);
      }
      flowUpdate();document.querySelector('[data-action="'+name+'"]')?.focus({preventScroll:true});return true;
    }
    if(name.startsWith("minio-")){const i=Number(name.slice(6));state.minio[i]=!state.minio[i];}
    if(name.startsWith("worker-")){const i=Number(name.slice(7));state.worker[i]=!state.worker[i];}
    if(name==="lab-next")state.phase=(state.phase+1)%4;
    if(name==="lab-reset"){state.minio=state.lab===4?[false,true,true]:[true,true,true];state.worker=[true,true];state.phase=0;}
    refresh(section);document.querySelector('[data-action="'+name+'"]')?.focus({preventScroll:true});return true;
  }
  function change(section,event) {
    const el=event.target.closest("[data-choice]");
    if(!el) return false;
    const key=el.dataset.choice;
    state[key]=key==="lab"?Number(el.value):el.value;
    if(key==="layer")state.table="";
    if(key==="lab") {state.minio=state.lab===4?[false,true,true]:[true,true,true];state.phase=0;state.worker=[true,true];}
    refresh(section,key);return true;
  }
  return {renderers,click,change,stop};
};
